@echo off
setlocal

set RUN_ARGS=
set REMAINING_ARGS=
set IS_DEBUG=0

pushd "%~dp0"

:parse
if "%~1"=="" goto run
if /I "%~1"=="debug" (
    set RUN_ARGS=--debug
    set IS_DEBUG=1
) else (
    set REMAINING_ARGS=%REMAINING_ARGS% "%~1"
)
shift
goto parse

:run
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m src.main %RUN_ARGS% %REMAINING_ARGS%
) else (
    where uv >nul 2>nul
    if %errorlevel%==0 (
        uv run python -m src.main %RUN_ARGS% %REMAINING_ARGS%
    ) else (
        echo [ERROR] .venv is missing, and uv not found. Please install uv and run: uv sync
        exit /b 1
    )
)

set EXIT_CODE=%errorlevel%
if %EXIT_CODE% neq 0 pause
if %IS_DEBUG% neq 0 pause
popd
endlocal & exit /b %EXIT_CODE%
