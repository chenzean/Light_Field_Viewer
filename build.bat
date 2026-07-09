@echo off
chcp 65001 >nul
echo ========================================
echo Light Field Viewer V1 - Build exe
echo ========================================

set PYTHON_EXE=D:\Anaconda3\envs\LFVFI\python.exe

"%PYTHON_EXE%" -m pip install pyinstaller PyQt5

"%PYTHON_EXE%" -m PyInstaller --clean --noconfirm LightFieldViewer.spec

echo.
echo Done! exe: dist\LightFieldViewer.exe
pause
