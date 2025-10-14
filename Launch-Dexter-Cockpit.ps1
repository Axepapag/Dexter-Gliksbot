#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Dexter Cockpit Launcher (PowerShell)

.DESCRIPTION
    Launches the WPF Cockpit UI for Dexter-Gliksbot
    
    Prerequisites:
      - .NET 8.0 SDK installed
      - Backend server running (python start.py --port 8765)

.PARAMETER Backend
    Backend URL (default: http://localhost:8765)

.PARAMETER Build
    Build configuration: Debug or Release (default: Debug)

.EXAMPLE
    .\Launch-Dexter-Cockpit.ps1
    
.EXAMPLE
    .\Launch-Dexter-Cockpit.ps1 -Backend "http://192.168.1.100:8765" -Build Release
#>

param(
    [string]$Backend = "http://localhost:8765",
    [ValidateSet("Debug", "Release")]
    [string]$Build = "Debug"
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Dexter Cockpit Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .NET SDK is installed
$dotnetPath = Get-Command dotnet -ErrorAction SilentlyContinue
if (-not $dotnetPath) {
    Write-Host "[ERROR] .NET SDK not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install .NET 8.0 SDK:" -ForegroundColor Yellow
    Write-Host "  https://dotnet.microsoft.com/download/dotnet/8.0" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Or use: winget install Microsoft.DotNet.SDK.8" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# Check .NET version
$dotnetVersion = & dotnet --version
Write-Host "Detected .NET SDK: $dotnetVersion" -ForegroundColor Green

if (-not $dotnetVersion.StartsWith("8.")) {
    Write-Host ""
    Write-Host "[WARNING] .NET SDK 8.0 is recommended" -ForegroundColor Yellow
    Write-Host "Current version: $dotnetVersion" -ForegroundColor Yellow
    Write-Host ""
}

# Navigate to cockpit directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$cockpitDir = Join-Path $scriptDir "cockpit\DexterCockpit"
$projectFile = Join-Path $cockpitDir "DexterCockpit.csproj"

if (-not (Test-Path $projectFile)) {
    Write-Host "[ERROR] Cockpit project not found!" -ForegroundColor Red
    Write-Host "Expected: $projectFile" -ForegroundColor Red
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "Cockpit directory: $cockpitDir" -ForegroundColor Gray
Write-Host "Backend URL: $Backend" -ForegroundColor Gray
Write-Host "Build configuration: $Build" -ForegroundColor Gray
Write-Host ""

# Restore dependencies
Write-Host "Restoring dependencies..." -ForegroundColor Cyan
Push-Location $cockpitDir
try {
    & dotnet restore | Out-Null
    Write-Host "Dependencies restored successfully" -ForegroundColor Green
} catch {
    Write-Host "[WARNING] Could not restore dependencies" -ForegroundColor Yellow
}
Pop-Location

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Starting Dexter Cockpit..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Make sure backend is running:" -ForegroundColor Yellow
Write-Host "  python start.py --port 8765" -ForegroundColor Yellow
Write-Host ""
Write-Host "Cockpit will connect to:" -ForegroundColor Cyan
Write-Host "  $Backend" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# Run the cockpit
Push-Location $cockpitDir
try {
    if ($Build -eq "Release") {
        & dotnet run --configuration Release
    } else {
        & dotnet run
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Cockpit stopped." -ForegroundColor Cyan
