param(
    [string]$InstallDirectory = "$env:ProgramData\AnsysMechanicalMcp\Autologon",
    [string]$TaskName = "Configure Windows Autologon",
    [string]$UserId = $([System.Security.Principal.WindowsIdentity]::GetCurrent().Name),
    [switch]$Launch
)

$ErrorActionPreference = "Stop"
$downloadUrl = "https://download.sysinternals.com/files/AutoLogon.zip"
$archivePath = Join-Path $env:TEMP "Sysinternals-Autologon.zip"

New-Item -ItemType Directory -Path $InstallDirectory -Force | Out-Null
Invoke-WebRequest -Uri $downloadUrl -OutFile $archivePath -UseBasicParsing
Expand-Archive -LiteralPath $archivePath -DestinationPath $InstallDirectory -Force

$executable = Join-Path $InstallDirectory "Autologon64.exe"
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Autologon64.exe was not found after extracting $downloadUrl"
}

$signature = Get-AuthenticodeSignature -LiteralPath $executable
if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -notmatch "Microsoft") {
    throw "Autologon64.exe signature validation failed: status=$($signature.Status), signer=$($signature.SignerCertificate.Subject)"
}

$action = New-ScheduledTaskAction -Execute $executable
$principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $existing) {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Principal $principal `
        -Settings $settings `
        -Description "Opens Microsoft's signed Sysinternals Autologon UI in the interactive console. Credentials are entered only in that local UI." | Out-Null
} else {
    Set-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Principal $principal `
        -Settings $settings | Out-Null
}

$hash = (Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash
Write-Output "Installed signed Sysinternals Autologon: $executable"
Write-Output "Signer: $($signature.SignerCertificate.Subject)"
Write-Output "SHA256: $hash"
Write-Output "Scheduled task: $TaskName"

if ($Launch) {
    $sessions = (query session 2>$null) -join "`n"
    if ($sessions -notmatch '(?m)^\s*>?console\s+\S+\s+\d+\s+(Aktiv|Active)') {
        throw "No active signed-in console user. Sign in once, then start scheduled task '$TaskName'."
    }
    Start-ScheduledTask -TaskName $TaskName
    Write-Output "Opened the Sysinternals Autologon UI in the interactive console."
}
