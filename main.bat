@echo off
setlocal

set RUN_ARGS=
set REMAINING_ARGS=

:parse
if "%~1"=="" goto run
if /I "%~1"=="debug" (
    set RUN_ARGS=--debug
) else (
    set REMAINING_ARGS=%REMAINING_ARGS% "%~1"
)
shift
goto parse

:run
call .venv\Scripts\activate.bat
python -m src.main %RUN_ARGS% %REMAINING_ARGS%

endlocal
pause
