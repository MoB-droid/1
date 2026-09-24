# Registers the Windows Task Scheduler entry for ASTS trigger watch (run once, as rayon, elevated).
# BR: at-startup trigger, run whether logged on, restart x3 every 1 min, any power, no idle stop, no time limit.
# ACTA: created DISABLED. ACTA enables it from registry col H = on.
$name   = "asts-trigger-watch"
$bat    = "C:\Users\rayon\Desktop\cld1\start_asts_trigger_watch.bat"
$action = New-ScheduledTaskAction -Execute $bat -WorkingDirectory "C:\Users\rayon\Desktop\cld1"
$trig   = New-ScheduledTaskTrigger -AtStartup
$set    = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
          -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
          -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -DontStopOnIdleEnd
$prin   = New-ScheduledTaskPrincipal -UserId "rayon" -LogonType S4U -RunLevel Limited   # run whether logged on or not
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trig -Settings $set -Principal $prin -Force | Out-Null
Disable-ScheduledTask -TaskName $name | Out-Null
Get-ScheduledTask -TaskName $name | Get-ScheduledTaskInfo
Write-Host "registered DISABLED. ACTA turns it on from col H. Manual start: Start-ScheduledTask -TaskName $name"
