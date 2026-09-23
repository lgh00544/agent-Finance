p = r"D:\self\backend_watchdog.ps1"
s = open(p, encoding="utf-8").read()
old = """function Test-BackendHealth {\n    try {\n        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 15 -UseBasicParsing\n        if ($r.StatusCode -ne 200) { return $false }\n        return ($r.Content -match 'status')\n    } catch {\n        return $false\n    }\n}"""
new = """function Test-BackendHealth {\n    # 连续 3 次失败才判挂死（单次网络抖动/超时不得触发误杀）\n    for ($i = 1; $i -le 3; $i++) {\n        try {\n            $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 20 -UseBasicParsing\n            if ($r.StatusCode -eq 200 -and $r.Content) { return $true }\n        } catch {\n            Write-Log ('HEALTH_PROBE_FAIL ' + $i + '/3 : ' + $_.Exception.Message)\n        }\n        Start-Sleep -Seconds 5\n    }\n    return $false\n}"""
assert old in s, "anchor missing"
s = s.replace(old, new, 1)
open(p, "w", encoding="utf-8").write(s)
print("watchdog hardened")