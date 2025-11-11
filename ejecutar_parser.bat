@echo off
echo Iniciando Parser de Pasarela...
cd /d "C:\Pasarela\services"
set PYTHONPATH=%CD%\src
python .\src\parser\parseador_local.py
pause





