$ErrorActionPreference = "Continue"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidDir = Join-Path $ProjectDir ".pids"

function Stop-ByPidFile($Name) {
    $file = Join-Path $PidDir "$Name-windows.pid"
    if (-not (Test-Path $file)) {
        Write-Host "$Name has no PID file. Skipped."
        return
    }

    $pidValue = Get-Content -LiteralPath $file -ErrorAction SilentlyContinue
    if ($pidValue) {
        $proc = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $proc.Id -Force
            Write-Host "$Name stopped. PID: $pidValue" -ForegroundColor Green
        } else {
            Write-Host "$Name process is not running. Removing PID file."
        }
    }
    Remove-Item -LiteralPath $file -Force -ErrorAction SilentlyContinue
}

Stop-ByPidFile "frontend"
Stop-ByPidFile "backend"
