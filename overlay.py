"""
ValTime - Valorant Communication Overlay
A transparent overlay that displays a communication menu on top of your game.

Requirements:
    pip install pyqt6 pynput

Usage:
    python overlay.py

Controls:
    .            - Toggle overlay visibility (works in-game)
    1-6          - Select option (when overlay is visible, works in-game)
    Escape       - Hide overlay
"""

import sys
import ctypes
from ctypes import wintypes
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                              QLabel, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont
from pynput import keyboard

# Windows blur effect constants
class ACCENT_STATE:
    DISABLED = 0
    ENABLE_GRADIENT = 1
    ENABLE_TRANSPARENTGRADIENT = 2
    ENABLE_BLURBEHIND = 3
    ENABLE_ACRYLICBLURBEHIND = 4  # Windows 10 1803+

class WINDOWCOMPOSITIONATTRIB:
    WCA_ACCENT_POLICY = 19

class ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]

class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attrib", ctypes.c_int),
        ("pvData", ctypes.c_void_p),
        ("cbData", ctypes.c_size_t),
    ]

def enable_blur(hwnd):
    """Enable Windows blur effect on a window"""
    try:
        user32 = ctypes.windll.user32
        SetWindowCompositionAttribute = user32.SetWindowCompositionAttribute
        SetWindowCompositionAttribute.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
        SetWindowCompositionAttribute.restype = ctypes.c_int
        
        # Use standard blur behind (clearer, like Windows 7 Aero)
        accent = ACCENT_POLICY()
        accent.AccentState = ACCENT_STATE.ENABLE_BLURBEHIND
        accent.AccentFlags = 0
        accent.GradientColor = 0
        
        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attrib = WINDOWCOMPOSITIONATTRIB.WCA_ACCENT_POLICY
        data.pvData = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.cbData = ctypes.sizeof(accent)
        
        SetWindowCompositionAttribute(hwnd, ctypes.pointer(data))
    except Exception as e:
        print(f"Could not enable blur effect: {e}")

# Signal bridge to communicate between pynput thread and Qt
class SignalBridge(QObject):
    toggle_signal = pyqtSignal()
    select_signal = pyqtSignal(int)
    hide_signal = pyqtSignal()
    back_signal = pyqtSignal()

class CommunicationMenu(QWidget):
    def __init__(self):
        super().__init__()
        # Main menu options (display order)
        self.main_options = [
            "Rocket League",
            "Animations",
            "Combat",
            "Tactics", 
            "Social",
            "Strategy"
        ]
        
        # Built-in Valorant menus (these use in-game voice lines)
        self.builtin_menus = ["Combat", "Tactics", "Social", "Strategy"]
        
        # Animation menus (trigger animation player)
        self.animation_menus = ["Animations"]
        
        # Mapping of menu names to their actual Valorant key numbers
        self.valorant_menu_keys = {
            "Combat": 1,
            "Tactics": 2,
            "Social": 3,
            "Strategy": 4
        }
        
        # Submenus
        self.submenus = {
            "Combat": [
                "Need Support",
                "Caution here!",
                "Need Healing!",
                "On My Way",
                "Ultimate Status"
            ],
            "Tactics": [
                "I'll Take Point",
                "Let's rush them!",
                "Be Quiet",
                "Fall Back!",
                "Play For Picks"
            ],
            "Social": [
                "Thanks",
                "Commend",
                "Yes",
                "No",
                "Sorry",
                "Hello"
            ],
            "Strategy": [
                "Going A",
                "Going B",
                "Going C",
                "Going Mid"
            ],
            "Rocket League": [
                "What a save!",
                "Nice shot!",
                "Thanks!",
                "Well played!"
            ],
            "Animations": [
                "Truck"
            ]
        }
        
        # Keyboard controller for typing in chat
        self.keyboard_controller = keyboard.Controller()
        
        self.current_menu = "main"  # "main" or submenu name
        self.main_menu_index = 0  # Track which main menu was selected (1-based)
        self.selection_pending = False  # Prevent multiple selections
        self.options = self.main_options
        self.option_labels = []
        self.signal_bridge = SignalBridge()
        self.init_ui()
        self.setup_global_hotkeys()
        
    def init_ui(self):
        # Window flags for overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Main container - transparent background (blur handled by Windows)
        self.container = QFrame(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet("""
            #container {
                background-color: transparent;
                border: 1px solid rgba(255, 255, 255, 200);
                border-radius: 3px;
            }
        """)
        
        # Layouts
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)
        
        # Header
        self.header = self.create_header()
        self.container_layout.addWidget(self.header)
        
        # Options container
        self.options_frame = QFrame()
        self.options_frame.setStyleSheet("background: transparent;")
        self.options_layout = QVBoxLayout(self.options_frame)
        self.options_layout.setContentsMargins(0, 0, 0, 0)
        self.options_layout.setSpacing(0)
        
        self.rebuild_options()
            
        self.container_layout.addWidget(self.options_frame)
        
        # Add stretch to push footer to bottom
        self.container_layout.addStretch()
        
        # Footer
        self.footer = self.create_footer()
        self.container_layout.addWidget(self.footer)
        
        main_layout.addWidget(self.container)
        
        # Position window
        self.position_window()
        
        # Connect signals
        self.signal_bridge.toggle_signal.connect(self.toggle_visibility)
        self.signal_bridge.select_signal.connect(self.select_option)
        self.signal_bridge.hide_signal.connect(self.hide)
        self.signal_bridge.back_signal.connect(self.handle_back)
        
        # Initially hidden
        self.hide()
        
    def create_header(self):
        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet("background-color: rgba(255, 255, 255, 220); border-bottom: 1px solid rgba(255, 255, 255, 255); border-top-left-radius: 3px; border-top-right-radius: 3px;")
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)
        
        # Communication icon
        icon_label = QLabel("📡")
        icon_label.setStyleSheet("font-size: 18px; background: transparent;")
        
        # Title - exact Valorant style
        self.header_title = QLabel("COMMUNICATION")
        self.header_title.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        self.header_title.setStyleSheet("color: rgba(0, 0, 0, 0.85); letter-spacing: 1px; background: transparent;")
        
        layout.addWidget(icon_label)
        layout.addWidget(self.header_title)
        layout.addStretch()
        
        return header
    
    def create_option(self, num, text):
        option = QFrame()
        option.setObjectName(f"option_{num}")
        option.setFixedHeight(32)
        option.setStyleSheet("""
            QFrame {
                background: transparent;
            }
            QFrame:hover {
                background-color: rgba(255, 255, 255, 0.06);
            }
        """)
        option.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(option)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(6)
        
        # Key number with colon
        key_label = QLabel(f"{num}:")
        key_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        key_label.setStyleSheet("color: rgba(255, 255, 255, 1.0);")
        key_label.setFixedWidth(24)
        
        # Option text
        text_label = QLabel(text)
        text_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        text_label.setStyleSheet("color: rgba(255, 255, 255, 1.0);")
        text_label.setObjectName(f"text_{num}")
        
        self.option_labels.append((option, text_label, num))
        
        layout.addWidget(key_label)
        layout.addWidget(text_label)
        layout.addStretch()
        
        # Click handler
        option.mousePressEvent = lambda e, n=num: self.select_option(n)
        
        return option
    
    def create_footer(self):
        footer = QFrame()
        footer.setFixedHeight(26)
        footer.setStyleSheet("background: transparent; border-top: 1px solid rgba(255, 255, 255, 8);")
        footer.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(5)
        
        # Esc key indicator
        esc_label = QLabel("Esc")
        esc_label.setFont(QFont("Segoe UI", 10))
        esc_label.setStyleSheet("color: rgba(255, 255, 255, 0.35);")
        
        # Close/Back text
        self.footer_text = QLabel("Close")
        self.footer_text.setFont(QFont("Segoe UI", 11))
        self.footer_text.setStyleSheet("color: rgba(255, 255, 255, 0.5);")
        
        layout.addWidget(esc_label)
        layout.addWidget(self.footer_text)
        layout.addStretch()
        
        footer.mousePressEvent = lambda e: self.handle_back()
        
        return footer
    
    def position_window(self):
        screen = QApplication.primaryScreen().geometry()
        # Original size
        self.setFixedSize(296, 402)
        x = screen.width() - 296
        y = screen.height() - 442
        self.move(x, y)
    
    def setup_global_hotkeys(self):
        """Setup global hotkeys using pynput - works even when game is focused"""
        def on_press(key):
            try:
                # Period key to toggle
                if hasattr(key, 'char') and key.char == '.':
                    self.signal_bridge.toggle_signal.emit()
                
                # Number keys 1-6 when visible
                if self.isVisible() and hasattr(key, 'char') and key.char in '123456':
                    self.signal_bridge.select_signal.emit(int(key.char))
                    
            except AttributeError:
                pass
            
            # Escape to go back or hide
            if key == keyboard.Key.esc and self.isVisible():
                self.signal_bridge.back_signal.emit()
        
        # Start listener in background thread
        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.daemon = True
        self.listener.start()
    
    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            # Reset to main menu when showing
            self.current_menu = "main"
            self.options = self.main_options
            self.selection_pending = False  # Reset selection lock
            self.rebuild_options()
            self.update_header_title()
            self.show()
            # Enable blur effect when shown
            hwnd = int(self.winId())
            enable_blur(hwnd)
    
    def rebuild_options(self):
        """Clear and rebuild the options list"""
        # Clear existing options
        self.option_labels = []
        while self.options_layout.count():
            child = self.options_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Add new options
        for i, option_text in enumerate(self.options, 1):
            option = self.create_option(i, option_text)
            self.options_layout.addWidget(option)
    
    def update_header_title(self):
        """Update the header title based on current menu"""
        if self.current_menu == "main":
            self.header_title.setText("COMMUNICATION")
            self.footer_text.setText("Close")
        else:
            self.header_title.setText(self.current_menu.upper())
            self.footer_text.setText("Back")
    
    def select_option(self, num):
        if not self.isVisible():
            return
        
        if self.selection_pending:
            return  # Already processing a selection
        
        if num > len(self.options):
            return
            
        selected = self.options[num-1]
        print(f"Selected: {selected}")
        
        if self.current_menu == "main":
            # Navigate to submenu
            if selected in self.submenus:
                self.main_menu_index = num  # Store which main menu (1-based)
                self.current_menu = selected
                self.options = self.submenus[selected]
                self.rebuild_options()
                self.update_header_title()
        else:
            # In submenu - execute action
            self.selection_pending = True  # Block further selections
            if self.current_menu in self.builtin_menus:
                # Built-in menu - trigger Valorant's native UI
                valorant_main_key = self.valorant_menu_keys[self.current_menu]
                self.trigger_valorant_voiceline(valorant_main_key, num)
                # Keep overlay visible longer to hide official UI
                QTimer.singleShot(500, self.hide)
            elif self.current_menu in self.animation_menus:
                # Animation menu - trigger animation
                self.trigger_animation(selected)
                QTimer.singleShot(50, self.hide)
            else:
                # Custom menu - type message in Valorant chat
                self.type_in_chat(selected)
                # Hide quickly after custom selection
                QTimer.singleShot(50, self.hide)
    
    def trigger_valorant_voiceline(self, main_num, sub_num):
        """Trigger Valorant's native communication wheel"""
        import time
        
        def do_voiceline():
            # Press backslash to open communication wheel
            self.keyboard_controller.press('\\')
            self.keyboard_controller.release('\\')
            time.sleep(0.08)
            
            # Press main menu number
            self.keyboard_controller.press(str(main_num))
            self.keyboard_controller.release(str(main_num))
            time.sleep(0.08)
            
            # Press submenu number
            self.keyboard_controller.press(str(sub_num))
            self.keyboard_controller.release(str(sub_num))
        
        import threading
        threading.Timer(0.05, do_voiceline).start()
    
    def trigger_animation(self, animation_name):
        """Trigger an ASCII animation in Valorant chat"""
        import time
        import pyperclip
        import json
        
        def load_animation_config():
            """Load animation configuration from file"""
            try:
                with open("animation_config.json", 'r') as f:
                    return json.load(f)
            except FileNotFoundError:
                return {"animations": {"Truck": {"skip_frames": 5, "frame_delay": 0.5}}}
        
        def play_animation():
            if animation_name == "Truck":
                # Import the truck animation
                from animation_player import TRUCK_ANIMATION, format_frame_for_valorant
                
                # Load settings from config
                config = load_animation_config()
                anim_config = config.get("animations", {}).get(animation_name, {})
                skip = anim_config.get("skip_frames", 5)
                frame_delay = anim_config.get("frame_delay", 0.5)
                
                frames = TRUCK_ANIMATION
                
                # Get frames to play
                frames_to_play = list(frames[::skip])
                # Always include last frame
                if frames and frames_to_play[-1] is not frames[-1]:
                    frames_to_play.append(frames[-1])
                
                for frame in frames_to_play:
                    formatted = format_frame_for_valorant(frame)
                    if formatted:
                        # Copy to clipboard
                        pyperclip.copy(formatted)
                        time.sleep(0.01)
                        
                        # Open all chat
                        self.keyboard_controller.press(keyboard.Key.shift)
                        time.sleep(0.01)
                        self.keyboard_controller.press(keyboard.Key.enter)
                        time.sleep(0.01)
                        self.keyboard_controller.release(keyboard.Key.enter)
                        time.sleep(0.01)
                        self.keyboard_controller.release(keyboard.Key.shift)
                        time.sleep(0.02)
                        
                        # Paste
                        self.keyboard_controller.press(keyboard.Key.ctrl)
                        self.keyboard_controller.press('v')
                        self.keyboard_controller.release('v')
                        self.keyboard_controller.release(keyboard.Key.ctrl)
                        time.sleep(0.01)
                        
                        # Send
                        self.keyboard_controller.press(keyboard.Key.enter)
                        self.keyboard_controller.release(keyboard.Key.enter)
                        
                        time.sleep(frame_delay)
        
        import threading
        threading.Timer(0.1, play_animation).start()
    
    def type_in_chat(self, message):
        """Type a message in Valorant all chat using clipboard paste"""
        import time
        import pyperclip
        
        def do_type():
            # Copy message to clipboard
            pyperclip.copy(message)
            
            # Press Shift+Enter to open all chat - hold shift while pressing enter
            self.keyboard_controller.press(keyboard.Key.shift)
            time.sleep(0.01)  # Small delay to ensure shift is registered
            self.keyboard_controller.press(keyboard.Key.enter)
            time.sleep(0.01)
            self.keyboard_controller.release(keyboard.Key.enter)
            time.sleep(0.01)
            self.keyboard_controller.release(keyboard.Key.shift)
            time.sleep(0.03)
            
            # Paste the message with Ctrl+V
            self.keyboard_controller.press(keyboard.Key.ctrl)
            self.keyboard_controller.press('v')
            self.keyboard_controller.release('v')
            self.keyboard_controller.release(keyboard.Key.ctrl)
            time.sleep(0.02)
            
            # Press Enter to send
            self.keyboard_controller.press(keyboard.Key.enter)
            self.keyboard_controller.release(keyboard.Key.enter)
        
        # Run immediately in a separate thread
        import threading
        threading.Timer(0.05, do_type).start()
    
    def go_back(self):
        """Go back to main menu"""
        if self.current_menu != "main":
            self.current_menu = "main"
            self.options = self.main_options
            self.rebuild_options()
            self.update_header_title()
    
    def handle_back(self):
        """Handle ESC key - go back or hide"""
        if self.current_menu != "main":
            self.go_back()
        else:
            self.hide()
    
    def reset_option(self, option, text_label):
        option.setStyleSheet("""
            QFrame {
                background: transparent;
            }
            QFrame:hover {
                background-color: rgba(255, 255, 255, 0.06);
            }
        """)
        text_label.setStyleSheet("color: rgba(255, 255, 255, 1.0);")
    
    def closeEvent(self, event):
        # Stop the keyboard listener when closing
        if hasattr(self, 'listener'):
            self.listener.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    
    overlay = CommunicationMenu()
    
    print("=" * 50)
    print("  ValTime Communication Overlay")
    print("=" * 50)
    print("\n  Controls (work while in-game):")
    print("  • .  (period)   - Toggle overlay")
    print("  • 1-6           - Select option")
    print("  • Escape        - Hide overlay")
    print("\n  Press . to show the menu!")
    print("=" * 50)
    
    # Show initially for demo and enable blur
    overlay.show()
    hwnd = int(overlay.winId())
    enable_blur(hwnd)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
