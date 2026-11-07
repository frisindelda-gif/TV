@echo off
rem Instala o FM27 Scouting Intelligence (uma vez). Requer Python 3.12+ e Node.js 20+.
setlocal
cd /d "%~dp0"

where py >nul 2>nul || (echo Python nao encontrado. Instale o Python 3.12+ de python.org e volte a correr. & pause & exit /b 1)
py -3 -c "import sys; sys.exit(sys.version_info < (3, 12))" || (echo E preciso Python 3.12 ou mais recente. & pause & exit /b 1)
where npm >nul 2>nul || (echo Node.js nao encontrado. Instale o Node.js 20+ de nodejs.org e volte a correr. & pause & exit /b 1)

echo [1/3] Ambiente Python...
if not exist backend\.venv\Scripts\python.exe (py -3 -m venv backend\.venv || goto :erro)
backend\.venv\Scripts\python -m pip install --quiet --upgrade pip || goto :erro
backend\.venv\Scripts\python -m pip install --quiet -e "backend[save]" || goto :erro

echo [2/3] Dependencias da interface...
pushd frontend
call npm ci --no-audit --no-fund || (popd & goto :erro)

echo [3/3] Compilar a interface...
call npm run build || (popd & goto :erro)
popd

echo.
echo Instalacao concluida. Abra "Iniciar FM27 Scouting.cmd".
pause
exit /b 0

:erro
echo.
echo Ocorreu um erro na instalacao (ver mensagens acima).
pause
exit /b 1
