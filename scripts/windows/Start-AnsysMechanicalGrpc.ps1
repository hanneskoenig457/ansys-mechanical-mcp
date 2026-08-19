param(
    [int]$GrpcPort = $(
        if ($env:ANSYS_MECHANICAL_GRPC_PORT) {
            [int]$env:ANSYS_MECHANICAL_GRPC_PORT
        } else {
            50053
        }
    ),
    [int]$StartupWaitSeconds = $(
        if ($env:ANSYS_MECHANICAL_START_WAIT_SECONDS) {
            [int]$env:ANSYS_MECHANICAL_START_WAIT_SECONDS
        } else {
            180
        }
    ),
    [string]$MechanicalExecutable = "C:\Program Files\ANSYS Inc\v251\aisol\bin\winx64\AnsysWBU.exe",
    [string]$TaskName = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($TaskName)) {
    $TaskName = "Ansys Mechanical gRPC $GrpcPort"
}

function Test-GrpcListener {
    $listener = Get-NetTCPConnection `
        -State Listen `
        -LocalPort $GrpcPort `
        -ErrorAction SilentlyContinue
    return $null -ne $listener
}

if (-not (Test-Path -LiteralPath $MechanicalExecutable -PathType Leaf)) {
    throw "Mechanical executable not found: $MechanicalExecutable"
}

# A program launched directly by Windows OpenSSH can appear in a non-interactive
# desktop session. An interactive scheduled task deliberately launches the GUI
# in the signed-in Parallels user's desktop instead.
$arguments = "-DSApplet -AppModeMech -grpc $GrpcPort"
$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction `
    -Execute $MechanicalExecutable `
    -Argument $arguments
$principal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Limited
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $existingTask) {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Principal $principal `
        -Trigger $trigger `
        -Settings $settings `
        -Description "Starts Ansys Mechanical 2025 R1 with a dedicated local gRPC endpoint on port $GrpcPort." `
        -ErrorAction Stop | Out-Null
} else {
    Set-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Principal $principal `
        -Trigger $trigger `
        -Settings $settings `
        -ErrorAction Stop | Out-Null
}

if (Test-GrpcListener) {
    Write-Output "Mechanical startup task is ready; gRPC is already listening on port $GrpcPort."
    exit 0
}

Start-ScheduledTask -TaskName $TaskName

$deadline = (Get-Date).AddSeconds($StartupWaitSeconds)
while ((Get-Date) -lt $deadline) {
    if (Test-GrpcListener) {
        Write-Output "Mechanical gRPC started successfully on port $GrpcPort."
        exit 0
    }
    Start-Sleep -Seconds 2
}

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
$state = if ($null -eq $task) { "missing" } else { $task.State }
$result = if ($null -eq $taskInfo) { "unknown" } else { $taskInfo.LastTaskResult }
throw "Mechanical did not open gRPC port $GrpcPort within $StartupWaitSeconds seconds. Scheduled-task state=$state, lastResult=$result. Ensure the Windows user is interactively signed in."
