$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
& (Join-Path $taskRoot 'work/venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'control.py') start
