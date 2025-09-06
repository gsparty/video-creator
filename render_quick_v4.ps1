# render_quick_v4.ps1
# Fixed: proper audio-existence check & safe escaping of Windows paths for ffmpeg subtitles filter.
# Run from C:\auto_video_agent
# Requires: ffmpeg on PATH. ImageMagick (magick) optional.

function New-TTSWav {
  param([string]$text,[string]$wavPath)
  $dir = Split-Path $wavPath -Parent
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  try {
    $stream = New-Object -ComObject SAPI.SpFileStream
    $voice  = New-Object -ComObject SAPI.SpVoice
    $SSFMCreateForWrite = 3
    $streamMode = [uint32]$SSFMCreateForWrite
    $stream.Open($wavPath, $streamMode)
    $voice.AudioOutputStream = $stream
    $voice.Rate = 0
    $voice.Volume = 100
    $voice.Speak($text) | Out-Null
    $stream.Close()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($voice) | Out-Null
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($stream) | Out-Null
    return $true
  } catch {
    Write-Warning "TTS generation failed (COM). $_"
    try { if ($stream) { $stream.Close() } } catch {}
    return $false
  }
}

# Config + manifest
$manifest = ".\manifest.csv"
if (-not (Test-Path $manifest)) { Write-Error "manifest.csv missing; run the manifest builder first."; exit 1 }
$rows = Import-Csv $manifest

$baseTmp = (Resolve-Path ".\tmp" -ErrorAction SilentlyContinue)
if (-not $baseTmp) { New-Item -ItemType Directory -Path ".\tmp" | Out-Null; $baseTmp = (Resolve-Path ".\tmp") }
$rendersRoot = Join-Path $baseTmp "renders"
New-Item -ItemType Directory -Path $rendersRoot -Force | Out-Null

$assStyle = "FontName=Arial,FontSize=36,BorderStyle=1,Outline=2,Shadow=0,MarginL=120,MarginR=120,MarginV=48,PrimaryColour=&H00FFFFFF&,BackColour=&H00000000&,Alignment=2"
$videoW = 1080; $videoH = 1920

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Error "ffmpeg not found on PATH. Please install ffmpeg and re-run."
  exit 1
}

$success=0; $fail=0
foreach ($row in $rows) {
  $id = $row.id
  $theme = ($row.theme -replace "`r|`n"," ").Trim()
  Write-Host "`n---- Processing $id : $theme ----"

  $itemDir = Join-Path $rendersRoot ("trend_" + $id)
  $itemOut = Join-Path $itemDir "outputs"
  New-Item -ItemType Directory -Path $itemDir -Force | Out-Null
  New-Item -ItemType Directory -Path $itemOut -Force | Out-Null

  $bg = if ($row.background) { ($row.background -replace '\\','/') } else { $null }
  $audio = if ($row.audio) { ($row.audio -replace '\\','/') } else { $null }
  $srt = if ($row.srt) { ($row.srt -replace '\\','/') } else { $null }

  # fallback background
  if (-not $bg -or -not (Test-Path $bg)) {
    $cand = Resolve-Path ".\background.jpg" -ErrorAction SilentlyContinue
    if ($cand) { $bg = $cand.Path -replace '\\','/' }
    else {
      $fallback = Join-Path $itemDir "fallback_bg.jpg"
      if (-not (Test-Path $fallback)) {
        if (Get-Command magick -ErrorAction SilentlyContinue) {
          magick -size "${videoW}x${videoH}" xc:black $fallback
        } else {
          # create a minimal black jpg so ffmpeg has something (ImageMagick missing -> we'll touch file)
          $bytes = [System.Convert]::FromBase64String("...") # not required; we'll touch an empty file
          New-Item -ItemType File -Path $fallback | Out-Null
        }
      }
      $bg = (Resolve-Path $fallback).Path -replace '\\','/'
    }
  }

  # audio existence / size check (fixed boolean logic)
  $ttsWav = Join-Path $itemDir ("tts_" + $id + ".wav")
  $ttsM4a = Join-Path $itemDir ("tts_" + $id + ".m4a")
  $generateTTS = $false
  if (-not $audio -or -not (Test-Path $audio) -or ((Get-Item $audio).Length -lt 200)) {
    $generateTTS = $true
  }

  if ($generateTTS) {
    Write-Host "Manifest audio appears missing/placeholder -> generating TTS for $id"
    $ok = New-TTSWav -text $theme -wavPath $ttsWav
    if ($ok -and (Test-Path $ttsWav)) {
      & ffmpeg -y -i $ttsWav -c:a aac -b:a 128k -ar 24000 $ttsM4a 2>&1 | Out-Null
      if (Test-Path $ttsM4a) { $audio = $ttsM4a } else { Write-Warning "Failed to convert TTS wav -> m4a for $id" }
    } else {
      Write-Warning "Failed to create TTS WAV for $id"
    }
  }

  # ensure an SRT exists (simple single-cue 8s)
  if (-not $srt -or -not (Test-Path $srt)) {
    $srt = Join-Path $itemDir ("trend_" + $id + ".wrapped.srt")
    $durationSec = 8
    $endTs = [TimeSpan]::FromSeconds($durationSec)
    $end = "{0:00}:{1:00}:{2:00},{3:000}" -f $endTs.Hours,$endTs.Minutes,$endTs.Seconds,$endTs.Milliseconds
    $srtContent = "1`r`n00:00:00,000 --> $end`r`n$theme`r`n"
    $srtContent | Out-File -FilePath $srt -Encoding UTF8
  }

  # rounded box
  $boxWidth = 760
  $boxHeight = [int]([Math]::Round($boxWidth * 0.9))
  $radius = [int]([Math]::Round($boxWidth * 0.05))
  $boxPng = Join-Path $itemDir "rounded_box.png"
  if (-not (Test-Path $boxPng)) {
    if (Get-Command magick -ErrorAction SilentlyContinue) {
      $fill = "rgba(0,0,0,0.35)"
      magick -size ("{0}x{1}" -f $boxWidth,$boxHeight) xc:none -fill $fill -draw ("roundrectangle 0,0,$($boxWidth-1),$($boxHeight-1),$radius,$radius") $boxPng
    } else {
      Write-Warning "magick not found; skipping rounded box creation."
    }
  }

  # ---------- Stage 1 ----------
  $intermediate = Join-Path $itemOut ("stage1_" + $id + ".mp4")
  $log1 = Join-Path $itemOut ("ffmpeg_stage1_" + $id + ".log")
  $filter1 = "[0:v]scale=${videoW}:${videoH}:force_original_aspect_ratio=decrease,pad=${videoW}:${videoH}:(ow-iw)/2:(oh-ih)/2,format=rgba[bg];" +
             "[1:v]scale=${boxWidth}:-1,format=rgba[box];" +
             "[bg][box]overlay=x=(W-w)/2:y=(H-h)/2[tmp]"

  $args1 = @(
    "-y",
    "-loop","1","-i",$bg,
    "-i",$boxPng,
    "-i",$audio,
    "-t","8",
    "-filter_complex",$filter1,
    "-map","[tmp]",
    "-map","2:a",
    "-c:v","libx264","-preset","medium","-crf","18",
    "-c:a","aac","-b:a","128k",
    "-shortest",
    $intermediate
  )

  Write-Host "Stage1 -> $intermediate"
  & ffmpeg @args1 2>&1 | Tee-Object -FilePath $log1

  if (-not (Test-Path $intermediate)) {
    Write-Warning "Stage1 failed for $id (see $log1)"; $fail++; continue
  }

  # ---------- Stage 2: burn subtitles (escape Windows ':' in path for ffmpeg subtitles filter) ----------
  $final = Join-Path $itemOut ("final_" + $id + ".mp4")
  $log2 = Join-Path $itemOut ("ffmpeg_stage2_" + $id + ".log")

  $srtForFf = ($srt -replace '\\','/')   # forward slashes
  # Escape any ':' characters so ffmpeg doesn't interpret them as option separators (e.g. drive letter)
  $srtEsc = $srtForFf -replace ':','\:'

  $vf = "subtitles='$srtEsc':force_style='$assStyle'"
  Write-Host "Stage2 vf -> $vf"

  $args2 = @(
    "-y",
    "-i",$intermediate,
    "-vf",$vf,
    "-c:v","libx264","-preset","medium","-crf","18",
    "-c:a","copy",
    $final
  )

  & ffmpeg @args2 2>&1 | Tee-Object -FilePath $log2

  if (Test-Path $final) {
    Write-Host "✅ Rendered: $final"
    $success++
  } else {
    Write-Warning "Stage2 failed for $id (see $log2)"
    $fail++
  }
}

Write-Host "`nDone. Success: $success, Failed: $fail"
