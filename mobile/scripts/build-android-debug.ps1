[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$JavaHome,

    [string]$AndroidHome = (Join-Path $env:LOCALAPPDATA "Android\Sdk"),

    [string]$LogDirectory = (Join-Path $env:TEMP "healthevent-android-build")
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
$launcherLog = Join-Path $LogDirectory "launcher.log"
$buildExitCode = 1
Start-Transcript -Path $launcherLog -Force | Out-Null

try {
    if (-not (Test-Path -LiteralPath (Join-Path $JavaHome "bin\java.exe"))) {
        throw "JavaHome does not contain bin\java.exe: $JavaHome"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $AndroidHome "platforms\android-36\android.jar"))) {
        throw "AndroidHome does not contain Android API 36: $AndroidHome"
    }

    $androidProject = (Resolve-Path (Join-Path $PSScriptRoot "..\android")).Path
    $gradleWrapper = Join-Path $androidProject "gradlew.bat"
    $standardOutput = Join-Path $LogDirectory "assemble-debug.out.log"
    $standardError = Join-Path $LogDirectory "assemble-debug.err.log"

    $env:JAVA_HOME = (Resolve-Path -LiteralPath $JavaHome).Path
    $env:ANDROID_HOME = (Resolve-Path -LiteralPath $AndroidHome).Path

    $buildProcess = Start-Process `
        -FilePath $gradleWrapper `
        -ArgumentList "--no-daemon", "assembleDebug" `
        -WorkingDirectory $androidProject `
        -WindowStyle Hidden `
        -RedirectStandardOutput $standardOutput `
        -RedirectStandardError $standardError `
        -Wait `
        -PassThru

    $buildExitCode = $buildProcess.ExitCode
} catch {
    Write-Error $_
} finally {
    Stop-Transcript | Out-Null
}

exit $buildExitCode
