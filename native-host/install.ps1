# PowerShell script to install Geo Monitor Doubao Native Host on Windows
# Run in PowerShell (as normal user, writes to HKCU)

$BridgePy = "\\wsl$\Ubuntu-24.04\home\eric\geo-monitor\native-host\doubao_bridge.py"
$PythonExe = "C:\Users\NINGMEI\AppData\Local\Python\bin\python.exe"
$ManifestDir = "$env:LOCALAPPDATA\GeoMonitorDoubao"
$ManifestFile = "$ManifestDir\com.geo-monitor.doubao.json"

mkdir -Force $ManifestDir | Out-Null

# Create batch wrapper that calls the bridge
$BatFile = "$ManifestDir\doubao_bridge.bat"
@"
@echo off
$PythonExe "$BridgePy"
"@ | Out-File -Encoding ASCII $BatFile

# Create native messaging manifest
@"
{
  "name": "com.geo-monitor.doubao",
  "description": "Geo Monitor Doubao Bridge",
  "path": "$($BatFile -replace '\\', '\\')",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://*"
  ]
}
"@ | Out-File -Encoding UTF8 $ManifestFile

# Register via Registry
$RegPath = "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.geo-monitor.doubao"
New-Item -Path $RegPath -Force | Out-Null
Set-ItemProperty -Path $RegPath -Name "(Default)" -Value $ManifestFile

Write-Host "✅ Geo Monitor Doubao Native Host installed"
Write-Host "   Manifest: $ManifestFile"
Write-Host "   Registry: $RegPath"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Load doubao-ext/ as unpacked extension in chrome://extensions"
Write-Host "  2. Reload the extension"
Write-Host "  3. Test: python3 native-host/doubao_cli.py '{\"action\":\"ping\"}'"
