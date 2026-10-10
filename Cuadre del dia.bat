@echo off
set "PYTHONW=C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
if not exist "%PYTHONW%" (
  start "Auto Cuadre - Error" cmd /k "echo No se encontro el entorno de Auto Cuadre. Abra el proyecto desde Codex."
  exit /b 1
)
start "" "%PYTHONW%" "%~dp0app_cuadre_dia.py"
