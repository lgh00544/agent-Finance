# 后端进程守护 watchdog (批A · A1)
# 30s 探活一次：端口 + /api/health。端口在但 health 非 ok = 挂死 → 拉起。
# 端口空时先看是否仍在冷启动（uptime < ColdGrace 则不干预），避免误杀 6.5 分钟启动过程。
param(
    [int]$IntervalSec = 30,
    [int]$ColdGrace = 480,
    [int]$StartupWait = 90,
    [switch]$Once
)
$ErrorActionPreference = 'Continue'
$Root  = 'D:\self'
$Py    = 'D:\self\.venv\Scripts\python.exe'
$LogDir = Join-Path $Root 'logs'
$Log   = Join-Path $LogDir 'watchdog.log'

function Write-Log([string]$m) {
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
    $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m
    Add-Content -Path $Log -Value $line -Encoding utf8
    Write-Output $line
}

function Get-ListenerPid {
    $rows = netstat -ano | Select-String ':8000' | Select-String 'LISTENING'
    if (-not $rows) { return 0 }
    $parts = ($rows[0].ToString().Trim() -split '\s+')
    return [int]$parts[-1]
}

function Test-BackendHealth {
    # 连续 3 次失败才判挂死（单次网络抖动/超时不得触发误杀）
    for ($i = 1; $i -le 3; $i++) {
        try {
            $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 20 -UseBasicParsing
            if ($r.StatusCode -eq 200 -and $r.Content) { return $true }
        } catch {
            Write-Log ('HEALTH_PROBE_FAIL ' + $i + '/3 : ' + $_.Exception.Message)
        }
        Start-Sleep -Seconds 5
    }
    return $false
}

function Get-ProcUptimeSec([int]$thePid) {
    try {
        $p = Get-Process -Id $thePid -ErrorAction Stop
        return [int]((Get-Date) - $p.StartTime).TotalSeconds
    } catch {
        return -1
    }
}

function Start-Backend {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $outLog = Join-Path $Root 'backend-dev.stdout.log'
    $errLog = Join-Path $Root 'backend-dev.stderr.log'
    if (Test-Path $outLog) {
        Copy-Item $outLog (Join-Path $Root ('backend-dev.stdout.' + $stamp + '.log')) -Force
    }
    if (Test-Path $errLog) {
        Copy-Item $errLog (Join-Path $Root ('backend-dev.stderr.' + $stamp + '.log')) -Force
    }
    $uvArgs = @('-m','uvicorn','app.main:app','--app-dir','backend','--host','127.0.0.1','--port','8000')
    $p = Start-Process -FilePath $Py -ArgumentList $uvArgs -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
    Write-Log ('WATCHDOG_RESTART newpid=' + $p.Id + ' archived=' + $stamp)
    return $p.Id
}

Write-Log ('WATCHDOG_START interval=' + $IntervalSec + 's coldGrace=' + $ColdGrace + 's')
$notListeningSince = $null

while ($true) {
    try {
        $listenPid = Get-ListenerPid
        if ($listenPid -eq 0) {
            $cand = Get-Process python -ErrorAction SilentlyContinue | Sort-Object StartTime -Descending | Select-Object -First 1
            if ($cand) {
                $up = Get-ProcUptimeSec $cand.Id
                if ($up -ge 0 -and $up -lt $ColdGrace) {
                    if (-not $notListeningSince) { $notListeningSince = Get-Date }
                    $waited = [int]((Get-Date) - $notListeningSince).TotalSeconds
                    Write-Log ('COLD_START pid=' + $cand.Id + ' uptime=' + $up + 's waited=' + $waited + 's')
                    Start-Sleep -Seconds $IntervalSec
                    continue
                }
            }
            Write-Log 'NOT_LISTENING 无进程或超冷启动宽限 -> 拉起'
            $null = Start-Backend
            $notListeningSince = Get-Date
            Start-Sleep -Seconds $StartupWait
            continue
        }
        $notListeningSince = $null
        if (Test-BackendHealth) {
            Write-Log ('OK pid=' + $listenPid + ' health=ok')
        } else {
            Write-Log ('HEALTH_BAD pid=' + $listenPid + ' -> 拉起')
            try { Stop-Process -Id $listenPid -Force -ErrorAction Stop } catch { }
            Start-Sleep -Seconds 5
            $null = Start-Backend
            Start-Sleep -Seconds $StartupWait
        }
    } catch {
        Write-Log ('WATCHDOG_ERR ' + $_.Exception.Message)
    }
    if ($Once) { break }
    Start-Sleep -Seconds $IntervalSec
}
