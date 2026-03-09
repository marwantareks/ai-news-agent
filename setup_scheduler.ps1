# setup_scheduler.ps1
# Run once (as Administrator) to register the daily Task Scheduler job.
# It will run at 3:00 AM GMT every day.
# If the laptop was off at 3 AM, it runs automatically at next startup.

$taskName   = "AI-News-Agent-Daily"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$batFile    = Join-Path $projectDir "run_agent.bat"

# ── Compute 3:00 AM GMT as local time ──────────────────────────────────────
$utcOffset  = [System.TimeZone]::CurrentTimeZone.GetUtcOffset([System.DateTime]::Now).TotalHours
$localHour  = [int](((3 + $utcOffset) % 24 + 24) % 24)
$localMin   = 0
$triggerTime = "{0:D2}:{1:D2}" -f $localHour, $localMin

Write-Host "Your UTC offset : $utcOffset hours"
Write-Host "Scheduled time  : $triggerTime local (= 03:00 GMT)"
Write-Host "Project folder  : $projectDir"
Write-Host ""

# ── Build Task XML ─────────────────────────────────────────────────────────
$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Daily AI news digest - Anthropic, OpenAI, Google Gemini, Meta AI, Mistral</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-01-01T${triggerTime}:00</StartBoundary>
      <ExecutionTimeLimit>PT30M</ExecutionTimeLimit>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <ExecutionTimeLimit>PT30M</ExecutionTimeLimit>
    <Hidden>false</Hidden>
    <WakeToRun>false</WakeToRun>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$batFile</Command>
      <WorkingDirectory>$projectDir</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

# ── Register the task ──────────────────────────────────────────────────────
$tmpXml = Join-Path $env:TEMP "ai-news-task.xml"
$xml | Out-File -FilePath $tmpXml -Encoding Unicode

# Remove existing task if present
schtasks /delete /tn $taskName /f 2>$null | Out-Null

schtasks /create /tn $taskName /xml $tmpXml /f
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Task '$taskName' registered successfully." -ForegroundColor Green
    Write-Host "- Runs daily at $triggerTime local time (03:00 GMT)"
    Write-Host "- Runs on next startup if the scheduled time was missed"
    Write-Host "- Reports saved to: $projectDir\reports\"
} else {
    Write-Host "Failed to register task. Try running this script as Administrator." -ForegroundColor Red
}

Remove-Item $tmpXml -ErrorAction SilentlyContinue
