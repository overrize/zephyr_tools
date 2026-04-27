$ztDir = "E:\zephyr_Tool"
$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")

# Remove E:\zephyr_Tool from User PATH (clean up)
$userPath = ($userPath -split ';' | Where-Object { $_ -ne $ztDir }) -join ';'
[Environment]::SetEnvironmentVariable("Path", $userPath, "User")

# Add to Machine PATH if not present
if ($machinePath -notlike "*$ztDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$machinePath;$ztDir", "Machine")
    Write-Host "E:\zephyr_Tool added to Machine PATH." -ForegroundColor Green
} else {
    Write-Host "E:\zephyr_Tool already in Machine PATH." -ForegroundColor Green
}

Write-Host ""
Write-Host "Done. Restart your terminal and run: zt --version" -ForegroundColor Cyan
