#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Dexter Full Stack Launcher (PowerShell)

.DESCRIPTION
    Launches both the backend server and WPF Cockpit UI
    
    Prerequisites:
      - Python 3.10+ with dependencies installed (run install.py first)
      - .NET 8.0 SDK installed
      - Redis running (optional, for Celery workers)

.PARAMETER Port
    Backend server port (default: 8765)

.PARAMETER SkipCockpit
    Skip launching the Cockpit UI

.EXAMPLE
    .\Launch-Dexter.ps1
    
.EXAMPLE
    .\Launch-Dexter.ps1 -Port 8080 -SkipCockpit
#>

param(
    [int]$Port = 8765,
    [switch]$SkipCockpit
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Dexter Full Stack Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
$pythonPath = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonPath) {
    Write-Host "[ERROR] Python not found!" -ForegroundColor Red
    Write-Host "Please install Python 3.10 or higher." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

$pythonVersion = & python --version
Write-Host "Detected: $pythonVersion" -ForegroundColor Green

# Check .NET SDK (optional for cockpit)
$dotnetPath = Get-Command dotnet -ErrorAction SilentlyContinue
if (-not $dotnetPath -and -not $SkipCockpit) {
    Write-Host "[WARNING] .NET SDK not found - Cockpit UI will not start" -ForegroundColor Yellow
    Write-Host "Install: https://dotnet.microsoft.com/download/dotnet/8.0" -ForegroundColor Yellow
    Write-Host ""
    $SkipCockpit = $true
}

# Start backend server
Write-Host ""
Write-Host "Starting Dexter backend server..." -ForegroundColor Cyan
Write-Host "Port: $Port" -ForegroundColor Gray
Write-Host ""

$backendJob = Start-Job -ScriptBlock {
    param($port)
    python start.py --port $port
} -ArgumentList $Port

Write-Host "Backend server started (Job ID: $($backendJob.Id))" -ForegroundColor Green
Write-Host "Waiting 5 seconds for backend to initialize..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# Check if backend is running
try {
    $response = Invoke-WebRequest -Uri "http://localhost:$Port/health" -TimeoutSec 2 -UseBasicParsing
    Write-Host "Backend health check: OK" -ForegroundColor Green
} catch {
    Write-Host "[WARNING] Backend health check failed - it may still be starting" -ForegroundColor Yellow
}

# Start cockpit if not skipped
if (-not $SkipCockpit) {
    Write-Host ""
    Write-Host "Starting Cockpit UI..." -ForegroundColor Cyan
    
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $cockpitDir = Join-Path $scriptDir "cockpit\DexterCockpit"
    
    if (Test-Path (Join-Path $cockpitDir "DexterCockpit.csproj")) {
        $cockpitJob = Start-Job -ScriptBlock {
            param($dir)
            Set-Location $dir
            dotnet restore | Out-Null
            dotnet run
        } -ArgumentList $cockpitDir
        
        Write-Host "Cockpit UI started (Job ID: $($cockpitJob.Id))" -ForegroundColor Green
        
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "  Dexter is Running!" -ForegroundColor Cyan
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Backend: http://localhost:$Port" -ForegroundColor White
        Write-Host "Cockpit: WPF window should appear" -ForegroundColor White
        Write-Host ""
        Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Yellow
        Write-Host ""
        
        # Monitor jobs
        try {
            while ($true) {
                Start-Sleep -Seconds 2
                
                if ($backendJob.State -eq "Failed" -or $backendJob.State -eq "Stopped") {
                    Write-Host "[ERROR] Backend stopped unexpectedly" -ForegroundColor Red
                    break
                }
                
                if ($cockpitJob.State -eq "Failed" -or $cockpitJob.State -eq "Stopped") {
                    Write-Host "[WARNING] Cockpit stopped" -ForegroundColor Yellow
                }
            }
        } finally {
            Write-Host ""
            Write-Host "Stopping services..." -ForegroundColor Yellow
            Stop-Job -Job $backendJob, $cockpitJob -ErrorAction SilentlyContinue
            Remove-Job -Job $backendJob, $cockpitJob -Force -ErrorAction SilentlyContinue
            Write-Host "All services stopped" -ForegroundColor Green
        }
    } else {
        Write-Host "[WARNING] Cockpit project not found at: $cockpitDir" -ForegroundColor Yellow
        $SkipCockpit = $true
    }
}

if ($SkipCockpit) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Dexter Backend is Running!" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Backend: http://localhost:$Port" -ForegroundColor White
    Write-Host "Cockpit: Not started" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Press Ctrl+C to stop backend" -ForegroundColor Yellow
    Write-Host ""
    
    # Monitor backend job
    try {
        Wait-Job -Job $backendJob | Out-Null
    } finally {
        Write-Host ""
        Write-Host "Stopping backend..." -ForegroundColor Yellow
        Stop-Job -Job $backendJob -ErrorAction SilentlyContinue
        Remove-Job -Job $backendJob -Force -ErrorAction SilentlyContinue
        Write-Host "Backend stopped" -ForegroundColor Green
    }
}
