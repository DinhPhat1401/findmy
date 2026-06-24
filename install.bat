@echo off
echo Installing Find My Laptop to Startup...
set "startup_folder=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "vbs_file=C:\Users\jicam\Downloads\PythonPrj\FindMyLaptop\startup.vbs"
copy "%vbs_file%" "%startup_folder%"
echo Installation complete! The app will start automatically when you log in.
pause
