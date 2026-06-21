Set WshShell = CreateObject("WScript.Shell")
' Run ctrl-agent silently using pythonw (no console window)
Dim projectDir
projectDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = projectDir
WshShell.Run "pythonw run_chat.py", 0, False
