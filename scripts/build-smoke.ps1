[CmdletBinding()]
param(
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$artifactDir = Join-Path $projectRoot 'artifacts/package-smoke'
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null

pyside6-deploy -c deployment/pysidedeploy.spec -f
if ($LASTEXITCODE -ne 0) { throw "pyside6-deploy failed with exit code $LASTEXITCODE" }

$artifact = Get-ChildItem -Path $artifactDir -Filter 'MatterContext.exe' -File -Recurse |
    Select-Object -First 1

# pyside6-deploy may resolve exec_directory relative to the deployment source
# directory on some PySide6 versions. Fall back to the deployment tree so the
# smoke test verifies the produced executable instead of failing on path layout.
if ($null -eq $artifact) {
    $artifact = Get-ChildItem -Path (Join-Path $projectRoot 'deployment') -Filter 'MatterContext.exe' -File -Recurse |
        Select-Object -First 1
}

if ($null -eq $artifact) { throw 'Standalone MatterContext.exe was not produced.' }

$stdoutPath = Join-Path $artifactDir 'MatterContext-smoke.stdout.log'
$stderrPath = Join-Path $artifactDir 'MatterContext-smoke.stderr.log'
$process = Start-Process -FilePath $artifact.FullName -ArgumentList '--smoke-test' -PassThru `
    -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath

function Write-SmokeLogs {
    foreach ($stream in @(
        @{ Name = 'stdout'; Path = $stdoutPath },
        @{ Name = 'stderr'; Path = $stderrPath }
    )) {
        if (Test-Path -LiteralPath $stream.Path) {
            Write-Host "--- Packaged smoke test $($stream.Name) ---"
            Get-Content -LiteralPath $stream.Path
        }
    }
}

if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    Stop-Process -Id $process.Id -Force
    $process.WaitForExit()
    Write-SmokeLogs
    throw "Packaged smoke test exceeded $TimeoutSeconds seconds."
}
if ($process.ExitCode -ne 0) {
    Write-SmokeLogs
    throw "Packaged smoke test failed with exit code $($process.ExitCode)."
}
