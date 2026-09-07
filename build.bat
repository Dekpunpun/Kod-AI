@echo off
REM Build KodAI.exe. Run this ON WINDOWS - PyInstaller cannot
REM cross-compile, so a Mac cannot produce a .exe no matter what you pass it.
REM
REM Needs Python 3.10+ from python.org, "Add python.exe to PATH" ticked.

setlocal
cd /d "%~dp0"

echo === installing dependencies ===
py -m pip install --upgrade pip
py -m pip install -r requirements.txt || goto :failed

echo.
echo === generating the icon ===
py rpg\make_icon.py || goto :failed

echo.
echo === building ===
py -m PyInstaller --noconfirm --clean KodAI.spec || goto :failed

echo.
echo === checking the build actually runs ===
dist\KodAI\KodAI.exe --selftest || goto :failed

echo.
echo ============================================================
echo  Done.  dist\KodAI\KodAI.exe
echo  Ship the whole dist\KodAI folder, not just the exe.
echo ============================================================
pause
exit /b 0

:failed
echo.
echo BUILD FAILED - see the error above.
pause
exit /b 1

