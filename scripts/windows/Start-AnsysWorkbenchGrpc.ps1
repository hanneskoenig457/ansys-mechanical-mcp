param(
    [int]$GrpcPort = $(
        if ($env:ANSYS_WORKBENCH_GRPC_PORT) {
            [int]$env:ANSYS_WORKBENCH_GRPC_PORT
        } else {
            51000
        }
    ),
    [int]$StartupWaitSeconds = $(
        if ($env:ANSYS_WORKBENCH_START_WAIT_SECONDS) {
            [int]$env:ANSYS_WORKBENCH_START_WAIT_SECONDS
        } else {
            180
        }
    ),
    [string]$WorkbenchExecutable = "C:\Program Files\ANSYS Inc\v251\Framework\bin\Win64\RunWB2.exe",
    [string]$TaskName = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($TaskName)) {
    $TaskName = "Ansys Workbench gRPC $GrpcPort"
}

function Test-GrpcListener {
    $listener = Get-NetTCPConnection `
        -State Listen `
        -LocalPort $GrpcPort `
        -ErrorAction SilentlyContinue
    return $null -ne $listener
}

if (-not (Test-Path -LiteralPath $WorkbenchExecutable -PathType Leaf)) {
    throw "Workbench executable not found: $WorkbenchExecutable"
}

if (Test-GrpcListener) {
    Write-Output "Workbench gRPC is already listening on port $GrpcPort."
    exit 0
}

# A program launched directly by Windows OpenSSH lands in the non-interactive
# Session 0. An interactive scheduled task launches the GUI in the signed-in
# Parallels user's desktop (Session 1) instead, same pattern as
# Start-AnsysMechanicalGrpc.ps1. Unlike that script, StartServer() is not a
# command-line switch: it is passed via Workbench's own "-E <command>" inline
# script argument (this is exactly what ansys.workbench.core.launch_workbench()
# does internally). This Ansys 251 install's StartServer() does not accept a
# 'Security' keyword argument (older addin signature) -- omit it. The
# resulting server still accepts an insecure gRPC client connection, matching
# the rest of this deployment's transport mode.
$prefix = [guid]::NewGuid().ToString("N")
$startServerCmd = "StartServer(EnvironmentPrefix='$prefix',PortToUse=$GrpcPort)"
$arguments = @("-I", "-E", $startServerCmd)

$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction `
    -Execute $WorkbenchExecutable `
    -Argument ($arguments -join " ")
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
        -Description "Starts Ansys Workbench 2025 R1 (GUI) with its project-schematic gRPC server on port $GrpcPort." `
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

Start-ScheduledTask -TaskName $TaskName

$deadline = (Get-Date).AddSeconds($StartupWaitSeconds)
while ((Get-Date) -lt $deadline) {
    if (Test-GrpcListener) {
        Write-Output "Workbench gRPC started successfully on port $GrpcPort."
        exit 0
    }
    Start-Sleep -Seconds 2
}

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
$state = if ($null -eq $task) { "missing" } else { $task.State }
$result = if ($null -eq $taskInfo) { "unknown" } else { $taskInfo.LastTaskResult }
throw "Workbench did not open gRPC port $GrpcPort within $StartupWaitSeconds seconds. Scheduled-task state=$state, lastResult=$result. Ensure the Windows user is interactively signed in. If Workbench shows a 'GuiOperation Processing commandline argument' error dialog about an unknown 'Security' argument, close it manually once -- it means StartServer's signature changed and this script's -E command needs adjusting."
