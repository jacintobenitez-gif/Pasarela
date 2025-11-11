@echo off
echo Iniciando Listener de Pasarela (modo PINNED por defecto)...
echo.
echo Opciones disponibles:
echo   %~n0 -all          (todos los canales)
echo   %~n0 -pinned       (solo canales fijados - por defecto)
echo   %~n0 -specific ID1,ID2,ID3  (canales específicos)
echo.
cd /d "C:\Pasarela\services"
set PYTHONPATH=%CD%\src
python .\src\listener\listener.py %*
pause

