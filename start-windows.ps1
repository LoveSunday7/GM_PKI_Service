param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectDir "backend"
$FrontendDir = Join-Path $ProjectDir "frontend"
$LogDir = Join-Path $ProjectDir ".logs"
$PidDir = Join-Path $ProjectDir ".pids"
$BackendLog = Join-Path $LogDir "backend-windows.log"
$BackendErr = Join-Path $LogDir "backend-windows.err.log"
$FrontendLog = Join-Path $LogDir "frontend-windows.log"
$FrontendErr = Join-Path $LogDir "frontend-windows.err.log"
$LauncherLog = Join-Path $LogDir "launcher-windows.log"

New-Item -ItemType Directory -Force -Path $LogDir, $PidDir | Out-Null

function Write-Step($Message) {
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Ok($Message) {
    Write-Host "[ OK ] $Message" -ForegroundColor Green
}

function Write-Warn($Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Normalize-ProcessPathEnvironment() {
    $envVars = [System.Environment]::GetEnvironmentVariables()
    $pathKeys = @($envVars.Keys | Where-Object { $_ -ieq "Path" })
    if ($pathKeys.Count -le 1) {
        return
    }

    $pathValue = $env:Path
    if (-not $pathValue) {
        $pathValue = $env:PATH
    }

    foreach ($key in $pathKeys) {
        [System.Environment]::SetEnvironmentVariable([string]$key, $null, "Process")
    }
    [System.Environment]::SetEnvironmentVariable("Path", $pathValue, "Process")
}

function Find-CommandPath($Names) {
    foreach ($name in $Names) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd.Source
        }
    }
    return $null
}

function Find-PythonPath() {
    $fromPath = Find-CommandPath @("python.exe", "python3.exe", "py.exe")
    if ($fromPath) {
        return $fromPath
    }

    $codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-PythonUsable $codexPython) {
        return $codexPython
    }

    return $null
}

function Test-PortOpen($Port) {
    try {
        $client = New-Object Net.Sockets.TcpClient
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $ok = $async.AsyncWaitHandle.WaitOne(200)
        if ($ok) {
            $client.EndConnect($async)
            $client.Close()
            return $true
        }
        $client.Close()
        return $false
    } catch {
        return $false
    }
}

function Get-PortOwnerDescription($Port) {
    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $connections) {
            return "unknown process"
        }
        $items = @()
        foreach ($conn in $connections) {
            $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
            $name = if ($proc) { $proc.ProcessName } else { "unknown" }
            $items += "PID $($conn.OwningProcess) ($name)"
        }
        return ($items -join ", ")
    } catch {
        return "unknown process"
    }
}

function Stop-StaleProjectProcess($Name) {
    $file = Join-Path $PidDir "$Name-windows.pid"
    if (-not (Test-Path $file)) {
        return
    }
    $pidValue = Get-Content -LiteralPath $file -ErrorAction SilentlyContinue
    if (-not $pidValue) {
        Remove-Item -LiteralPath $file -Force -ErrorAction SilentlyContinue
        return
    }
    $proc = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
    if (-not $proc) {
        Remove-Item -LiteralPath $file -Force -ErrorAction SilentlyContinue
        return
    }
    Write-Warn "Stopping previous $Name process from PID file: $pidValue"
    Stop-Process -Id $proc.Id -Force
    Remove-Item -LiteralPath $file -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}

function Stop-PortOwners($Port, $Name) {
    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $connections) {
            return
        }

        foreach ($conn in $connections) {
            $pidValue = [int]$conn.OwningProcess
            if ($pidValue -le 0 -or $pidValue -eq $PID) {
                continue
            }

            $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
            $procName = if ($proc) { $proc.ProcessName } else { "unknown" }
            Write-Warn "$Name port $Port is occupied by PID $pidValue ($procName). Stopping it..."
            Stop-Process -Id $pidValue -Force -ErrorAction Stop
        }

        Start-Sleep -Milliseconds 800
    } catch {
        Write-Warn "Could not stop process using port ${Port}: $($_.Exception.Message)"
    }
}

function Test-PythonUsable($Path) {
    if (-not (Test-Path $Path)) {
        return $false
    }
    try {
        & $Path -c "import sys; print(sys.executable)" | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Test-BackendDeps($Path) {
    try {
        & $Path -c "import fastapi, uvicorn, sqlalchemy, gmssl" | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Wait-Http($Url, $Name) {
    for ($i = 1; $i -le 45; $i++) {
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2 | Out-Null
            Write-Ok "$Name is ready"
            return
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    Write-Warn "$Name is slow to start. Check logs in $LogDir"
}

function Test-HttpOk($Url) {
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function ConvertTo-CmdArgument($Value) {
    return '"' + ([string]$Value).Replace('"', '\"') + '"'
}

function Start-CmdLoggedProcess($FilePath, $Arguments, $WorkingDirectory, $StdOut, $StdErr) {
    $parts = @((ConvertTo-CmdArgument $FilePath))
    foreach ($arg in $Arguments) {
        $parts += ConvertTo-CmdArgument $arg
    }
    $command = "$($parts -join ' ') > $(ConvertTo-CmdArgument $StdOut) 2> $(ConvertTo-CmdArgument $StdErr)"
    $cmdArgument = "`"$command`""
    "cmd.exe /d /c $cmdArgument" | Add-Content -Encoding UTF8 -LiteralPath $LauncherLog

    return Start-Process -FilePath $env:ComSpec `
        -ArgumentList @("/d", "/c", $cmdArgument) `
        -WorkingDirectory $WorkingDirectory `
        -PassThru
}

Write-Host ""
Write-Host "GM PKI Service - Windows launcher" -ForegroundColor Green
Write-Host ""

Normalize-ProcessPathEnvironment

Stop-StaleProjectProcess "frontend"
Stop-StaleProjectProcess "backend"

$BackendAlreadyRunning = $false
$FrontendAlreadyRunning = $false

if (Test-PortOpen $BackendPort -and (Test-HttpOk "http://127.0.0.1:$BackendPort/api/health")) {
    Write-Ok "Backend is already running on port $BackendPort. Reusing it."
    $BackendAlreadyRunning = $true
}

if ((-not $BackendAlreadyRunning) -and (Test-PortOpen $BackendPort)) {
    Stop-PortOwners $BackendPort "Backend"
}

if (Test-PortOpen $FrontendPort -and (Test-HttpOk "http://127.0.0.1:$FrontendPort")) {
    Write-Ok "Frontend is already running on port $FrontendPort. Reusing it."
    $FrontendAlreadyRunning = $true
}

if ((-not $FrontendAlreadyRunning) -and (Test-PortOpen $FrontendPort)) {
    Stop-PortOwners $FrontendPort "Frontend"
}

if ((-not $BackendAlreadyRunning) -and (Test-PortOpen $BackendPort)) {
    $owner = Get-PortOwnerDescription $BackendPort
    throw "Backend port $BackendPort is already in use by $owner. Run .\stop-windows.ps1, close that process, or pass -BackendPort."
}
if ((-not $FrontendAlreadyRunning) -and (Test-PortOpen $FrontendPort)) {
    $owner = Get-PortOwnerDescription $FrontendPort
    throw "Frontend port $FrontendPort is already in use by $owner. Run .\stop-windows.ps1, close that process, or pass -FrontendPort."
}

$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$VenvDir = Join-Path $BackendDir ".venv"

$Python = $null
if (-not $BackendAlreadyRunning) {
    $Python = Find-PythonPath
    if (-not $Python) {
        throw "Python was not found. Install Python 3.10+ and enable Add Python to PATH."
    }
    Write-Ok "Python: $Python"

    if ((Test-Path $VenvDir) -and -not (Test-PythonUsable $VenvPython)) {
        Write-Warn "Backend virtual environment is broken. Recreating backend/.venv..."
        $resolvedVenv = (Resolve-Path -LiteralPath $VenvDir).Path
        $resolvedBackend = (Resolve-Path -LiteralPath $BackendDir).Path
        if (-not $resolvedVenv.StartsWith($resolvedBackend, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove unexpected venv path: $resolvedVenv"
        }
        Remove-Item -LiteralPath $VenvDir -Recurse -Force
    }

    if (-not (Test-PythonUsable $VenvPython)) {
        Write-Step "Creating backend virtual environment..."
        & $Python -m venv $VenvDir
        if (-not (Test-PythonUsable $VenvPython)) {
            throw "Backend virtual environment was created but python.exe cannot run. Please reinstall Python and recreate backend/.venv."
        }
    }
}

$Node = $null
$Npm = $null
if (-not $FrontendAlreadyRunning) {
    $Node = Find-CommandPath @("node.exe")
    if (-not $Node) {
        throw "Node.js was not found. Install Node.js 22.18+."
    }
    Write-Ok "Node: $(& $Node --version)"

    $Npm = Find-CommandPath @("npm.cmd")
    if (-not $Npm) {
        throw "npm.cmd was not found. Reinstall Node.js."
    }
    Write-Ok "npm: $(& $Npm --version)"
}

if (-not $SkipInstall) {
    $ReqMarker = Join-Path $BackendDir ".venv\.deps_installed"
    if ((-not $BackendAlreadyRunning) -and ((-not (Test-Path $ReqMarker)) -or (-not (Test-BackendDeps $VenvPython)))) {
        Write-Step "Installing backend dependencies..."
        & $VenvPython -m pip install -r (Join-Path $BackendDir "requirements.txt")
        New-Item -ItemType File -Force -Path $ReqMarker | Out-Null
    } elseif (-not $BackendAlreadyRunning) {
        Write-Ok "Backend dependencies are already installed"
    }

    if ((-not $FrontendAlreadyRunning) -and (-not (Test-Path (Join-Path $FrontendDir "node_modules")))) {
        Write-Step "Installing frontend dependencies..."
        Push-Location $FrontendDir
        & $Npm install
        Pop-Location
    } elseif (-not $FrontendAlreadyRunning) {
        Write-Ok "Frontend dependencies are already installed"
    }
}

Remove-Item -LiteralPath $BackendLog, $BackendErr, $FrontendLog, $FrontendErr -Force -ErrorAction SilentlyContinue

if (-not $BackendAlreadyRunning) {
    Write-Step "Starting backend..."
    $BackendArgs = @(
        "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0",
        "--port", "$BackendPort",
        "--reload",
        "--log-level", "info"
    )
    $BackendProcess = Start-Process -FilePath $VenvPython `
        -ArgumentList $BackendArgs `
        -WorkingDirectory $BackendDir `
        -RedirectStandardOutput $BackendLog `
        -RedirectStandardError $BackendErr `
        -PassThru
    $BackendProcess.Id | Set-Content -Encoding ASCII (Join-Path $PidDir "backend-windows.pid")
    Write-Ok "Backend started. PID: $($BackendProcess.Id)"
}

if (-not $FrontendAlreadyRunning) {
    Write-Step "Starting frontend..."
    $ViteStarter = Join-Path $FrontendDir "scripts\start-vite.mjs"
    $VitePackage = Join-Path $FrontendDir "node_modules\vite\package.json"
    if (-not (Test-Path $VitePackage)) {
        throw "Frontend dependencies are missing. Run start-windows.bat once without -SkipInstall so npm install can finish."
    }
    $FrontendArgs = @($ViteStarter, "--host", "0.0.0.0", "--port", "$FrontendPort")
    $FrontendProcess = Start-CmdLoggedProcess $Node $FrontendArgs $FrontendDir $FrontendLog $FrontendErr
    $FrontendProcess.Id | Set-Content -Encoding ASCII (Join-Path $PidDir "frontend-windows.pid")
    Write-Ok "Frontend started. PID: $($FrontendProcess.Id)"
}

Wait-Http "http://localhost:$BackendPort/api/health" "Backend"

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "Frontend:    http://localhost:$FrontendPort"
Write-Host "API docs:    http://localhost:$BackendPort/api/docs"
Write-Host "Health:      http://localhost:$BackendPort/api/health"
Write-Host "Login:       admin / admin123"
Write-Host "Logs:        $LogDir"
Write-Host ""
Write-Host "To stop services, run: .\stop-windows.ps1"
