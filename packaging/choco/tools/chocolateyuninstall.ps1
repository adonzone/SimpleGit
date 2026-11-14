$ErrorActionPreference = 'Stop'

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$targetExe = Join-Path $toolsDir 'sgit.exe'
if (Test-Path $targetExe) {
  Remove-Item $targetExe -Force
}
