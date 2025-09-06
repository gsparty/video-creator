# overlay_all.ps1
# Usage: .\overlay_all.ps1
# or:  .\overlay_all.ps1 -InputDir .\outputs -Overwrite $true

param(
    [string]$InputDir = ".\outputs",
    [switch]$Overwrite
)

if (-not (Test-Path $InputDir)) {
    Write-Host "InputDir not found: $InputDir"
    exit 1
}

$py = "C:\auto_video_agent\venv\Scripts\python.exe"  # adjust if different
if (-not (Test-Path $py)) {
    Write-Host "Python not found at $py - adjust variable in script"
    exit 1
}

Get-ChildItem -Path $InputDir -Filter "*.mp4" | ForEach-Object {
    $infile = $_.FullName
    $base = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
    # derive a readable headline from the filename (remove leading number tokens and underscores/dashes)
    $headline = $base -replace "^\d+[_\-\s]*", "" -replace "_", " " -replace "-", " "
    if ([string]::IsNullOrWhiteSpace($headline)) { $headline = "Top Trend" }

    $overlayPng = Join-Path $InputDir ("overlay_" + ($base -replace '[^0-9A-Za-z\-]','') + ".png")
    $outfile = Join-Path $InputDir ($base + "_with_overlay.mp4")

    Write-Host "Processing: $infile"
    Write-Host " -> Headline: $headline"
    Write-Host " -> Overlay: $overlayPng"
    Write-Host " -> Out: $outfile"

    # generate overlay PNG
    & $py .\overlay_png.py $headline $overlayPng 1080 1920 120

    if (-not (Test-Path $overlayPng)) {
        Write-Host "Failed to create overlay PNG for $infile"
        return
    }

    # composite with ffmpeg, center horizontally, place at 20% from top (adjust if desired)
    $overlayY = "(main_h-overlay_h)/6"
    $ffmpegCmd = "ffmpeg -y -i `"$infile`" -i `"$overlayPng`" -filter_complex `"overlay=(main_w-overlay_w)/2:$overlayY`" -c:v libx264 -crf 23 -preset medium -c:a aac `"$outfile`""
    Write-Host $ffmpegCmd
    iex $ffmpegCmd

    if ($Overwrite -or -not (Test-Path $outfile)) {
        Write-Host "OK -> $outfile"
    } else {
        Write-Host "Output exists and not overwritten: $outfile"
    }
}
