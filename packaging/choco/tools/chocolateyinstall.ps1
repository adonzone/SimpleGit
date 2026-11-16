$ErrorActionPreference = 'Stop'

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$url64 = 'https://github.com/adonzone/SimpleGit/releases/download/v0.1.0/sgit-win32-x64.exe'
$checksum64 = 'REPLACE_WITH_WIN32_X64_SHA256'
$targetExe = Join-Path $toolsDir 'sgit.exe'

Get-ChocolateyWebFile `
  -PackageName 'simplegit' `
  -FileFullPath $targetExe `
  -Url64bit $url64 `
  -Checksum64 $checksum64 `
  -ChecksumType64 'sha256'
