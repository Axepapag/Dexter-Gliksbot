@echo off
REM =====================================================================
REM Dexter Cockpit Launcher
REM
REM This script launches the WPF Cockpit UI for Dexter-Gliksbot
REM Prerequisites:
REM   - .NET 8.0 SDK installed
REM   - Backend server running (python start.py --port 8765)
REM =====================================================================

echo.
echo ========================================
echo   Dexter Cockpit Launcher
echo ========================================
echo.

REM Check if .NET SDK is installed
where dotnet >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] .NET SDK not found!
    echo.
    echo Please install .NET 8.0 SDK:
    echo   https://dotnet.microsoft.com/download/dotnet/8.0
    echo.
    echo Or use: winget install Microsoft.DotNet.SDK.8
    echo.
    pause
    exit /b 1
)

REM Check .NET version
for /f "tokens=*" %%i in ('dotnet --version') do set DOTNET_VERSION=%%i
echo Detected .NET SDK: %DOTNET_VERSION%

REM Navigate to cockpit directory
cd /d "%~dp0cockpit\DexterCockpit"

if not exist "DexterCockpit.csproj" (
    echo [ERROR] Cockpit project not found!
    echo Expected: cockpit\DexterCockpit\DexterCockpit.csproj
    echo.
    pause
    exit /b 1
)

echo.
echo Restoring dependencies...
dotnet restore >nul 2>nul

echo.
echo ========================================
echo   Starting Dexter Cockpit...
echo ========================================
echo.
echo Make sure backend is running:
echo   python start.py --port 8765
echo.
echo Cockpit will connect to:
echo   http://localhost:8765
echo.
echo Press Ctrl+C to stop
echo.

REM Run the cockpit
dotnet run

echo.
echo Cockpit stopped.
pause
