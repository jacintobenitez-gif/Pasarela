@echo off
echo Iniciando Listener en modo SPECIFIC (canales específicos)...
echo Usando canales: 1727126726,3070669722,1839677922
cd /d "C:\Pasarela\services"
set PYTHONPATH=%CD%\src
python .\src\listener\listener.py -specific 1727126726,3070669722,1839677922
pause