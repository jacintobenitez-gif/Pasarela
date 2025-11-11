@echo off
echo Iniciando Visor Web de Pasarela...
cd /d "C:\Pasarela\services"
set PYTHONPATH=%CD%\src
python .\src\bbdd\visor.py
pause





