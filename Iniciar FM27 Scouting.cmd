@echo off
rem Arranca a app local e abre-a no browser. Fechar esta janela termina a app.
setlocal
cd /d "%~dp0"
if not exist backend\.venv\Scripts\fm27si.exe (echo Corra primeiro instalar.cmd & pause & exit /b 1)
if not exist frontend\dist\index.html (echo Interface nao compilada. Corra instalar.cmd & pause & exit /b 1)

start "" /b cmd /c "timeout /t 3 /nobreak >nul & start "" http://127.0.0.1:8727/"
echo FM27 Scouting Intelligence em http://127.0.0.1:8727/  (feche esta janela para terminar)
backend\.venv\Scripts\fm27si.exe serve --port 8727
