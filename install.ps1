[CmdletBinding()]
param(
    [switch]$SkipTask
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Get-Command python -ErrorAction Stop

& $Python.Source -m venv (Join-Path $ProjectRoot '.venv')
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $ProjectRoot 'requirements.txt')

New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot 'logs'), (Join-Path $ProjectRoot 'data'), (Join-Path $ProjectRoot 'output') | Out-Null
& $VenvPython -m src.main --dry-run
if ($LASTEXITCODE -ne 0) {
    throw "Connectivity test failed. See logs\tesla_job_tracker.log. No scheduled task was created."
}

if (-not $SkipTask) {
    $TaskName = 'Tesla Job Tracker - Daily 11AM'
    $Action = New-ScheduledTaskAction -Execute $VenvPython -Argument '-m src.main' -WorkingDirectory $ProjectRoot
    $Trigger = New-ScheduledTaskTrigger -Daily -At 11:00AM
    $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
    $Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description 'Fetches Tesla US full-time jobs and records newly seen Req IDs.' -Force | Out-Null
    Write-Host "Scheduled task '$TaskName' created for 11:00 AM daily (StartWhenAvailable enabled)."
}

Write-Host 'Installation complete. Create the initial baseline with: .\run.bat --baseline'
