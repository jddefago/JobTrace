' Launches start.bat with no visible window at all (not even a brief flash).
' This is what the desktop shortcut points to. Double-clicking start.bat
' directly still works too, it just shows a console window for a moment.
Set objFSO = CreateObject("Scripting.FileSystemObject")
scriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = scriptDir
objShell.Run """" & scriptDir & "\start.bat""", 0, False
