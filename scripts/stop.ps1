$taskRoot = Split-Path $PSScriptRoot -Parent
& (Join-Path $taskRoot 'work/venv/Scripts/python.exe') (Join-Path $taskRoot 'outputs/local_voice/control.py') stop
