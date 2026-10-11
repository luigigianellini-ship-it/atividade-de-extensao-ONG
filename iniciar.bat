@echo off
chcp 65001 >nul
echo =====================================================================
echo   🌱 Iniciando Landing Page da ONG / Projeto Social
echo =====================================================================
echo.

set PYTHON_CMD=

:: 1. Tenta python padrão do PATH
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    goto RUN
)

:: 2. Tenta py launcher
py --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py
    goto RUN
)

:: 3. Tenta caminhos comuns no Windows
if exist "C:\msys64\ucrt64\bin\python.exe" (
    set PYTHON_CMD="C:\msys64\ucrt64\bin\python.exe"
    goto RUN
)

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%D\python.exe" (
        set PYTHON_CMD="%%D\python.exe"
        goto RUN
    )
)

for /d %%D in ("C:\Program Files\Python*") do (
    if exist "%%D\python.exe" (
        set PYTHON_CMD="%%D\python.exe"
        goto RUN
    )
)

:RUN
if "%PYTHON_CMD%"=="" (
    echo [ERRO] Python não foi encontrado no sistema!
    echo Instale o Python em https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Usando interpretador: %PYTHON_CMD%
echo.
echo Iniciando servidor em http://localhost:8000 ...
echo Pressione Ctrl+C na janela para encerrar.
echo.

start "" "http://localhost:8000"

%PYTHON_CMD% server.py
pause
