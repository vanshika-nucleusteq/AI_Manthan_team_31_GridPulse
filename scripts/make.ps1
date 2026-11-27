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
$Compose = @("compose", "--env-file", ".env", "-f", "deploy/docker-compose.yml")
function Invoke-Compose([string[]]$ComposeArgs) { Invoke-Step "docker" ($Compose + $ComposeArgs) }
function Initialize-Env { Invoke-Step "py" @("-3", "scripts/init_env.py") }
$Args2 = @($Rest | Where-Object { $_ })

switch ($Target) {
    "venv" {
        Invoke-Step "py" @("-3.12", "-m", "venv", ".venv")
        Invoke-Step $Py @("-m", "pip", "install", "--upgrade", "pip")
        Invoke-Step $Py @("-m", "pip", "install", "-e", ".[dev]")
    }
    "lint" { Invoke-Lint }
    "test" { Invoke-Test }
    "check" { Invoke-Lint; Invoke-Test }
    "generate" { Invoke-Step $Py (@("-m", "gridpulse.generator") + $Args2) }
    "up" {
        Initialize-Env
        Invoke-Compose @("up", "-d", "--build", "--wait")
        Invoke-Compose @("ps")
        Write-Output "Airflow: http://localhost:8080   Streamlit: http://localhost:8501"
    }
    "down" { Invoke-Compose @("down") }
    "reset" { Invoke-Compose @("down", "--volumes", "--remove-orphans") }
    "logs" { Invoke-Compose (@("logs", "--tail", "200") + $Args2) }
    "seed" { Initialize-Env; Invoke-Compose @("run", "--rm", "gridpulse-init") }
    { $_ -in @("run-day", "backfill", "rollback") } { Write-Output "TODO: built in P8" }
    default {
        Write-Output "Targets: venv lint test check generate up down reset logs seed run-day backfill rollback"
        if ($Target -ne "help") { exit 1 }
    }
}
