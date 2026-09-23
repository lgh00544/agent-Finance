p = r"D:\self\backend_watchdog.ps1"
s = open(p, encoding="utf-8").read()
s = s.replace("    $args = @('-m','uvicorn','app.main:app','--app-dir','backend','--host','127.0.0.1','--port','8000')", "    $uvArgs = @('-m','uvicorn','app.main:app','--app-dir','backend','--host','127.0.0.1','--port','8000')")
s = s.replace("-ArgumentList $args -WorkingDirectory", "-ArgumentList $uvArgs -WorkingDirectory")
s = s.replace("$pid8000", "$listenPid")
open(p, "w", encoding="utf-8").write(s)
print("args->uvArgs:", "$uvArgs" in s, "| listenPid:", s.count("$listenPid"))