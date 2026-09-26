@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title BillingPro

echo.
echo Starting BillingPro...
echo.

REM Default HTTP :8003 (stable). For HTTPS camera: set BILLINGPRO_HTTPS=1
if not defined BILLINGPRO_HTTPS set BILLINGPRO_HTTPS=0

REM Free leftover uvicorn on common ports (ignore errors)
for %%P in (8003 8443) do (
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P" ^| findstr LISTENING') do (
    echo Freeing port %%P PID %%A ...
    taskkill /PID %%A /F >nul 2>&1
  )
)

REM Try Python launcher, then python, then python3
where py >nul 2>&1
if %ERRORLEVEL%==0 (
    py -3 run.py
    goto :done
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
    python run.py
    goto :done
)

where python3 >nul 2>&1
if %ERRORLEVEL%==0 (
    python3 run.py
    goto :done
)

echo.
echo ============================================================
echo   ERROR: Python was not found on this computer.
echo ============================================================
echo.
echo Please install Python 3.9 or newer from:
echo   https://www.python.org/downloads/
echo.
echo On Windows, during installation check:
echo   [x] Add python.exe to PATH
echo.
echo Then double-click START_BILLINGPRO.bat again.
echo.
pause
exit /b 1

:done
if errorlevel 1 pause
endlocal
