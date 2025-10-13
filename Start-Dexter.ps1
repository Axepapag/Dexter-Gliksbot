<# 
    Dexter Autonomy launcher for Windows.
    - Verifies Redis availability (required for the full stack).
    - Starts the Python backend in its own terminal window.
    - Ensures the WPF cockpit is built before launching (unless -SkipUI).
#>
param(
    [switch]$SkipUI,
    [string]$PythonExe = 'python',
    [string]$RedisPath
)

$ErrorActionPreference = 'Stop'

function Write-Stage {
    param(
        [string]$Message,
        [ConsoleColor]$Color = [ConsoleColor]::Cyan
    )
    $stamp = Get-Date -Format 'HH:mm:ss'
    Write-Host "[$stamp] $Message" -ForegroundColor $Color
}

function Test-RedisConnection {
    param([string]$RedisHost = '127.0.0.1', [int]$Port = 6379)
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $async = $client.BeginConnect($RedisHost, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(1000)) {
            $client.Close()
            return $false
        }
        $client.EndConnect($async) | Out-Null
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

function Resolve-RedisExecutable {
    param([string]$PathCandidate)

    if (-not $PathCandidate) { return $null }

    if (Test-Path $PathCandidate -PathType Leaf) {
        return $PathCandidate
    }

    if (Test-Path $PathCandidate -PathType Container) {
        $match = Get-ChildItem -Path $PathCandidate -Filter "redis-server*.exe" -File -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($match) {
            return $match.FullName
        }
    }
    return $null
}

function Ensure-Redis {
    param([string]$RequestedPath)

    if (Test-RedisConnection) {
        Write-Stage "Redis is running on localhost:6379."
        return $true
    }

    try {
        $svc = Get-Service -Name 'redis' -ErrorAction Stop
        if ($svc.Status -ne 'Running') {
            Write-Stage "Starting Redis Windows service..."
            Start-Service -Name 'redis'
            Start-Sleep -Seconds 2
        }
        if (Test-RedisConnection) {
            Write-Stage "Redis service is running."
            return $true
        }
    } catch {
        # Service not found or failed
    }

    $candidates = @()
    if ($RequestedPath) { $candidates += Resolve-RedisExecutable $RequestedPath }
    if ($env:REDIS_SERVER_EXE) { $candidates += Resolve-RedisExecutable $env:REDIS_SERVER_EXE }
    $candidates += @(
        Resolve-RedisExecutable "C:\Redis",
        Resolve-RedisExecutable "C:\Program Files\Redis",
        Resolve-RedisExecutable "C:\Program Files\Redis\redis-server.exe"
    )
    $candidates = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

    foreach ($exe in $candidates) {
        $dir = Split-Path $exe -Parent
        $conf = Join-Path $dir 'redis.windows.conf'
        $args = @()
        if (Test-Path $conf) { $args += $conf }

        Write-Stage "Attempting to launch Redis from '$exe'..."
        try {
            $proc = Start-Process -FilePath $exe -ArgumentList $args -PassThru -WindowStyle Hidden
            Start-Sleep -Seconds 2
            if (Test-RedisConnection) {
                Write-Stage "Redis started (PID $($proc.Id))."
                return $true
            }
            Write-Stage "Redis did not respond after launch attempt." ([ConsoleColor]::Yellow)
            try { $proc | Stop-Process -ErrorAction SilentlyContinue } catch {}
        } catch {
            Write-Stage "Failed to start Redis from '$exe': $($_.Exception.Message)" ([ConsoleColor]::Red)
        }
    }

    Write-Stage "Redis is required but was not found. Install Redis or provide -RedisPath <redis-server.exe> (file or directory)." ([ConsoleColor]::Red)
    return $false
}

function Resolve-Shell {
    if (Get-Command pwsh.exe -ErrorAction SilentlyContinue) { return 'pwsh.exe' }
    return 'powershell.exe'
}

function Ensure-CockpitBuild($RepoRoot) {
    $project = Join-Path $RepoRoot 'cockpit\DexterCockpit\DexterCockpit.csproj'
    $releaseExe = Join-Path $RepoRoot 'cockpit\DexterCockpit\bin\Release\net8.0-windows\DexterCockpit.exe'
    if (Test-Path $releaseExe) {
        return $releaseExe
    }

    Write-Stage "Building Dexter cockpit (Release configuration)..."
    $build = Start-Process -FilePath 'dotnet' -ArgumentList @('build', $project, '-c', 'Release') -Wait -PassThru
    if ($build.ExitCode -ne 0) {
        throw "dotnet build failed (exit code $($build.ExitCode))."
    }

    if (-not (Test-Path $releaseExe)) {
        throw "Build completed but cockpit executable was not found at $releaseExe."
    }

    Write-Stage "Cockpit build ready."
    return $releaseExe
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

if (-not (Ensure-Redis -RequestedPath $RedisPath)) {
    Write-Stage "Launcher aborted because Redis is unavailable." ([ConsoleColor]::Red)
    exit 1
}

$shellExe = Resolve-Shell
$backendCommand = "Set-Location `"$repoRoot`"; $PythonExe start.py --port 8765"

Write-Stage "Launching Dexter backend (full stack)..."
Start-Process -FilePath $shellExe -ArgumentList @('-NoExit', '-Command', $backendCommand) | Out-Null

if ($SkipUI) {
    Write-Stage "UI launch skipped by request." ([ConsoleColor]::DarkGray)
} else {
    try {
        $uiExe = Ensure-CockpitBuild -RepoRoot $repoRoot
        Write-Stage "Launching Dexter cockpit UI..."
        Start-Process -FilePath $uiExe -WorkingDirectory (Split-Path $uiExe -Parent) | Out-Null
    } catch {
        Write-Stage "Unable to launch the cockpit: $($_.Exception.Message)" ([ConsoleColor]::Red)
    }
}

Write-Stage "Launcher has finished dispatching services. Close spawned windows to stop Dexter." ([ConsoleColor]::Green)
