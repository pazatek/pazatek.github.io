# Installs the Room Coach thermal agent on this PC. Run it once the camera is plugged in:
#   powershell -ExecutionPolicy Bypass -File install.ps1
# It copies the agent to %USERPROFILE%\room-thermal, makes a Python venv with pysenxor-lite, and adds a scheduled task
# "Room thermal camera" that starts the agent at logon and restarts it within a minute if it stops.
$ErrorActionPreference = 'Stop'
$dest = Join-Path $env:USERPROFILE 'room-thermal'
New-Item -ItemType Directory -Force $dest | Out-Null
Copy-Item (Join-Path $PSScriptRoot 'thermal_agent.py'), (Join-Path $PSScriptRoot 'room_scene.py') $dest -Force

$venv = Join-Path $dest 'venv'
if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) { py -3.12 -m venv $venv }
& (Join-Path $venv 'Scripts\python.exe') -m pip install --quiet --upgrade pip pysenxor-lite numpy
if (-not (Test-Path (Join-Path $dest 'thermal.env'))) { Write-Warning 'thermal.env is missing; the camera key lives there. Ask Claude to make one.' }

$action = New-ScheduledTaskAction -Execute (Join-Path $venv 'Scripts\pythonw.exe') -Argument "`"$dest\thermal_agent.py`"" -WorkingDirectory $dest
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'Room thermal camera' -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName 'Room thermal camera'
Write-Host "Installed. Log: $dest\agent.log"
