"""
Build ctrl-agent into a standalone Windows executable.

Usage:
    python build.py

Output:
    dist/ctrl-agent.exe
"""

import os
import subprocess
import sys


def main():
    # Use the venv python if available
    venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "Scripts", "python.exe")
    python = venv_python if os.path.isfile(venv_python) else sys.executable

    cmd = [
        python, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", "ctrl-agent",

        # Bundle pystray's win32 backends (PyInstaller misses them)
        "--collect-all", "pystray",

        # Bundle static assets
        "--add-data", "chat_ui;chat_ui",
        "--add-data", "widget;widget",
        "--add-data", "data;data",

        # Hidden imports that PyInstaller may miss
        "--hidden-import", "PIL",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "engineio.async_drivers.threading",

        "run_chat.py",
    ]

    print("Building ctrl-agent.exe ...")
    print(f"  Command: {' '.join(cmd)}\n")

    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n[OK] Build successful! -> dist/ctrl-agent.exe")
    else:
        print(f"\n[FAIL] Build failed with exit code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
