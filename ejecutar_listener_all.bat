@echo off
echo Iniciando Listener en modo ALL (todos los canales)...
cd /d "C:\Pasarela\services"
set PYTHONPATH=%CD%\src
python .\src\listener\listener.py -all
pause