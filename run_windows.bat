@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 main.py
) else (
  python main.py
)
if errorlevel 1 (
  echo.
  echo Python or Tkinter could not run. Check your Python installation.
  pause
)