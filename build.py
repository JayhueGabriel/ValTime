# build.py - Build script for ValTime
import subprocess
import shutil
import os

# Change to the ValTime directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Build the overlay executable
subprocess.run([
    "pyinstaller",
    "--onefile",
    "--windowed",
    "--name", "ValTime",
    "--add-data", "animation_config.json;.",
    "--add-data", "animation_player.py;.",
    "--hidden-import", "pynput.keyboard._win32",
    "--hidden-import", "pynput.mouse._win32",
    "overlay.py"
], check=True)

print("\n" + "="*50)
print("Build complete!")
print("Executable is in: dist/ValTime.exe")
print("="*50)
print("\nTo share with friends, send them:")
print("  1. dist/ValTime.exe")
print("  2. animation_config.json (for animation settings)")
