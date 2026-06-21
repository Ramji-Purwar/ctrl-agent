"""
Manage Windows shortcuts for ctrl-agent.

Usage:
    python startup.py enable      Add to Startup (runs on boot)
    python startup.py disable     Remove from Startup
    python startup.py register    Add to Start Menu (Windows Search)
    python startup.py unregister  Remove from Start Menu
    python startup.py status      Show current state
"""

import os
import sys
from pathlib import Path


def _get_exe_path() -> str:
    """Return the path to the executable or the dev-mode launch script."""
    # If running as a PyInstaller bundle, use the .exe path
    if getattr(sys, "frozen", False):
        return sys.executable

    # If the built executable exists, prefer it
    compiled_exe = Path(__file__).resolve().parent / "dist" / "ctrl-agent.exe"
    if compiled_exe.exists():
        return str(compiled_exe)

    # Dev mode: point to a .vbs launcher that runs pythonw
    vbs = Path(__file__).resolve().parent / "start_agent.vbs"
    if vbs.exists():
        return str(vbs)

    # Fallback: the python script itself
    return str(Path(__file__).resolve().parent / "run_chat.py")


def _startup_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _start_menu_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def _create_shortcut(shortcut_path: Path, target: str):
    """Create a Windows shortcut (.lnk) using PowerShell COM."""
    ps_script = f"""
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut('{shortcut_path}')
$sc.TargetPath = '{target}'
$sc.WorkingDirectory = '{Path(target).parent}'
$sc.Description = 'ctrl-agent personal assistant'
$sc.Save()
"""
    import subprocess
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  Error: {result.stderr.strip()}")
        return False
    return True


def enable():
    """Add ctrl-agent to Windows Startup."""
    target = _get_exe_path()
    shortcut = _startup_dir() / "ctrl-agent.lnk"
    if _create_shortcut(shortcut, target):
        print(f"  ✓ Startup shortcut updated: {shortcut}")
        print(f"    Target: {target}")


def disable():
    """Remove ctrl-agent from Windows Startup."""
    shortcut = _startup_dir() / "ctrl-agent.lnk"
    if shortcut.exists():
        shortcut.unlink()
        print("  ✓ Startup shortcut removed.")
    else:
        print("  Not in Startup.")


def register():
    """Add ctrl-agent to the Start Menu for Windows Search indexing."""
    target = _get_exe_path()
    shortcut = _start_menu_dir() / "ctrl-agent.lnk"
    if _create_shortcut(shortcut, target):
        print(f"  ✓ Start Menu shortcut updated: {shortcut}")
        print(f"    Target: {target}")
        print("  You can now find 'ctrl-agent' in Windows Search.")


def unregister():
    """Remove ctrl-agent from the Start Menu."""
    shortcut = _start_menu_dir() / "ctrl-agent.lnk"
    if shortcut.exists():
        shortcut.unlink()
        print("  ✓ Start Menu shortcut removed.")
    else:
        print("  Not in Start Menu.")


def status():
    """Show the current state of shortcuts."""
    startup_lnk = _startup_dir() / "ctrl-agent.lnk"
    menu_lnk    = _start_menu_dir() / "ctrl-agent.lnk"

    print(f"  Startup:    {'✓ enabled' if startup_lnk.exists() else '✗ disabled'}")
    print(f"  Start Menu: {'✓ registered' if menu_lnk.exists() else '✗ not registered'}")
    print(f"  Exe/Script: {_get_exe_path()}")


def main():
    commands = {
        "enable":     enable,
        "disable":    disable,
        "register":   register,
        "unregister": unregister,
        "status":     status,
    }

    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(__doc__)
        return

    commands[sys.argv[1]]()


if __name__ == "__main__":
    main()
