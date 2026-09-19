$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
New-Item -ItemType Directory -Force (Join-Path $taskRoot 'work') | Out-Null
py -3.12 -m venv (Join-Path $taskRoot 'work/venv')
if ($LASTEXITCODE -ne 0) { throw 'Please install Python 3.12 first.' }
$taskPython = Join-Path $taskRoot 'work/venv/Scripts/python.exe'
& $taskPython -m pip install -r (Join-Path $taskRoot 'outputs/local_voice/requirements-lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $taskPython (Join-Path $PSScriptRoot 'download_runtime.py')
if ($LASTEXITCODE -ne 0) { throw 'Runtime download failed.' }
Write-Output 'Ready. Run scripts/start.ps1 next.'
