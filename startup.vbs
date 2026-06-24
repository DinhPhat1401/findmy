Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d ""C:\Users\jicam\Downloads\PythonPrj\FindMyLaptop"" && .\venv\Scripts\pythonw.exe main.py", 0, False
