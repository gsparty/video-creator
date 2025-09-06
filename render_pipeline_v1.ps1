# render_pipeline_v1.ps1
# Run from C:\auto_video_agent
# Requires: ffmpeg on PATH. ImageMagick (magick) optional.
# Generates TTS using Windows SAPI, converts to m4a, mixes optional sfx, renders MP4 per manifest.

$manifest = ".\manifest.csv"
if (-not (Test-Path $manifest)) {
  Write-Error "manifest.csv missing; run the manifest builder first."
  exit 1
}

# check ffmpeg
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Error "ffmpeg not found on PATH. Please install ffmpeg and re-run."
  exit 1
}

# create central outputs folder
$centralOutputs = Join-Path (Get-Location) "outputs"
New-Item -ItemType Directory -Path $centralOutputs -Force | Out-Null

$rows = Import-Csv $manifest

# Basic ASS style for subtitles (change to taste)
$assStyle = 'FontName=Arial,FontSize=36,BorderStyle=1,Outline=2,Shadow=0,MarginL=120,MarginR=120,MarginV=48,PrimaryColour=&H00FFFFFF&,BackColour=&H00000000&,Alignment=2'

# helper to create TTS wav via Windows SAPI
function New-TTSWav {
  param(
    [string]$text,
    [string]$wavPath
  )
  $ss = New-Object -TypeName System.Speech.Synthesis.SpeechSynthesizer
  try {
    $ss.Rate = 0    # adjust speaking rate
    $ss.Volume = 100
    $ss.SetOutputToWaveFile($wavPath)
    $ss.Speak($text)
  } finally {
    $ss.SetOutputToNull()
    $ss.Dispose()
  }
}

$success = 0; $fail = 0

foreach ($row in $rows) {
  $id = $row.id
  $theme = $row.theme.Trim()
  if (-not $theme) { $theme = "Trend $id" }
  Write-Host "`n---- Processing $id : $theme ----"

  # Work dirs
  $workDir = Join-Path (Resolve-Path ".\tmp").Path ("render_trend_" + $id)
  New-Item -ItemType Directory -Path $workDir -Force | Out-Null
  $itemOutputs = Join-Path $workDir "outputs"
  New-Item -ItemType Directory -Path $itemOutputs -Force | Out-Null

  # Normalize manifest paths (if they exist)
  $bg = $row.background
  if ($bg) { $bg = (Resolve-Path $bg -ErrorAction SilentlyContinue).Path -replace '\\','/' }
  $srt = $row.srt
  if ($srt) { $srt = (Resolve-Path $srt -ErrorAction SilentlyContinue).Path -replace '\\','/' }
  $audio = $row.audio
  if ($audio) { $audio = (Resolve-Path $audio -ErrorAction SilentlyContinue).Path -replace '\\','/' }
  # optional SFX column name: sfx
  $sfx = $null
  if ($row.PSObject.Properties.Name -contains 'sfx') {
    $sfx = $row.sfx
    if ($sfx) { $sfx = (Resolve-Path $sfx -ErrorAction SilentlyContinue).Path -replace '\\','/' }
  }

  # fallback background if missing
  if (-not $bg) {
    $fallback = (Resolve-Path ".\background.jpg" -ErrorAction SilentlyContinue)
    if ($fallback) { $bg = $fallback.Path -replace '\\','/' }
  }

  # File names
  $ttsWav = Join-Path $workDir ("tts_" + $id + ".wav")
  $ttsM4a = Join-Path $workDir ("tts_" + $id + ".m4a")
  $mixedAudio = Join-Path $workDir ("audio_mixed_" + $id + ".m4a")
  $boxPng = Join-Path $workDir "rounded_box.png"
  $outMp4 = Join-Path $itemOutputs ("final_" + $id + ".mp4")
  $logFile = Join-Path $itemOutputs ("ffmpeg_" + $id + ".log")

  # Create TTS if no real audio exists or the file is a "silent" placeholder
  $needTts = $true
  if ($audio -and (Test-Path $audio)) {
    # if the manifest audio path exists and it's not obviously the silent placeholder, reuse it
    # heuristic: if filename contains "silent" treat as placeholder
    if ($audio -notmatch '(?i)silent') {
      Write-Host "Using existing audio from manifest: $audio"
      Copy-Item -Path $audio -Destination $ttsM4a -Force
      $needTts = $false
    } else {
      Write-Host "Manifest audio appears to be silent placeholder -> will generate TTS"
    }
  }

  if ($needTts) {
    Write-Host "Generating TTS WAV for id $id ..."
    New-TTSWav -text $theme -wavPath $ttsWav
    # convert wav -> m4a
    Write-Host "Converting WAV -> m4a..."
    & ffmpeg -y -hide_banner -loglevel error -i $ttsWav -c:a aac -b:a 128k $ttsM4a
    if (-not (Test-Path $ttsM4a)) {
      Write-Warning "Failed to create tts m4a for $id"
      $fail++; continue
    }
  }

  # If there's SFX, mix tts m4a + sfx -> $mixedAudio; else use $ttsM4a as final audio
  $finalAudio = $ttsM4a
  if ($sfx -and (Test-Path $sfx)) {
    Write-Host "Mixing TTS + SFX..."
    # simple amix: keep longest duration, scale volume weights if needed
    & ffmpeg -y -hide_banner -loglevel error -i $ttsM4a -i $sfx -filter_complex "amix=inputs=2:duration=longest:dropout_transition=2" -c:a aac -b:a 128k $mixedAudio
    if (Test-Path $mixedAudio) {
      $finalAudio = $mixedAudio
    } else {
      Write-Warning "SFX mixing failed; falling back to TTS only"
      $finalAudio = $ttsM4a
    }
  }

  # Ensure we have SRT; if missing, create a simple single-cue SRT from the theme (so subtitles show)
  if (-not $srt -or -not (Test-Path $srt)) {
    Write-Host "SRT missing; creating a simple single-cue SRT for the full audio duration..."
    # compute audio duration via ffprobe
    $audioDuration = 8
    try {
      $probe = & ffmpeg -i $finalAudio 2>&1 | Select-String "Duration"
      if ($probe) {
        $line = ($probe -join "`n")
        # attempt parse HH:MM:SS.mmm
        if ($line -match "Duration:\s+(\d+:\d+:\d+\.\d+)") {
          $audioDuration = [timespan]::Parse($matches[1]).TotalSeconds
        }
      }
    } catch {}
    $tsTotal = [TimeSpan]::FromSeconds([Math]::Max(1,[Math]::Round($audioDuration)))
    $start = "00:00:00,000"
    $end = "{0:00}:{1:00}:{2:00},{3:000}" -f $tsTotal.Hours,$tsTotal.Minutes,$tsTotal.Seconds,$tsTotal.Milliseconds
    $wrapped = $theme
    # optional wrapping: insert newlines every ~40 chars
    function Wrap-Text([string]$text,[int]$max=40){
      $words=$text -split '\s+'; $line=""; $out=@()
      foreach($w in $words){ if(($line.Length+$w.Length+1) -le $max){ if($line -eq ""){$line=$w} else{$line="$line $w"} } else{ $out+=$line; $line=$w } }
      if($line -ne ""){$out+=$line}; return ($out -join "`r`n")
    }
    $wrapped = Wrap-Text $theme 40
    $srt = Join-Path $workDir ("auto_" + $id + ".srt")
    $srtContent = "1`r`n$start --> $end`r`n$wrapped`r`n"
    $srtContent | Out-File -FilePath $srt -Encoding UTF8
  }

  # Create rounded box PNG if magick available (used as translucent panel)
  if (-not (Test-Path $boxPng)) {
    if (Get-Command magick -ErrorAction SilentlyContinue) {
      $boxWidth = 760; $boxHeight = [int]([Math]::Round($boxWidth * 0.9)); $radius = [int]([Math]::Round($boxWidth*0.05))
      $fill = "rgba(0,0,0,0.35)"
      $draw = "roundrectangle 0,0,$($boxWidth-1),$($boxHeight-1),$radius,$radius"
      magick -size ("{0}x{1}" -f $boxWidth,$boxHeight) xc:none -fill $fill -draw $draw $boxPng
      Write-Host "Created box: $boxPng"
    } else {
      Write-Host "magick not found; skipping box creation. Provide $boxPng if you want the panel."
    }
  } else {
    Write-Host "Using existing box: $boxPng"
  }

  # verify inputs exist
  $missing = @()
  if (-not $bg) { $missing += "background (missing)" }
  if (-not (Test-Path $finalAudio)) { $missing += "audio ($finalAudio missing)" }
  if (-not (Test-Path $srt)) { $missing += "srt ($srt missing)" }
  if (-not (Test-Path $boxPng)) { Write-Host "warning: box png missing; continuing without panel" } 

  if ($missing.Count -gt 0) {
    Write-Warning ("Skipping {0} : {1}" -f $id, ($missing -join ', '))
    $fail++; continue
  }

  # Escape : in SRT path for ffmpeg subtitles filter
  $srtForFilter = $srt -replace ':','\:'

  # Build filter_complex. We keep it minimal: scale background to 1080x1920, pad, overlay (box centered), subtitles.
  $filter = @"
[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=rgba[bg];
[1:v]scale=760:-1,format=rgba[box];
[bg][box]overlay=x=(W-w)/2:y=(H-h)/2[tmp];
[tmp]subtitles='$srtForFilter':force_style='$assStyle'[v]
"@.Trim()

  # build ffmpeg args. Map video from filter [v], audio from finalAudio
  $args = @(
    "-y",
    "-loop","1","-i",$bg,
    "-i",$boxPng,
    "-i",$finalAudio,
    "-filter_complex",$filter,
    "-map","[v]",
    "-map","2:a",
    "-c:v","libx264","-preset","medium","-crf","18",
    "-c:a","aac","-b:a","128k",
    "-shortest",
    $outMp4
  )

  Write-Host ("Rendering -> {0}" -f $outMp4)
  try {
    & ffmpeg @args 2>&1 | Tee-Object -FilePath $logFile
    if (Test-Path $outMp4) {
      Write-Host ("✅ Rendered: {0}" -f $outMp4)
      # copy to central outputs (final_<id>.mp4)
      $centralDst = Join-Path $centralOutputs ("final_" + $id + ".mp4")
      Copy-Item -Path $outMp4 -Destination $centralDst -Force
      Write-Host ("--> copied to {0}" -f $centralDst)
      $success++
    } else {
      Write-Warning ("ffmpeg finished but output missing for {0}. Check log: {1}" -f $id, $logFile)
      $fail++
    }
  } catch {
    Write-Warning ("Error rendering {0}: {1}" -f $id, $_.Exception.Message)
    $fail++
  }
}

Write-Host "`nDone. Success: $success, Failed: $fail"
Write-Host ("All saved outputs (central): {0}" -f $centralOutputs)
