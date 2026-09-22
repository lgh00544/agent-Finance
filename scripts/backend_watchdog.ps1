# 后端进程守护 watchdog (批A · A1)
# 60s 探活 127.0.0.1:8000 + /api/health；连续 3 次探活失败才判挂死（单次抖动不误杀）。
# 拉起 gate：net_check 出网/TiDB 不通不拉起；同一自然日拉起上限 3 次；拉起前归档 stdout/stderr。
param(
    [int]$IntervalSec = 60,
    [int]$ColdGrace = 600,
    [int]$StartupWait = 90,
    [int]$DailyRestartLimit = 3,
    [switch]$Once,
    [switch]$DryRun,
    [switch]$SimulateDown,
    [string]$NetCheckOutput = ''
)
$ErrorActionPreference = 'Continue'
$Root   = 'D:\self'
$Py     = 'D:\self\.venv\Scripts\python.exe'
$LogDir = Join-Path $Root 'logs'
$Log    = Join-Path $LogDir 'watchdog.log'
$Marker = Join-Path $LogDir 'watchdog.starting'

function Write-Log([string]$m) {
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
    $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m
    Add-Content -Path $Log -Value $line -Encoding utf8
    Write-Host $line
}

function Get-ListenerPid {
    $rows = netstat -ano | Select-String ':8000 ' | Select-String 'LISTENING'
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

function Get-BackendUptimeSec {
    # 命令行可读时只认后端进程；被沙箱拒绝时用最年轻 python 兜底（宁可不重启，也不双开）
    try {
        $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction Stop |
            Where-Object { $_.CommandLine -and ($_.CommandLine -match 'dev_run\.py' -or $_.CommandLine -match 'uvicorn') }
        if ($procs) {
            $p = $procs | Sort-Object CreationDate -Descending | Select-Object -First 1
            return (Get-ProcUptimeSec $p.ProcessId)
        }
        return -1
    } catch {
        try {
            $readable = @(Get-Process python -ErrorAction SilentlyContinue |
                Where-Object { try { [void]$_.StartTime; $true } catch { $false } })
            if ($readable.Count -gt 0) {
                $p = $readable | Sort-Object StartTime -Descending | Select-Object -First 1
                return (Get-ProcUptimeSec $p.Id)
            }
        } catch { }
        return -1
    }
}

function Test-OutNet {
    # 铁律：拉起前先跑 net_check.py；出网基线/TiDB 任一 FAIL 则不拉起
    if ($NetCheckOutput -and (Test-Path $NetCheckOutput)) {
        $out = Get-Content -Path $NetCheckOutput -Raw
    } else {
        try { $out = & $Py (Join-Path $Root 'net_check.py') 2>&1 | Out-String }
        catch { Write-Log ('NET_CHECK_ERR ' + $_.Exception.Message); return $false }
    }
    foreach ($h in @('www.baidu.com', 'tidbcloud.com')) {
        $line = (($out -split "`r?`n") | Where-Object { $_ -match [regex]::Escape($h) }) -join ' '
        if (-not $line -or $line -match 'FAIL') { Write-Log ('NET_DOWN ' + $h); return $false }
    }
    return $true
}

function Get-TodayRestartCount {
    if (-not (Test-Path $Log)) { return 0 }
    $today = Get-Date -Format 'yyyy-MM-dd'
    return @(Get-Content -Path $Log | Where-Object { $_ -like ($today + '*') -and $_ -match 'WATCHDOG_RESTART(?!_DRYRUN)' }).Count
}

function Archive-Log([string]$path, [string]$stamp) {
    if (Test-Path $path) {
        $name = [System.IO.Path]::GetFileNameWithoutExtension($path) + '.' + $stamp + [System.IO.Path]::GetExtension($path)
        Copy-Item $path (Join-Path $Root $name) -Force
    }
}

function Start-Backend {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $outLog = Join-Path $Root 'backend-dev.stdout.log'
    $errLog = Join-Path $Root 'backend-dev.stderr.log'
    Archive-Log $outLog $stamp
    Archive-Log $errLog $stamp
    if ($DryRun) {
        Write-Log ('WATCHDOG_RESTART_DRYRUN archived=' + $stamp)
        return 0
    }
    $p = Start-Process -FilePath $Py -ArgumentList @('backend/scripts/dev_run.py') -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
    Set-Content -Path $Marker -Value (Get-Date -Format o)
    Write-Log ('WATCHDOG_RESTART newpid=' + $p.Id + ' archived=' + $stamp)
    return $p.Id
}

function Invoke-Cycle {
    $listenPid = Get-ListenerPid
    if ($SimulateDown) { $listenPid = 0 }
    if ($listenPid -eq 0) {
        if (Test-Path $Marker) {
            $age = [int]((Get-Date) - (Get-Item $Marker).LastWriteTime).TotalSeconds
            if ($age -ge 0 -and $age -lt $ColdGrace) {
                Write-Log ('COLD_START marker age=' + $age + 's -> 宽限期内不重复拉起')
                return
            }
            Remove-Item $Marker -Force -ErrorAction SilentlyContinue
        }
        $up = Get-BackendUptimeSec
        if ($up -ge 0 -and $up -lt $ColdGrace) {
            Write-Log ('COLD_START uptime=' + $up + 's -> 宽限期内不重复拉起')
            return
        }
        if (-not (Test-OutNet)) {
            Write-Log 'NET_DOWN 出网/TiDB 不通 -> 不拉起'
            return
        }
        $n = Get-TodayRestartCount
        if ($n -ge $DailyRestartLimit) {
            Write-Log ('RESTART_CAP_REACHED ' + $n + '/' + $DailyRestartLimit + ' -> 只告警不拉起')
            return
        }
        Write-Log 'NOT_LISTENING 无进程或超冷启动宽限 -> 拉起'
        $null = Start-Backend
        Start-Sleep -Seconds $StartupWait
        return
    }
    if (Test-BackendHealth) {
        if (Test-Path $Marker) { Remove-Item $Marker -Force -ErrorAction SilentlyContinue }
        Write-Log ('OK pid=' + $listenPid + ' health=ok')
        return
    }
    $n = Get-TodayRestartCount
    if ($n -ge $DailyRestartLimit) {
        Write-Log ('RESTART_CAP_REACHED ' + $n + '/' + $DailyRestartLimit + ' health=bad -> 只告警不拉起')
        return
    }
    Write-Log ('HEALTH_BAD pid=' + $listenPid + ' -> 拉起')
    if (-not $DryRun) { try { Stop-Process -Id $listenPid -Force -ErrorAction Stop } catch { } }
    Start-Sleep -Seconds 5
    $null = Start-Backend
    Start-Sleep -Seconds $StartupWait
}

Write-Log ('WATCHDOG_START interval=' + $IntervalSec + 's coldGrace=' + $ColdGrace + 's cap=' + $DailyRestartLimit + ' dryRun=' + [bool]$DryRun + ' netCheckOutput=[' + $NetCheckOutput + ']')
while ($true) {
    try { Invoke-Cycle } catch { Write-Log ('WATCHDOG_ERR ' + $_.Exception.Message) }
    if ($Once) { break }
    Start-Sleep -Seconds $IntervalSec
}
