# Run from ai/ directory. Does not install or download models.
param([string]$Python = "python")

$ErrorActionPreference = "Stop"
Write-Host "RoleReady hardware inventory" -ForegroundColor Cyan
& $Python --version
Get-CimInstance Win32_Processor | Format-List Name,NumberOfCores,NumberOfLogicalProcessors
Get-CimInstance Win32_ComputerSystem | Select-Object @{Name="RAM_GiB";Expression={[math]::Round($_.TotalPhysicalMemory/1GB,2)}} | Format-List
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
} else {
  Get-CimInstance Win32_VideoController | Format-List Name
}
Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | Select-Object DeviceID,@{Name="SizeGiB";Expression={[math]::Round($_.Size/1GB,1)}},@{Name="FreeGiB";Expression={[math]::Round($_.FreeSpace/1GB,1)}} | Format-Table
& $Python -m pip check
if ($LASTEXITCODE -ne 0) { throw "Python dependency check failed" }
& $Python -c "import torch; print('PyTorch:', torch.__version__, 'CUDA build:', torch.version.cuda, 'CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'unavailable'); print('CUDA tensor sum:', torch.ones(8, device='cuda').sum().item() if torch.cuda.is_available() else 'not run')"
if ($LASTEXITCODE -ne 0) { throw "PyTorch runtime check failed" }
& $Python -m roleready_ai.readiness
if ($LASTEXITCODE -ne 0) { throw "Model dependency inventory failed" }
