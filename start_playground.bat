@echo off
title Aether Playground
cd /d "%~dp0"
echo === Aether Playground ===
echo Working dir: %cd%
echo.

REM Try the Python launcher first (most reliable on Windows), then fall back.
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYCMD=py -3"
    goto :run
)
where python >nul 2>&1
if %errorlevel%==0 (
    set "PYCMD=python"
    goto :run
)
where python3 >nul 2>&1
if %errorlevel%==0 (
    set "PYCMD=python3"
    goto :run
)
echo No Python interpreter found on PATH. Install Python 3.10+ and rerun.
pause
exit /b 1

:run
echo Using interpreter: %PYCMD%
%PYCMD% --version
echo.
echo Starting server at http://localhost:8080
echo Press Ctrl+C in this window to stop.
echo.
%PYCMD% -m playground.backend.app --port 8080
echo.
echo Server exited.
pause
