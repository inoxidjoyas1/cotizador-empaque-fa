@echo off
REM ====================================================================
REM  Refresca los precios de empaque (lineas F y A) desde Aspel SAE y
REM  los sube a GitHub para que el cotizador en la nube se actualice.
REM
REM  Lo corre el Programador de tareas de Windows (cada 15 dias) y
REM  tambien puedes hacer doble clic aqui cuando cambies precios.
REM
REM  Si "python" no se reconoce, cambia la palabra python de abajo por la
REM  ruta completa a tu python.exe (ej: C:\Python313\python.exe).
REM ====================================================================
cd /d "%~dp0"
python refrescar_precios.py
echo.
echo Listo. Puedes cerrar esta ventana.
REM Si lo corres a mano y quieres ver el resultado, quita el REM de la linea de abajo:
REM pause
