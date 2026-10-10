@echo off
cd /d "%~dp0"
set "PYTHONW=C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
if exist "%PYTHONW%" (
  start "" "%PYTHONW%" "%~dp0main.py"
  exit /b 0
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw "%~dp0main.py"
  exit /b 0
)
where pyw >nul 2>nul
if %errorlevel%==0 (
  start "" pyw "%~dp0main.py"
  exit /b 0
)
start "Auto Cuadre - Error" cmd /k "echo No se encontro Python. Instale Python 3 (con la opcion Add to PATH) y vuelva a abrir Auto Cuadre."
exit /b 1
