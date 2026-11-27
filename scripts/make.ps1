<#
.SYNOPSIS
  Windows replacement for the Makefile. Usage:
  powershell -ExecutionPolicy Bypass -File scripts/make.ps1 <target> [args]
#>
param(
    [Parameter(Position = 0)][string]$Target = "help",
    [Parameter(Position = 1, ValueFromRemainingArguments = $true)][string[]]$Rest
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$Py = Join-Path ".venv" "Scripts\python.exe"

function Invoke-Step([string]$Exe, [string[]]$StepArgs) {
    & $Exe @StepArgs
    if ($LASTEXITCODE -ne 0) { throw "Failed ($LASTEXITCODE): $Exe $($StepArgs -join ' ')" }
}
function Invoke-Lint {
    Invoke-Step $Py @("-m", "ruff", "check", ".")
    Invoke-Step $Py @("-m", "black", "--check", ".")
}
function Invoke-Test { Invoke-Step $Py @("-m", "pytest", "-q") }

switch ($Target) {
    "venv" {
        Invoke-Step "py" @("-3.12", "-m", "venv", ".venv")
        Invoke-Step $Py @("-m", "pip", "install", "--upgrade", "pip")
        Invoke-Step $Py @("-m", "pip", "install", "-e", ".[dev]")
    }
    "lint" { Invoke-Lint }
    "test" { Invoke-Test }
    "check" { Invoke-Lint; Invoke-Test }
    "generate" { Invoke-Step $Py (@("-m", "gridpulse.generator") + @($Rest | Where-Object { $_ })) }
    { $_ -in @("up", "down", "reset", "logs") } { Write-Output "TODO: built in P3" }
    { $_ -in @("run-day", "backfill", "rollback") } { Write-Output "TODO: built in P8" }
    default {
        Write-Output "Targets: venv lint test check generate up down reset logs run-day backfill rollback"
        if ($Target -ne "help") { exit 1 }
    }
}
