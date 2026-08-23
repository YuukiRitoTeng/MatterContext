[CmdletBinding()]
param(
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

pyside6-deploy -c deployment/pysidedeploy.spec -f
if ($LASTEXITCODE -ne 0) { throw "pyside6-deploy failed with exit code $LASTEXITCODE" }

$artifact = Get-ChildItem -Path (Join-Path $projectRoot 'artifacts/package-smoke') -Filter 'MatterContext.exe' -File -Recurse |
    Select-Object -First 1
if ($null -eq $artifact) { throw 'Standalone MatterContext.exe was not produced.' }

$process = Start-Process -FilePath $artifact.FullName -ArgumentList '--smoke-test' -PassThru
if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    Stop-Process -Id $process.Id -Force
    throw "Packaged smoke test exceeded $TimeoutSeconds seconds."
}
if ($process.ExitCode -ne 0) { throw "Packaged smoke test failed with exit code $($process.ExitCode)." }
