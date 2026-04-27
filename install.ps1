$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptsDir = Join-Path $env:APPDATA "Python\Python$((python --version 2>&1) -replace 'Python ', '' -replace '\..*', '')\Scripts"

Write-Host "Installing zephyr-tools in editable mode..." -ForegroundColor Cyan
& pip install -e "$RepoRoot"

if ($LASTEXITCODE -ne 0) {
    Write-Error "pip install failed"
    exit 1
}

$CurrentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($CurrentPath -notlike "*$ScriptsDir*") {
    Write-Host "Adding Python user Scripts directory to PATH..." -ForegroundColor Cyan
    [Environment]::SetEnvironmentVariable("Path", "$CurrentPath;$ScriptsDir", "User")
    Write-Host "PATH updated. Please restart your terminal for 'zt' to be available." -ForegroundColor Green
} else {
    Write-Host "Scripts directory already in PATH." -ForegroundColor Green
}

Write-Host ""
Write-Host "Installation complete. Run 'zt --version' after restarting your terminal." -ForegroundColor Green
