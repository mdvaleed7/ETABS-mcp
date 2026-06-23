$chmPath = "c:\Users\mdval\Desktop\etaps mcp\CSI API ETABS v1.chm"
$outDir = "c:\Users\mdval\Desktop\etaps mcp\extracted_docs"

# Clean and create output directory
if (Test-Path $outDir) { Remove-Item $outDir -Recurse -Force }
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

# Try using hh.exe with proper quoting
$proc = Start-Process -FilePath "hh.exe" -ArgumentList "-decompile `"$outDir`" `"$chmPath`"" -Wait -PassThru -NoNewWindow -ErrorAction SilentlyContinue

Start-Sleep -Seconds 2

$files = Get-ChildItem $outDir -Recurse
Write-Host "Extracted $($files.Count) files"
$files | Select-Object -First 30 | ForEach-Object { Write-Host $_.FullName }
