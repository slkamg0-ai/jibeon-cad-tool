$ws = New-Object -ComObject WScript.Shell
$desktopPath = [System.Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktopPath "PC Monitor.lnk"
$sc = $ws.CreateShortcut($shortcutPath)
$sc.TargetPath = "c:\Users\slkam\Documents\pc-monitor\start.bat"
$sc.WorkingDirectory = "c:\Users\slkam\Documents\pc-monitor"
$sc.IconLocation = "c:\Users\slkam\Documents\pc-monitor\icon.ico,0"
$sc.Description = "PC Monitor Dashboard"
$sc.Save()
Write-Host "Shortcut created at: $shortcutPath"
