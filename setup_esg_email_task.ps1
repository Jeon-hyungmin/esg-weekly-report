$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = "python"
$scriptFile = Join-Path $scriptDir "generate_and_send_report.py"
$configFile = Join-Path $scriptDir "esg_email_config.json"

if (-not (Test-Path $scriptFile)) {
    Write-Error "generate_and_send_report.py 파일을 찾을 수 없습니다: $scriptFile"
    exit 1
}

if (-not (Test-Path $configFile)) {
    Write-Error "esg_email_config.json 파일을 찾을 수 없습니다. esg_email_config.json.example을 복사하여 값으로 채우세요."
    exit 1
}

$apiKey = $env:ANTHROPIC_API_KEY
if (-not $apiKey) {
    $apiKey = Read-Host "ANTHROPIC_API_KEY를 입력하세요"
}

$action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument "`"$scriptFile`"" `
    -WorkingDirectory $scriptDir

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday -At 09:00

$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

$envVar = [Microsoft.Win32.Registry]::SetValue(
    "HKEY_CURRENT_USER\Environment", "ANTHROPIC_API_KEY", $apiKey
)

$taskName = "ESG Weekly Report"

try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force
    Write-Host "예약 작업 '$taskName'이(가) 생성되었습니다. 매주 토요일 오전 9시에 실행됩니다."
    Write-Host "ANTHROPIC_API_KEY가 사용자 환경 변수에 저장되었습니다. (로그아웃 후 재로그인 필요)"
} catch {
    Write-Error "작업 생성 중 오류가 발생했습니다: $_"
    exit 1
}
