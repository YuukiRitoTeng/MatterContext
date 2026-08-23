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

$process = Start-Process -FilePath $artifact.FullName -ArgumentList '--smoke-test' -PassThru
if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    Stop-Process -Id $process.Id -Force
    throw "Packaged smoke test exceeded $TimeoutSeconds seconds."
}
if ($process.ExitCode -ne 0) { throw "Packaged smoke test failed with exit code $($process.ExitCode)." }
