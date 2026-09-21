$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskPython = Join-Path $taskRoot 'work/venv/Scripts/pythonw.exe'
$taskScript = Join-Path $taskRoot 'outputs/local_voice/maintenance.py'
if (!(Test-Path -LiteralPath $taskPython)) { throw 'Run setup first.' }
$taskAction = New-ScheduledTaskAction -Execute $taskPython -Argument ('"' + $taskScript + '"') -WorkingDirectory $taskRoot
$taskTriggers = @((New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)), (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)))
$taskSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 3) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$taskPrincipal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'DreamType Maintenance' -Action $taskAction -Trigger $taskTriggers -Settings $taskSettings -Principal $taskPrincipal -Description 'Check DreamType, recover stopped services, and create private encrypted daily backups.' -Force | Out-Null
Write-Output 'DreamType maintenance installed. Runs while this Windows user is logged in; does not prevent sleep.'
