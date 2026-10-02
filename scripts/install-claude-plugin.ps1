#requires -Version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    throw 'Install Claude Code first. See https://code.claude.com/docs/en/setup'
}
& claude plugin marketplace add Visualsectors/systematic-trading-toolkit
if ($LASTEXITCODE -ne 0) { throw 'Marketplace registration failed; plugin was not installed.' }
& claude plugin install systematic-trading-toolkit@visualsectors --scope project
if ($LASTEXITCODE -ne 0) { throw 'Plugin installation failed.' }
Write-Host 'Installed six skills in project scope. Restart Claude Code. Python toolkit installation is separate; see README.md.'
