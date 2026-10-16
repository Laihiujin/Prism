Option Explicit
Dim shell, fs, root, command, arg
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(fs.GetParentFolderName(WScript.ScriptFullName))
shell.CurrentDirectory = root
command = "powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File " & Quote(root & "\scripts\start-background.ps1")
For Each arg In WScript.Arguments
  command = command & " " & Quote(arg)
Next
shell.Run command, 0, False

Function Quote(value)
  Quote = Chr(34) & Replace(value, Chr(34), Chr(34) & Chr(34)) & Chr(34)
End Function
