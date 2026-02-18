import sys
import time
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QListWidget, QLabel, QSpinBox, QDoubleSpinBox,
    QGroupBox, QSplitter, QMessageBox, QInputDialog, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont
from pynput import keyboard
import pyperclip
import json


class AnimationSignals(QObject):
    """Signals for thread-safe communication"""
    frame_played = pyqtSignal(int)
    animation_complete = pyqtSignal()


# The full truck sprite (each line is exactly 26 characters)
TRUCK_SPRITE = [
    "▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒",
    "▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒",
    "▛▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀█▒▒▒▒▒",
    "▌▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒█▄▄▄▒▒",
    "▌▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒█▒▒▐▒▒",
    "▌▒▒▒▀▀▜▒▀▀▜▒▛▜▒▛▜▒▒▒█║█▐▒▒",
    "▌▄▄▒▄▄▟▒▄▄▟║▙▟▒▙▟▒▒▒█║▌▐▒▒",
    "▌▒▒▒▌▒▒▒▌▒▒▒▌▌▒▌▌▒▒▒█████▒",
    "▌▒▒▒▙▄▄▒▙▄▄▒▌▙▒▌▙▒▒▒█████▒",
    "▌▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒█████▒",
    "▙▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄█████▒",
    "▒▒▛▜▛▜▒▒▒▒▒▒▒▒▒▒▛▜▛▜▒▒▒▒▒▒",
    "▒▒▙▟▙▟▒▒▒▒▒▒▒▒▒▒▙▟▙▟▒▒▒▒▒▒",
]

# Background character
BG_CHAR = "▒"
SCREEN_WIDTH = 26  # Each line is 26 characters
TRUCK_WIDTH = 26

def generate_truck_frames():
    """
    Generate frames for the truck scrolling left to right.
    - Frame 0: All background (truck fully off-screen left)
    - Truck enters from left, scrolls right, exits right
    - Each frame has exactly 13 lines of 26 characters
    - Space added after every 26 chars for Valorant compatibility
    """
    frames = []
    
    # truck_pos: position of truck's left edge relative to screen
    # -TRUCK_WIDTH = fully off left, 0 = at left edge, SCREEN_WIDTH = fully off right
    for truck_pos in range(-TRUCK_WIDTH, SCREEN_WIDTH + 1):
        frame_lines = []
        for sprite_line in TRUCK_SPRITE:
            line = ""
            for screen_x in range(SCREEN_WIDTH):
                # Which column of the truck would be at this screen position?
                truck_x = screen_x - truck_pos
                if 0 <= truck_x < TRUCK_WIDTH:
                    line += sprite_line[truck_x]
                else:
                    line += BG_CHAR
            frame_lines.append(line)
        frames.append(frame_lines)
    
    return frames

def format_frame_for_valorant(frame_lines):
    """
    Combine all lines into one string with spaces after every 26 characters.
    Each line is 26 chars, so we add a space after each line.
    """
    result = ""
    for line in frame_lines:
        result += line + " "
    return result.rstrip()  # Remove trailing space

# Generate the full animation frames
TRUCK_ANIMATION = generate_truck_frames()


CONFIG_FILE = "animation_config.json"

def load_animation_config():
    """Load animation configuration from file"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"animations": {"Truck": {"skip_frames": 5, "frame_delay": 0.5}}}

def save_animation_config(config):
    """Save animation configuration to file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


class AnimationPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.frames = TRUCK_ANIMATION.copy()  # Each frame is a list of lines
        self.keyboard_controller = keyboard.Controller()
        self.signals = AnimationSignals()
        self.is_playing = False
        self.current_animation = "Truck"
        
        # Load config
        self.config = load_animation_config()
        anim_config = self.config.get("animations", {}).get("Truck", {})
        self.frame_delay = anim_config.get("frame_delay", 0.5)
        self.skip_frames = anim_config.get("skip_frames", 5)
        self.line_delay = 0.05  # seconds between lines within a frame
        
        self.signals.frame_played.connect(self.on_frame_played)
        self.signals.animation_complete.connect(self.on_animation_complete)
        
        self.init_ui()
        self.load_default_animation()
        
    def load_default_animation(self):
        """Load the default truck animation into the UI"""
        self.frames_list.clear()
        for i in range(len(self.frames)):
            self.frames_list.addItem(f"Frame {i+1}")
        if self.frames:
            self.frames_list.setCurrentRow(0)
        self.delay_spin.setValue(self.frame_delay)
        self.skip_spin.setValue(self.skip_frames)
        self.status_label.setText(f"Truck animation loaded - {len(self.frames)} frames, {len(TRUCK_SPRITE)} lines each")
        
    def init_ui(self):
        self.setWindowTitle("Valorant ASCII Animation Player")
        self.setMinimumSize(800, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Splitter for frames list and editor
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - Frames list
        frames_group = QGroupBox("Frames")
        frames_layout = QVBoxLayout(frames_group)
        
        self.frames_list = QListWidget()
        self.frames_list.currentRowChanged.connect(self.on_frame_selected)
        frames_layout.addWidget(self.frames_list)
        
        # Frame buttons
        frame_buttons = QHBoxLayout()
        
        add_btn = QPushButton("Add Frame")
        add_btn.clicked.connect(self.add_frame)
        frame_buttons.addWidget(add_btn)
        
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_frame)
        frame_buttons.addWidget(remove_btn)
        
        frames_layout.addLayout(frame_buttons)
        
        move_buttons = QHBoxLayout()
        
        up_btn = QPushButton("Move Up")
        up_btn.clicked.connect(self.move_frame_up)
        move_buttons.addWidget(up_btn)
        
        down_btn = QPushButton("Move Down")
        down_btn.clicked.connect(self.move_frame_down)
        move_buttons.addWidget(down_btn)
        
        frames_layout.addLayout(move_buttons)
        
        splitter.addWidget(frames_group)
        
        # Right side - Frame editor
        editor_group = QGroupBox("Frame Editor")
        editor_layout = QVBoxLayout(editor_group)
        
        self.frame_editor = QTextEdit()
        self.frame_editor.setFont(QFont("Consolas", 10))
        self.frame_editor.setPlaceholderText("Paste your ASCII art frame here...")
        self.frame_editor.textChanged.connect(self.on_editor_changed)
        editor_layout.addWidget(self.frame_editor)
        
        update_btn = QPushButton("Update Frame")
        update_btn.clicked.connect(self.update_current_frame)
        editor_layout.addWidget(update_btn)
        
        splitter.addWidget(editor_group)
        splitter.setSizes([250, 550])
        
        main_layout.addWidget(splitter)
        
        # Settings
        settings_layout = QHBoxLayout()
        
        settings_layout.addWidget(QLabel("Delay between frames (seconds):"))
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.1, 5.0)
        self.delay_spin.setSingleStep(0.1)
        self.delay_spin.setValue(0.5)
        self.delay_spin.valueChanged.connect(lambda v: setattr(self, 'frame_delay', v))
        settings_layout.addWidget(self.delay_spin)
        
        settings_layout.addWidget(QLabel("Skip frames (1=all, 2=every other):"))
        self.skip_spin = QSpinBox()
        self.skip_spin.setRange(1, 10)
        self.skip_spin.setValue(1)
        self.skip_spin.valueChanged.connect(lambda v: setattr(self, 'skip_frames', v))
        settings_layout.addWidget(self.skip_spin)
        
        settings_layout.addStretch()
        
        # Save/Load buttons
        save_btn = QPushButton("Save Animation")
        save_btn.clicked.connect(self.save_animation)
        settings_layout.addWidget(save_btn)
        
        load_btn = QPushButton("Load Animation")
        load_btn.clicked.connect(self.load_animation)
        settings_layout.addWidget(load_btn)
        
        save_config_btn = QPushButton("Save Settings")
        save_config_btn.clicked.connect(self.save_config)
        save_config_btn.setToolTip("Save current skip/delay settings for this animation")
        settings_layout.addWidget(save_config_btn)
        
        main_layout.addLayout(settings_layout)
        
        # Playback controls
        playback_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("▶ Play Animation in Valorant")
        self.play_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        self.play_btn.clicked.connect(self.play_animation)
        playback_layout.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        self.stop_btn.clicked.connect(self.stop_animation)
        self.stop_btn.setEnabled(False)
        playback_layout.addWidget(self.stop_btn)
        
        main_layout.addLayout(playback_layout)
        
        # Status
        self.status_label = QLabel("Ready - Add frames and press Play")
        self.status_label.setStyleSheet("color: gray; padding: 5px;")
        main_layout.addWidget(self.status_label)
        
    def add_frame(self):
        """Add a new frame"""
        self.frames.append([])  # Empty list for multi-line frame
        self.frames_list.addItem(f"Frame {len(self.frames)}")
        self.frames_list.setCurrentRow(len(self.frames) - 1)
        self.frame_editor.clear()
        self.frame_editor.setFocus()
        
    def remove_frame(self):
        """Remove selected frame"""
        row = self.frames_list.currentRow()
        if row >= 0:
            self.frames.pop(row)
            self.frames_list.takeItem(row)
            self.update_frame_labels()
            
    def move_frame_up(self):
        """Move selected frame up"""
        row = self.frames_list.currentRow()
        if row > 0:
            self.frames[row], self.frames[row-1] = self.frames[row-1], self.frames[row]
            self.frames_list.setCurrentRow(row - 1)
            self.update_frame_labels()
            
    def move_frame_down(self):
        """Move selected frame down"""
        row = self.frames_list.currentRow()
        if row < len(self.frames) - 1:
            self.frames[row], self.frames[row+1] = self.frames[row+1], self.frames[row]
            self.frames_list.setCurrentRow(row + 1)
            self.update_frame_labels()
            
    def update_frame_labels(self):
        """Update frame list labels"""
        for i in range(self.frames_list.count()):
            self.frames_list.item(i).setText(f"Frame {i+1}")
            
    def on_frame_selected(self, row):
        """When a frame is selected, show it in editor"""
        if 0 <= row < len(self.frames):
            self.frame_editor.blockSignals(True)
            frame = self.frames[row]
            if isinstance(frame, list):
                # Multi-line frame - join with newlines
                self.frame_editor.setText('\n'.join(frame))
            else:
                self.frame_editor.setText(frame)
            self.frame_editor.blockSignals(False)
            
    def on_editor_changed(self):
        """Auto-save editor content to current frame"""
        row = self.frames_list.currentRow()
        if 0 <= row < len(self.frames):
            text = self.frame_editor.toPlainText()
            # Store as list of lines for multi-line support
            self.frames[row] = text.split('\n') if '\n' in text else text
            
    def update_current_frame(self):
        """Explicitly update current frame"""
        row = self.frames_list.currentRow()
        if 0 <= row < len(self.frames):
            text = self.frame_editor.toPlainText()
            self.frames[row] = text.split('\n') if '\n' in text else text
            self.status_label.setText(f"Frame {row + 1} updated")
            
    def save_animation(self):
        """Save animation to file"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Animation", "", "JSON Files (*.json)"
        )
        if filename:
            data = {
                "frames": self.frames,
                "delay": self.frame_delay
            }
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            self.status_label.setText(f"Saved to {filename}")
            
    def load_animation(self):
        """Load animation from file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Animation", "", "JSON Files (*.json)"
        )
        if filename:
            with open(filename, 'r') as f:
                data = json.load(f)
            self.frames = data.get("frames", [])
            self.frame_delay = data.get("delay", 0.5)
            self.delay_spin.setValue(self.frame_delay)
            
            self.frames_list.clear()
            for i in range(len(self.frames)):
                self.frames_list.addItem(f"Frame {i+1}")
            
            if self.frames:
                self.frames_list.setCurrentRow(0)
                
            self.status_label.setText(f"Loaded {len(self.frames)} frames")
    
    def save_config(self):
        """Save current animation settings to config file"""
        if "animations" not in self.config:
            self.config["animations"] = {}
        
        self.config["animations"][self.current_animation] = {
            "skip_frames": self.skip_frames,
            "frame_delay": self.frame_delay
        }
        
        save_animation_config(self.config)
        self.status_label.setText(f"Settings saved for {self.current_animation}: skip={self.skip_frames}, delay={self.frame_delay}s")
            
    def play_animation(self):
        """Play the animation in Valorant chat"""
        if not self.frames:
            QMessageBox.warning(self, "No Frames", "Add some frames first!")
            return
            
        self.is_playing = True
        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Playing... Switch to Valorant now! (3 seconds)")
        
        # Give user time to switch to Valorant
        QTimer.singleShot(3000, self.start_playback)
        
    def start_playback(self):
        """Start the actual playback"""
        def play_thread():
            # Get frames to play based on skip setting
            frames_to_play = list(self.frames[::self.skip_frames])
            
            # Always include the last frame if not already included
            if self.frames and frames_to_play[-1] is not self.frames[-1]:
                frames_to_play.append(self.frames[-1])
            
            for i, frame in enumerate(frames_to_play):
                if not self.is_playing:
                    break
                
                # Each frame is a list of 26-char lines
                # Format with space after every 26 chars for Valorant
                if isinstance(frame, list):
                    formatted = format_frame_for_valorant(frame)
                    if formatted:
                        self.type_line_in_chat(formatted)
                else:
                    # Single line frame - add spaces every 26 chars
                    if frame.strip():
                        result = ""
                        for j, char in enumerate(frame):
                            result += char
                            if (j + 1) % 26 == 0:
                                result += " "
                        self.type_line_in_chat(result.rstrip())
                
                self.signals.frame_played.emit(i + 1)
                    
                if i < len(frames_to_play) - 1 and self.is_playing:
                    time.sleep(self.frame_delay)
                    
            self.signals.animation_complete.emit()
            
        threading.Thread(target=play_thread, daemon=True).start()
        
    def type_line_in_chat(self, line):
        """Paste a line in Valorant all chat using clipboard"""
        # Copy to clipboard
        pyperclip.copy(line)
        time.sleep(0.01)
        
        # Press Shift+Enter to open all chat
        self.keyboard_controller.press(keyboard.Key.shift)
        time.sleep(0.01)
        self.keyboard_controller.press(keyboard.Key.enter)
        time.sleep(0.01)
        self.keyboard_controller.release(keyboard.Key.enter)
        time.sleep(0.01)
        self.keyboard_controller.release(keyboard.Key.shift)
        time.sleep(0.02)
        
        # Paste with Ctrl+V
        self.keyboard_controller.press(keyboard.Key.ctrl)
        self.keyboard_controller.press('v')
        self.keyboard_controller.release('v')
        self.keyboard_controller.release(keyboard.Key.ctrl)
        time.sleep(0.01)
        
        # Press Enter to send
        self.keyboard_controller.press(keyboard.Key.enter)
        self.keyboard_controller.release(keyboard.Key.enter)
        
    def on_frame_played(self, frame_num):
        """Update UI when frame is played"""
        base_frames = list(self.frames[::self.skip_frames])
        # Account for possibly added last frame
        if self.frames and base_frames[-1] is not self.frames[-1]:
            total = len(base_frames) + 1
        else:
            total = len(base_frames)
        self.status_label.setText(f"Playing frame {frame_num}/{total}")
        
    def on_animation_complete(self):
        """Animation finished"""
        self.is_playing = False
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Animation complete!")
        
    def stop_animation(self):
        """Stop the animation"""
        self.is_playing = False
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Animation stopped")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = AnimationPlayer()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
