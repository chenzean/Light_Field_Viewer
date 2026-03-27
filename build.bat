@echo off
chcp 65001 >nul
echo ========================================
echo Light Field Viewer V1 - Build exe
echo ========================================

pip install pyinstaller

pyinstaller LightFieldViewer.spec

echo.
echo Done! exe: dist\LightFieldViewer.exe
pause
