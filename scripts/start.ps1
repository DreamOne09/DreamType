$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskPython = Join-Path $taskRoot 'work/venv/Scripts/python.exe'
& $taskPython (Join-Path $taskRoot 'outputs/local_voice/control.py') start
if ($LASTEXITCODE -ne 0) { throw 'Start failed.' }
$taskReady = $false
for ($taskTry = 0; $taskTry -lt 90; $taskTry++) {
 try { $taskReady = (Invoke-RestMethod 'http://127.0.0.1:19870/health' -TimeoutSec 2).status -eq 'ready' } catch {}
 if ($taskReady) { break }
 Start-Sleep -Seconds 2
}
if (!$taskReady) { throw 'Models not ready. See work/logs.' }
& $taskPython (Join-Path $taskRoot 'outputs/local_voice/control.py') tunnel
if ($LASTEXITCODE -ne 0) { throw 'Tunnel failed.' }
& $taskPython (Join-Path $PSScriptRoot 'pair.py')
if ($LASTEXITCODE -ne 0) { throw 'Pairing failed. See work/logs.' }
Start-Process (Join-Path $taskRoot 'work/pairing.html')
