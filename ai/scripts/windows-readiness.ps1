# Run from ai/ directory. Does not install or download models.
$ErrorActionPreference = "Stop"
Write-Host "RoleReady hardware inventory" -ForegroundColor Cyan
python --version
Get-CimInstance Win32_ComputerSystem | Select-Object @{Name="RAM_GB";Expression={[math]::Round($_.TotalPhysicalMemory/1GB,1)}}
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
} else {
  Get-CimInstance Win32_VideoController | Select-Object Name
}
Get-PSDrive -PSProvider FileSystem | Select-Object Name,@{Name="FreeGB";Expression={[math]::Round($_.Free/1GB,1)}}
python -m roleready_ai.readiness
