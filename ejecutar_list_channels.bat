@echo off
echo ========================================
echo Listador de Canales de Telegram
echo ========================================
echo.
echo Este script lista todos los canales disponibles
echo y genera el archivo de configuracion channels.json
echo.
cd /d "C:\Pasarela\services"
set PYTHONPATH=%CD%\src
python .\src\listener\list_channels.py
pause



