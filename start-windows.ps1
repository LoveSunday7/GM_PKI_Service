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

function Find-CommandPath($Names) {
    foreach ($name in $Names) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd.Source
        }
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

Write-Host ""
Write-Host "GM PKI Service - Windows launcher" -ForegroundColor Green
Write-Host ""

if (Test-PortOpen $BackendPort) {
    throw "Backend port $BackendPort is already in use. Close that process or pass -BackendPort."
}
if (Test-PortOpen $FrontendPort) {
    throw "Frontend port $FrontendPort is already in use. Close that process or pass -FrontendPort."
}

$Python = Find-CommandPath @("python.exe", "python3.exe", "py.exe")
if (-not $Python) {
    throw "Python was not found. Install Python 3.10+ and enable Add Python to PATH."
}
Write-Ok "Python: $Python"

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

$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Step "Creating backend virtual environment..."
    & $Python -m venv (Join-Path $BackendDir ".venv")
}

if (-not $SkipInstall) {
    $ReqMarker = Join-Path $BackendDir ".venv\.deps_installed"
    if (-not (Test-Path $ReqMarker)) {
        Write-Step "Installing backend dependencies..."
        & $VenvPython -m pip install -r (Join-Path $BackendDir "requirements.txt")
        New-Item -ItemType File -Force -Path $ReqMarker | Out-Null
    } else {
        Write-Ok "Backend dependencies are already installed"
    }

    if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
        Write-Step "Installing frontend dependencies..."
        Push-Location $FrontendDir
        & $Npm install
        Pop-Location
    } else {
        Write-Ok "Frontend dependencies are already installed"
    }
}

Remove-Item -LiteralPath $BackendLog, $BackendErr, $FrontendLog, $FrontendErr -Force -ErrorAction SilentlyContinue

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

Write-Step "Starting frontend..."
$FrontendArgs = @("run", "dev", "--", "--host", "0.0.0.0", "--port", "$FrontendPort")
$FrontendProcess = Start-Process -FilePath $Npm `
    -ArgumentList $FrontendArgs `
    -WorkingDirectory $FrontendDir `
    -RedirectStandardOutput $FrontendLog `
    -RedirectStandardError $FrontendErr `
    -PassThru
$FrontendProcess.Id | Set-Content -Encoding ASCII (Join-Path $PidDir "frontend-windows.pid")
Write-Ok "Frontend started. PID: $($FrontendProcess.Id)"

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
