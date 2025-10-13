@echo off
setlocal

set "SCRIPT=%~dp0Start-Dexter.ps1"
if not exist "%SCRIPT%" (
    echo [Launcher] Unable to locate Start-Dexter.ps1 next to this file.
    exit /b 1
)

set "SHELL="
for %%S in (pwsh.exe powershell.exe) do (
    if not defined SHELL (
        where %%S >nul 2>nul && set "SHELL=%%S"
    )
)

if not defined SHELL (
    echo [Launcher] Neither PowerShell nor PowerShell Core was found on PATH.
    exit /b 1
)

%SHELL% -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*

endlocal
