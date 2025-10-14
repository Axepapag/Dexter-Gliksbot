@echo off
REM =====================================================================
REM Dexter Full Stack Launcher
REM
REM This script launches both the backend server and WPF Cockpit UI
REM Prerequisites:
REM   - Python 3.10+ with dependencies installed (run install.py first)
REM   - .NET 8.0 SDK installed
REM   - Redis running (optional, for Celery workers)
REM =====================================================================

echo.
echo ========================================
echo   Dexter Full Stack Launcher
echo ========================================
echo.

REM Check Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found!
    echo Please install Python 3.10 or higher.
    pause
    exit /b 1
)

REM Check .NET SDK
where dotnet >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [WARNING] .NET SDK not found - Cockpit UI will not start
    echo Install: https://dotnet.microsoft.com/download/dotnet/8.0
    set SKIP_COCKPIT=1
)

echo Starting Dexter backend...
echo.

REM Start backend in new window
start "Dexter Backend" cmd /k "python start.py --port 8765"

echo Backend starting in separate window...
echo Waiting 5 seconds for backend to initialize...
timeout /t 5 /nobreak >nul

if not defined SKIP_COCKPIT (
    echo.
    echo Starting Cockpit UI...
    echo.
    
    REM Start cockpit in new window
    start "Dexter Cockpit" cmd /k "cd cockpit\DexterCockpit && dotnet restore >nul 2>nul && dotnet run"
    
    echo.
    echo ========================================
    echo   Dexter is Running!
    echo ========================================
    echo.
    echo Backend: http://localhost:8765
    echo Cockpit: WPF window should appear
    echo.
    echo Close windows to stop services.
) else (
    echo.
    echo ========================================
    echo   Dexter Backend is Running!
    echo ========================================
    echo.
    echo Backend: http://localhost:8765
    echo Cockpit: Not started (install .NET 8.0 SDK)
    echo.
    echo Close window to stop backend.
)

echo.
pause
