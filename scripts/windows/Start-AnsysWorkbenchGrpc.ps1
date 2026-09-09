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
    # FlexNet licence port, as clients report it ("License path: 1055@localhost").
    [int]$LicensePort = $(
        if ($env:ANSYS_LICENSE_PORT) { [int]$env:ANSYS_LICENSE_PORT } else { 1055 }
    ),
    # Local Ansys Licensing Client web service. FlexNet can be listening while
    # this proxy is still unavailable, which makes Workbench open blocking
    # "Not connected to a server for Licensing Client Proxy actions" dialogs.
    [int]$LicensingClientPort = $(
        if ($env:ANSYS_LICENSING_CLIENT_PORT) { [int]$env:ANSYS_LICENSING_CLIENT_PORT } else { 1084 }
    ),
    # Require the complete licensing stack to remain healthy for a continuous
    # window. This absorbs the short post-restart interval in which the ports
    # exist but the client proxy has not finished connecting internally.
    [int]$LicensingStabilitySeconds = $(
        if ($env:ANSYS_LICENSING_STABILITY_SECONDS) { [int]$env:ANSYS_LICENSING_STABILITY_SECONDS } else { 20 }
    ),
    # Three-digit Ansys release directory ("251" = 2025 R1). Kept separate from
    # the executable path so a different release only needs one value, while
    # -WorkbenchExecutable still allows a non-standard install location.
    [string]$AnsysVersion = $(
        if ($env:ANSYS_VERSION) { $env:ANSYS_VERSION } else { "251" }
    ),
    [string]$WorkbenchExecutable = "C:\Program Files\ANSYS Inc\v$AnsysVersion\Framework\bin\Win64\RunWB2.exe",
    [string]$LicensingUtility = "C:\Program Files\ANSYS Inc\v$AnsysVersion\licensingclient\winx64\ansysli_util.exe",
    [string]$ProjectPath = "",
    [string]$TaskName = "",
    [switch]$LaunchWorkbenchProcess,
    [string]$StartupCommandBase64 = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($TaskName)) {
    $TaskName = "Ansys Workbench gRPC $GrpcPort"
}

# Internal entry point for the interactive scheduled task. Keep the launcher
# process hidden while RunWB2 itself remains visible in the signed-in desktop.
# This VM intentionally uses only its local FlexNet licence. The 2025 R1
# client otherwise adds web-elastic as a fallback and was observed crashing
# in that cache path (C0000005), after which Workbench showed two modal Client
# Proxy/licensing dialogs even though the FlexNet checkout had succeeded.
if ($LaunchWorkbenchProcess) {
    if ([string]::IsNullOrWhiteSpace($StartupCommandBase64)) {
        throw "StartupCommandBase64 is required with LaunchWorkbenchProcess."
    }
    $env:ANSYS_LICENSING_SERVICE_PRIORITY = "fnp"
    $decodedStartupCommand = [System.Text.Encoding]::UTF8.GetString(
        [Convert]::FromBase64String($StartupCommandBase64)
    )
    & $WorkbenchExecutable "-I" "-E" $decodedStartupCommand
    exit $LASTEXITCODE
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
if (-not (Test-Path -LiteralPath $LicensingUtility -PathType Leaf)) {
    throw "Ansys licensing utility not found: $LicensingUtility"
}
if (Test-GrpcListener) {
    Write-Output "Workbench gRPC is already listening on port $GrpcPort."
    return
}

# A running Workbench server can own an intentionally unsaved disposable
# project. Reuse that visible session without requiring a `.wbpj` file; the
# path is needed only when this bootstrap must launch a new Workbench process.
if (-not [string]::IsNullOrWhiteSpace($ProjectPath) -and -not (Test-Path -LiteralPath $ProjectPath -PathType Leaf)) {
    throw "Workbench project not found: $ProjectPath"
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

    # Then confirm the server is actually accepting connections on the licence
    # port, which is what a client failing here reports as
    # "License path: 1055@localhost". Checking the port rather than shelling
    # out to ansysli_util is deliberate: that utility's option set is not
    # stable to guess at (an invented "-liclist" silently failed every check
    # and blocked startup entirely), whereas a listening socket is unambiguous.
    $listening = Get-NetTCPConnection -State Listen -LocalPort $LicensePort -ErrorAction SilentlyContinue
    if ($null -eq $listening) { return $false }

    $clientListener = Get-NetTCPConnection `
        -State Listen `
        -LocalAddress "127.0.0.1" `
        -LocalPort $LicensingClientPort `
        -ErrorAction SilentlyContinue
    if ($null -eq $clientListener) { return $false }

    try {
        $response = Invoke-WebRequest `
            -Uri "http://127.0.0.1:$LicensingClientPort/" `
            -UseBasicParsing `
            -TimeoutSec 3 `
            -ErrorAction Stop
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Test-WorkbenchLicenseCheckout {
    # A listening FlexNet port only proves that a TCP socket exists. Exercise
    # the supported Ansys 2025 R1 client path with a one-second checkout of the
    # exact Workbench feature, then require its explicit OUT confirmation.
    # ansysli_util releases the temporary licence when it exits.
    $probeDirectory = Join-Path $env:TEMP "ansys-mechanical-mcp-license-probe"
    New-Item -ItemType Directory -Path $probeDirectory -Force | Out-Null
    $probeId = [guid]::NewGuid().ToString("N")
    $stdoutPath = Join-Path $probeDirectory "$probeId.stdout.txt"
    $stderrPath = Join-Path $probeDirectory "$probeId.stderr.txt"
    try {
        $probe = Start-Process `
            -FilePath $LicensingUtility `
            -ArgumentList @("-checkout", "ANS_WB", "-wait", "1") `
            -NoNewWindow `
            -PassThru `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath
        if (-not $probe.WaitForExit(60 * 1000)) {
            $probe.Kill()
            Write-Host "Workbench licence probe timed out after 60 seconds."
            return $false
        }
        # Windows PowerShell 5 can signal the timed WaitForExit overload before
        # redirected stream handlers have finished and before ExitCode is
        # populated. The parameterless call drains those handlers; Refresh then
        # makes the final exit code observable.
        $probe.WaitForExit()
        $probe.Refresh()
        $stdout = if (Test-Path $stdoutPath) { Get-Content $stdoutPath -Raw } else { "" }
        $stderr = if (Test-Path $stderrPath) { Get-Content $stderrPath -Raw } else { "" }
        # On this Windows PowerShell 5 installation ExitCode remains null for
        # this redirected utility even after Refresh(). `ANS_WB OUT` is the
        # utility's explicit, feature-specific success result and is therefore
        # the authoritative signal; failures do not emit that line.
        if ($stdout -match '(?m)^ANS_WB OUT\b') {
            Write-Host "Verified a real ANS_WB FlexNet checkout with ansysli_util."
            return $true
        }
        Write-Host "Workbench licence probe failed (exit $($probe.ExitCode)): $stdout $stderr"
        return $false
    } catch {
        Write-Host "Workbench licence probe failed: $($_.Exception.Message)"
        return $false
    } finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function Start-LicensingDaemons {
    # On this VM the FlexNet daemons do not reliably come up on their own after
    # a cold boot, even though the CVD service reports Running/Automatic.
    # Restarting that service does start them (verified). This is the scripted
    # equivalent of running ansyslmcenter.exe as administrator, which is what
    # gets the daemons up by hand. Requires an elevated session; the SSH login
    # on this VM already is one.
    $serverService = Get-Service "ANSYS, Inc. License Manager CVD" -ErrorAction SilentlyContinue
    if (-not $serverService) { return $false }
    $clientService = Get-Service "ANSYSLicensingTomcat" -ErrorAction SilentlyContinue
    try {
        # The License Management Center's manual Restart operation repairs the
        # FlexNet server side, but the observed cold-start failure was in the
        # separate Licensing Client Proxy. Restart both layers deterministically
        # so a stale Tomcat process cannot keep returning proxy errors.
        if ($clientService -and $clientService.Status -ne "Stopped") {
            Stop-Service $clientService -Force -ErrorAction Stop
            $clientService.WaitForStatus("Stopped", [TimeSpan]::FromSeconds(30))
        }
        Restart-Service $serverService -Force -ErrorAction Stop
        $serverService.WaitForStatus("Running", [TimeSpan]::FromSeconds(30))
        if ($clientService) {
            Start-Service $clientService -ErrorAction Stop
            $clientService.WaitForStatus("Running", [TimeSpan]::FromSeconds(30))
        }
        return $true
    } catch {
        Write-Host "Licensing restart failed: $($_.Exception.Message)"
        return $false
    }
}

function Invoke-ColdStartLicensingRestart {
    # App and AI launchers can overlap. Serialize their restart and keep a
    # short cooldown marker so both do not bounce the same services seconds
    # apart. A later retry in the same boot is still allowed after the
    # cooldown.
    $mutex = New-Object System.Threading.Mutex($false, "Global\AnsysMechanicalMcpLicensingRestart")
    $hasMutex = $false
    try {
        $hasMutex = $mutex.WaitOne([TimeSpan]::FromSeconds(90))
        if (-not $hasMutex) {
            Write-Host "Another launcher is still restarting licensing; continuing to wait for readiness."
            return $true
        }

        $markerPath = Join-Path $env:ProgramData "AnsysMechanicalMcp\licensing-restart-utc.txt"
        if (Test-Path -LiteralPath $markerPath -PathType Leaf) {
            $markerText = (Get-Content -LiteralPath $markerPath -Raw -ErrorAction SilentlyContinue).Trim()
            $markerTime = [DateTime]::MinValue
            if ([DateTime]::TryParse(
                $markerText,
                [System.Globalization.CultureInfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::RoundtripKind,
                [ref]$markerTime
            ) -and (([DateTime]::UtcNow - $markerTime.ToUniversalTime()).TotalSeconds -lt 60)) {
                Write-Host "Licensing was already restarted by the concurrent launcher less than 60 seconds ago."
                return $true
            }
        }

        if (Get-Process RunWB2, AnsysFWW, AnsysFW, AnsysWBU -ErrorAction SilentlyContinue) {
            Write-Host "An Ansys GUI appeared before the cold-start restart; refusing to interrupt a possible licence holder."
            return $false
        }

        Write-Host "Cold start: immediately restarting the License Manager and Licensing Client Proxy services."
        if (-not (Start-LicensingDaemons)) { return $false }

        New-Item -ItemType Directory -Path (Split-Path $markerPath) -Force | Out-Null
        [DateTime]::UtcNow.ToString("o", [System.Globalization.CultureInfo]::InvariantCulture) |
            Set-Content -LiteralPath $markerPath -Encoding Ascii
        return $true
    } finally {
        if ($hasMutex) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}

$readinessDeadline = (Get-Date).AddSeconds($ReadinessWaitSeconds)
$sessionOk = $false
$licenseOk = $false
$licensingStableSince = $null
$nudgedLicensing = $false
$coldStartRestartHandled = $false
# Give the daemons a grace period to appear by themselves before intervening;
# restarting the service while something holds a licence throws error dialogs
# in any running Ansys app. That hazard only exists if an Ansys app is actually
# running -- which on a cold boot it is not, since this script is what starts
# the first one. A measured cold start spent 97s waiting here and then needed
# 5s once the service was restarted, so the long grace period was almost pure
# waste in exactly the case it could not protect. Keep it only when there is
# something to protect.
$ansysAppsRunning = @(Get-Process RunWB2, AnsysFWW, AnsysWBU -ErrorAction SilentlyContinue)
if ($ansysAppsRunning.Count -gt 0) {
    $nudgeGraceSeconds = 90
    Write-Output "Ansys apps already running (licence holders possible); waiting $nudgeGraceSeconds s before touching the licensing service."
} else {
    $nudgeGraceSeconds = 0
    Write-Output "No Ansys app running; the complete licensing stack will be restarted immediately once session and network are ready."
}
$nudgeAfter = (Get-Date).AddSeconds($nudgeGraceSeconds)
while ((Get-Date) -lt $readinessDeadline) {
    if (-not $sessionOk) { $sessionOk = Test-InteractiveSession }
    $networkOk = Test-NetworkReady

    if (-not $coldStartRestartHandled -and $ansysAppsRunning.Count -eq 0 -and $sessionOk -and $networkOk) {
        $coldStartRestartHandled = $true
        $nudgedLicensing = Invoke-ColdStartLicensingRestart
        # Always re-evaluate after the services have settled (or after the
        # concurrent launcher has completed) rather than accepting sockets
        # observed just before the restart.
        $licensingStableSince = $null
        Start-Sleep -Seconds 3
        continue
    }

    if ($sessionOk -and $networkOk -and (Test-LicensingReady)) {
        if ($null -eq $licensingStableSince) {
            $licensingStableSince = Get-Date
            Write-Output "FlexNet and Licensing Client Proxy are reachable; requiring $LicensingStabilitySeconds seconds of continuous stability."
        }
        if (((Get-Date) - $licensingStableSince).TotalSeconds -ge $LicensingStabilitySeconds) {
            if (Test-WorkbenchLicenseCheckout) {
                $licenseOk = $true
                break
            }
            $licensingStableSince = $null
        }
    } else {
        $licensingStableSince = $null
    }
    if (-not $nudgedLicensing -and (Get-Date) -gt $nudgeAfter -and $sessionOk -and $networkOk) {
        Write-Output "Licensing stack still unhealthy; restarting the License Manager and Licensing Client Proxy services."
        $nudgedLicensing = Start-LicensingDaemons
        if (-not $nudgedLicensing) {
            Write-Output "Could not restart the licensing service automatically; continuing to wait."
            $nudgedLicensing = $true  # do not retry in a loop
        }
    }
    Start-Sleep -Seconds 3
}

if (-not $sessionOk) {
    throw "No active interactive console session. Sign in to Windows in the Parallels console, then retry: an interactive scheduled task cannot start a GUI without one."
}
if (-not $licenseOk) {
    throw "The complete Ansys licensing stack did not remain ready within $ReadinessWaitSeconds seconds (lmgrd, ansyslmd, FlexNet port $LicensePort, and Licensing Client Proxy HTTP port $LicensingClientPort). Workbench was not started because it would open blocking licence dialogs. Open http://localhost:$LicensingClientPort in the VM, repair licensing, then retry."
}

Write-Output "Interactive session, network, and licensing are ready."

# Serialize the complete check-and-launch section. Two callers can otherwise
# both observe "no RunWB2 process" during the same cold boot and then each
# register/start the interactive launcher before either Workbench becomes
# visible. The second Workbench subsequently fails with "Failed to bind port
# 0.0.0.0:<port>" even though the first one is healthy. The re-check after the
# mutex makes parallel app/AI invocations idempotent.
$launchMutex = New-Object System.Threading.Mutex($false, "Global\AnsysMechanicalMcpWorkbenchLaunch-$GrpcPort")
$hasLaunchMutex = $false
try {
    try {
        $hasLaunchMutex = $launchMutex.WaitOne([TimeSpan]::FromSeconds($StartupWaitSeconds + 30))
    } catch [System.Threading.AbandonedMutexException] {
        $hasLaunchMutex = $true
    }
    if (-not $hasLaunchMutex) {
        throw "Timed out waiting for another Workbench startup on gRPC port $GrpcPort to finish."
    }
    if (Test-GrpcListener) {
        Write-Output "Workbench gRPC is already listening on port $GrpcPort; reusing it."
        return
    }

# A Workbench from an earlier failed attempt is still running but has no
# server port (for example, stuck behind a licensing dialog). Launching a
# second one would not fix it and would leave two GUIs behind, so report the
# state instead of stacking processes.
$existingWorkbench = Get-Process RunWB2 -ErrorAction SilentlyContinue
if ($existingWorkbench) {
    # A prior launcher may still be completing. Give that same process the
    # full startup budget instead of stacking another GUI behind it. A
    # genuinely stuck process still fails with diagnostics after the deadline.
    Write-Output "Workbench (RunWB2, PID $($existingWorkbench.Id -join ', ')) is already starting; waiting for gRPC port $GrpcPort instead of launching a duplicate."
    $existingDeadline = (Get-Date).AddSeconds($StartupWaitSeconds)
    while ((Get-Date) -lt $existingDeadline) {
        if (Test-GrpcListener) {
            Write-Output "Existing Workbench opened gRPC port $GrpcPort successfully."
            return
        }
        Start-Sleep -Seconds 2
    }
    throw "Workbench (RunWB2, PID $($existingWorkbench.Id -join ', ')) remained running without gRPC port $GrpcPort for $StartupWaitSeconds seconds. It may be blocked by an error dialog or may have been launched without StartServer(). Close it in the VM and retry."
}

# Workbench leaves <project>_files\.lock behind when it is killed while a
# project is open. A later cold start then blocks behind a modal "project was
# locked" dialog. Quarantine only a lock owned by this same Windows user and
# computer, and only after proving that no local Workbench process exists.
if (-not [string]::IsNullOrWhiteSpace($ProjectPath)) {
    $projectDirectory = [System.IO.Path]::GetDirectoryName($ProjectPath)
    $projectStem = [System.IO.Path]::GetFileNameWithoutExtension($ProjectPath)
    $projectLock = Join-Path (Join-Path $projectDirectory "${projectStem}_files") ".lock"
    if (Test-Path -LiteralPath $projectLock -PathType Leaf) {
        $lockOwner = @(Get-Content -LiteralPath $projectLock -ErrorAction Stop)
        $isLocalOwner = $lockOwner.Count -ge 2 `
            -and $lockOwner[0].Trim() -eq $env:USERNAME `
            -and $lockOwner[1].Trim() -eq $env:COMPUTERNAME
        if (-not $isLocalOwner) {
            throw "Project lock belongs to another user or computer and was not touched: $projectLock"
        }
        if (Get-Process RunWB2, AnsysFWW, AnsysFW -ErrorAction SilentlyContinue) {
            throw "Project lock exists while a Workbench process is running; refusing to remove it: $projectLock"
        }
        $quarantinePath = "$projectLock.stale-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        Move-Item -LiteralPath $projectLock -Destination $quarantinePath -ErrorAction Stop
        Write-Output "Quarantined stale local Workbench project lock: $quarantinePath"
    }
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
$startupCommand = $startServerCmd
if (-not [string]::IsNullOrWhiteSpace($ProjectPath)) {
    # Workbench's startup scripting accepts forward slashes on Windows. They
    # avoid backslash escaping in the IronPython raw string. A single quote is
    # escaped for the IronPython literal before the command line is built.
    $projectForScript = $ProjectPath.Replace("\", "/").Replace("'", "\\'")
    $startupCommand = "Open(FilePath=r'$projectForScript');$startServerCmd"
}
$startupCommandBase64 = [Convert]::ToBase64String(
    [System.Text.Encoding]::UTF8.GetBytes($startupCommand)
)

$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$powerShellExecutable = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$launcherArguments = @(
    "-NoLogo",
    "-NoProfile",
    "-NonInteractive",
    "-WindowStyle", "Hidden",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$PSCommandPath`"",
    "-LaunchWorkbenchProcess",
    "-WorkbenchExecutable", "`"$WorkbenchExecutable`"",
    "-StartupCommandBase64", $startupCommandBase64
)
$action = New-ScheduledTaskAction `
    -Execute $powerShellExecutable `
    -Argument ($launcherArguments -join " ")
$principal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Limited
# Deliberately NO trigger. An -AtLogOn trigger was tried and is actively
# harmful here: Windows then launches Workbench about 10 seconds after boot,
# long before the FlexNet licensing daemons exist, so it comes up behind a
# "Cannot connect to license server system" dialog and bypasses every
# readiness check in this script. The task exists only as a launcher that
# Start-ScheduledTask invokes below, once conditions are verified.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $existingTask) {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Principal $principal `
        -Settings $settings `
        -Description "On-demand launcher for Ansys Workbench $AnsysVersion (GUI) with its project-schematic gRPC server on port $GrpcPort. Intentionally has no trigger: it is started only after licensing is verified." `
        -ErrorAction Stop | Out-Null
} else {
    Set-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Principal $principal `
        -Settings $settings `
        -ErrorAction Stop | Out-Null
}

Start-ScheduledTask -TaskName $TaskName

$deadline = (Get-Date).AddSeconds($StartupWaitSeconds)
while ((Get-Date) -lt $deadline) {
    if (Test-GrpcListener) {
        Write-Output "Workbench gRPC started successfully on port $GrpcPort."
        return
    }
    Start-Sleep -Seconds 2
}

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
$state = if ($null -eq $task) { "missing" } else { $task.State }
$result = if ($null -eq $taskInfo) { "unknown" } else { $taskInfo.LastTaskResult }
throw "Workbench did not open gRPC port $GrpcPort within $StartupWaitSeconds seconds. Scheduled-task state=$state, lastResult=$result. Ensure the Windows user is interactively signed in. If Workbench shows a 'GuiOperation Processing commandline argument' error dialog about an unknown 'Security' argument, close it manually once -- it means StartServer's signature changed and this script's -E command needs adjusting."
} finally {
    if ($hasLaunchMutex) {
        $launchMutex.ReleaseMutex()
    }
    $launchMutex.Dispose()
}
