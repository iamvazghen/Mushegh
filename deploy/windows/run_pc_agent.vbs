' Mushegh PC-control executor — hidden launcher (no console window).
' Connects this laptop OUT to the 24/7 VPS brain's /control socket so Mushegh can run
' file/process/PowerShell/open-app/open-URL commands here. Started at logon by the
' MusheghPcAgent scheduled task. Window style 0 = hidden, so nothing flashes on screen.
' Call the venv Python DIRECTLY (not `uv run`) — no per-launch dependency resolution, so it starts
' reliably in the elevated scheduled-task context.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Mushegh"
sh.Run "cmd /c ""C:\Mushegh\.venv\Scripts\python.exe"" -m mushegh.edge.pc_agent", 0, False
