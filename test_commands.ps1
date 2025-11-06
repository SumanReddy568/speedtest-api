# Base URL - change port from 10000 to 8000 since we mapped it
$BASE = "http://localhost:8000"

# 1. Test API Info
Write-Host "`nTesting API Info..."
curl.exe "$BASE/"

# 2. Test Ping
Write-Host "`nTesting Ping..."
curl.exe "$BASE/api/speedtest/ping"

# 3. Test Download Speed
Write-Host "`nTesting Download Speed (5MB)..."
$start = Get-Date
curl.exe "$BASE/api/speedtest/download?size_mb=5" -o nul
$duration = (Get-Date) - $start
$speed = (5 * 8) / $duration.TotalSeconds
Write-Host "Download Speed: $($speed.ToString('F2')) Mbps"

# 4. Test Upload Speed
Write-Host "`nTesting Upload Speed..."
# Create 5MB test file
$testFile = "testfile.bin"
$buffer = New-Object byte[] (5 * 1024 * 1024)
[System.IO.File]::WriteAllBytes($testFile, $buffer)
curl.exe -X POST -F "file=@$testFile" "$BASE/api/speedtest/upload"
Remove-Item $testFile

# 5. Get Network Info
Write-Host "`nGetting Network Info..."
curl.exe "$BASE/api/speedtest/network"
