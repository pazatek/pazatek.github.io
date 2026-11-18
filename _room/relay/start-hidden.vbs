' Starts run.cmd with no window. A shortcut to this file in the Startup folder starts the relay at login.
CreateObject("WScript.Shell").Run """" & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\run.cmd""", 0, False
