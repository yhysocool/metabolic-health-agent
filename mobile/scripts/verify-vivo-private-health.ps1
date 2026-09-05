[CmdletBinding()]
param(
    [string]$AndroidHome,
    [string]$ApkPath,
    [string]$Package = 'com.healthevent.mobile',
    [string]$Serial,
    [switch]$RepairPermission
)

$ErrorActionPreference = 'Stop'
$Permission = 'com.vivo.health.widget.permission'
$ProviderAuthorities = @('com.vivo.health.provider', 'com.vivo.health.provider.care')

function Resolve-AdbPath {
    $roots = @()
    if ($AndroidHome) { $roots += $AndroidHome }
    if ($env:ANDROID_HOME) { $roots += $env:ANDROID_HOME }
    if ($env:ANDROID_SDK_ROOT) { $roots += $env:ANDROID_SDK_ROOT }
    $roots += @('E:\software\SDK', 'E:\HealthEvent\android-sdk')
    foreach ($root in ($roots | Select-Object -Unique)) {
        if (-not $root) { continue }
        $candidate = Join-Path $root 'platform-tools\adb.exe'
        if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    $command = Get-Command adb -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    throw '找不到 adb.exe。请安装 Android Platform-Tools，或通过 -AndroidHome 指定 SDK。'
}

function Invoke-DeviceAdb {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $fullArguments = @()
    if ($Serial) { $fullArguments += @('-s', $Serial) }
    $fullArguments += $Arguments
    $output = & $script:AdbPath @fullArguments 2>&1
    [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = ($output | Out-String) }
}

function Invoke-AdbInstall {
    param([Parameter(Mandatory = $true)][string]$Apk)
    $fullArguments = @()
    if ($Serial) { $fullArguments += @('-s', $Serial) }
    $fullArguments += @('install', '-r', $Apk)
    $stdoutPath = [IO.Path]::GetTempFileName()
    $stderrPath = [IO.Path]::GetTempFileName()
    try {
        $process = Start-Process -FilePath $script:AdbPath -ArgumentList $fullArguments -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
        $stdout = if (Test-Path -LiteralPath $stdoutPath) { [IO.File]::ReadAllText($stdoutPath) } else { '' }
        $stderr = if (Test-Path -LiteralPath $stderrPath) { [IO.File]::ReadAllText($stderrPath) } else { '' }
        [pscustomobject]@{ ExitCode = $process.ExitCode; Output = ($stdout + $stderr) }
    } finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function Fail-Gate {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Error "VIVO_PERMISSION_GATE_FAIL  $Message"
    exit 1
}

try {
    $script:AdbPath = Resolve-AdbPath
    Write-Output "adb         $script:AdbPath"
    Write-Output "package     $Package"
    Write-Output "permission  $Permission"

    $deviceResult = Invoke-DeviceAdb @('devices')
    $devices = @(
        $deviceResult.Output -split "`r?`n" |
            Where-Object { $_ -match '^\s*\S+\s+device\s*$' } |
            ForEach-Object { ($_ -split '\s+')[0] }
    )
    if ($devices.Count -eq 0) { Fail-Gate '没有已授权的 Android 真机。请连接手机并确认 USB 调试授权。' }
    if ($devices.Count -gt 1 -and -not $Serial) { Fail-Gate ("检测到多台设备（{0}），请使用 -Serial 指定目标设备。" -f ($devices -join ', ')) }
    if ($Serial -and $devices -notcontains $Serial) { Fail-Gate "指定的设备 $Serial 不在已连接设备列表中。" }
    $target = if ($Serial) { $Serial } else { $devices[0] }
    Write-Output "device      $target"

    if ($ApkPath) {
        $apk = (Resolve-Path -LiteralPath $ApkPath -ErrorAction Stop).Path
        Write-Output "apk         $apk"
        $install = Invoke-AdbInstall -Apk $apk
        if ($install.ExitCode -ne 0) { Fail-Gate "APK 覆盖安装失败：$($install.Output.Trim())" }
        Write-Output 'install     PASS (adb install -r)'
    }

    $installed = Invoke-DeviceAdb @('shell', 'pm', 'path', $Package)
    if ($installed.ExitCode -ne 0 -or $installed.Output -notmatch 'package:') { Fail-Gate "$Package 未安装。" }

    $providerDump = Invoke-DeviceAdb @('shell', 'dumpsys', 'package', 'providers')
    foreach ($authority in $ProviderAuthorities) {
        if ($providerDump.Output -notmatch [regex]::Escape($authority)) { Fail-Gate "Provider $authority 不存在，当前设备不支持此读取路径。" }
    }
    Write-Output "providers   PASS ($($ProviderAuthorities -join ', '))"

    function Get-PrimaryPermissionState {
        $dump = Invoke-DeviceAdb @('shell', 'dumpsys', 'package', $Package)
        $pattern = '^\s*' + [regex]::Escape($Permission) + ':\s+granted=(true|false)\b'
        $primary = @(
            $dump.Output -split "`r?`n" |
                Where-Object { $_ -match $pattern -and $_ -notmatch 'userId=' }
        )
        if ($primary.Count -eq 0) { return $false }
        return ($primary[0] -match 'granted=true')
    }

    $granted = Get-PrimaryPermissionState
    if (-not $granted -and $RepairPermission) {
        Write-Output 'grant       attempting ADB grant'
        $grant = Invoke-DeviceAdb @('shell', 'pm', 'grant', $Package, $Permission)
        if ($grant.ExitCode -ne 0) { Fail-Gate "ADB 授权命令失败：$($grant.Output.Trim())" }
        $granted = Get-PrimaryPermissionState
    }
    if (-not $granted) { Fail-Gate "$Permission 未对主用户授权。可在本人设备上重试并加 -RepairPermission。" }

    Write-Output "permission  PASS ($Permission granted=true)"
    Write-Output 'VIVO_PERMISSION_GATE_PASS  可以进入后续发布流程。'
    exit 0
} catch {
    Write-Error "VIVO_PERMISSION_GATE_FAIL  $($_.Exception.Message)"
    exit 1
}
