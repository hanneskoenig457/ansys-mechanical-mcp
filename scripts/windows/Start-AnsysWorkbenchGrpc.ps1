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
    # Separate budget: on a cold boot the FlexNet licensing daemons were seen
    # taking ~2 minutes to appear, and that wait must not eat into the time
    # allowed for Workbench itself to open its port afterwards.
    [int]$ReadinessWaitSeconds = $(
        if ($env:ANSYS_WORKBENCH_READY_WAIT_SECONDS) {
            [int]$env:ANSYS_WORKBENCH_READY_WAIT_SECONDS
        } else {
            300
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

# On a cold VM boot, SSH answers well before the machine is actually ready to
# run Ansys: the network adapter is still initializing and the licensing
# client cannot reach a server yet. Starting Workbench at that moment produces
# a blocking "could not connect to a valid licensing server" dialog, the GUI
# never finishes initializing, the -E StartServer command never runs, and the
# port never opens. Mechanical additionally falls back to read-only mode.
# So wait for licensing to actually be usable before launching anything.
function Test-InteractiveSession {
    # An interactive scheduled task cannot paint a GUI without a signed-in
    # console session.
    $sessions = (query session 2>$null) -join "`n"
    return $sessions -match '(?m)^\s*>?console\s+\S+\s+\d+\s+(Aktiv|Active)'
}

function Test-NetworkReady {
    $up = Get-NetAdapter -ErrorAction SilentlyContinue |
        Where-Object { $_.Status -eq "Up" -and $_.Virtual -eq $false }
    if (-not $up) {
        $up = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq "Up" }
    }
    return $null -ne $up
}

function Test-LicensingReady {
    # The Windows services (License Manager CVD, Licensing Tomcat) reach
    # "Running" well before licensing actually works: the FlexNet daemons
    # lmgrd and ansyslmd are what Workbench needs, and on this VM they were
    # observed appearing about 2 minutes after boot -- long after SSH answers.
    # Checking the services alone therefore reports ready far too early.
    $lmgrd = Get-Process lmgrd -ErrorAction SilentlyContinue
    $ansyslmd = Get-Process ansyslmd -ErrorAction SilentlyContinue
    if (-not $lmgrd -or -not $ansyslmd) { return $false }

    # Daemons are up; confirm with a real query when the utility is present.
    # -liclist asks the configured server without consuming a seat.
    if ($env:AWP_ROOT251) {
        $utility = Join-Path $env:AWP_ROOT251 "licensingclient\winx64\ansysli_util.exe"
        if (Test-Path -LiteralPath $utility -PathType Leaf) {
            $null = & $utility -liclist 2>&1
            return $LASTEXITCODE -eq 0
        }
    }
    return $true
}

$readinessDeadline = (Get-Date).AddSeconds($ReadinessWaitSeconds)
$sessionOk = $false
$licenseOk = $false
while ((Get-Date) -lt $readinessDeadline) {
    if (-not $sessionOk) { $sessionOk = Test-InteractiveSession }
    if ($sessionOk -and (Test-NetworkReady) -and (Test-LicensingReady)) {
        $licenseOk = $true
        break
    }
    Start-Sleep -Seconds 3
}

if (-not $sessionOk) {
    throw "No active interactive console session. Sign in to Windows in the Parallels console, then retry: an interactive scheduled task cannot start a GUI without one."
}
if (-not $licenseOk) {
    throw "Ansys licensing did not become reachable within $ReadinessWaitSeconds seconds (waiting for the lmgrd and ansyslmd FlexNet daemons). Workbench would open with a blocking 'could not connect to a valid licensing server' dialog and Mechanical would fall back to read-only, so it was not started. Open http://localhost:1084 in the VM and start the license manager, then retry. Raise ANSYS_WORKBENCH_READY_WAIT_SECONDS if the daemons simply need longer."
}

Write-Output "Interactive session, network, and licensing are ready."

# A Workbench from an earlier failed attempt is still running but has no
# server port (for example, stuck behind a licensing dialog). Launching a
# second one would not fix it and would leave two GUIs behind, so report the
# state instead of stacking processes.
$existingWorkbench = Get-Process RunWB2 -ErrorAction SilentlyContinue
if ($existingWorkbench) {
    throw "Workbench (RunWB2, PID $($existingWorkbench.Id -join ', ')) is already running but port $GrpcPort is not open. It was most likely started before licensing was reachable and is waiting on an error dialog, or was started without the -E StartServer argument. Close Workbench in the VM and retry; StartServer() only takes effect at launch."
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
