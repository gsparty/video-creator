# render_pipeline_v2.ps1
# Run from repo root (C:\auto_video_agent)
# Requires: ffmpeg on PATH. ImageMagick (magick) optional (for rounded box)

function New-TTSWav {
  param([string]$text,[string]$wavPath)
  $dir = Split-Path $wavPath -Parent
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  try {
    $stream = New-Object -ComObject SAPI.SpFileStream
    $voice  = New-Object -ComObject SAPI.SpVoice
    $SSFMCreateForWrite = 3
    $stream.Open($wavPath, [uint32]$SSFMCreateForWrite)
    $voice.AudioOutputStream = $stream
    $voice.Rate = 0; $voice.Volume = 100
    $voice.Speak($text) | Out-Null
    $stream.Close()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($voice) | Out-Null
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($stream) | Out-Null
    Write-Host "TTS created: $wavPath"
    return $true
  } catch {
    Write-Warning "TTS generation failed (COM). $_"
    try { if ($stream) { $stream.Close() } } catch {}
    return $false
  }
}

# ---------- CONFIG ----------
$manifest = ".\manifest.csv"
if (-not (Test-Path $manifest)) { Write-Error "manifest.csv missing; run the manifest builder first."; exit 1 }
$rows = Import-Csv $manifest

# Base outputs under tmp\renders
$baseTmp = (Resolve-Path ".\tmp" -ErrorAction SilentlyContinue)
if (-not $baseTmp) { New-Item -ItemType Directory -Path ".\tmp" | Out-Null; $baseTmp = (Resolve-Path ".\tmp") }
$absOutputsRoot = Join-Path $baseTmp "renders"
New-Item -ItemType Directory -Path $absOutputsRoot -Force | Out-Null

# Default ASS style (we will pass as force_style to subtitles filter)
$assStyle = "FontName=Arial,FontSize=32,BorderStyle=1,Outline=2,Shadow=0,MarginL=120,MarginR=120,MarginV=48,PrimaryColour=&H00FFFFFF&,BackColour=&H00000000&,Alignment=2"

# check ffmpeg
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Error "ffmpeg not found on PATH. Please install ffmpeg and re-run."
  exit 1
}

$success = 0; $fail = 0

foreach ($row in $rows) {
  $id = $row.id
  $theme = $row.theme
  $bg = ($row.background -replace '\\','/')  # manifest should provide absolute paths
  $audio = ($row.audio -replace '\\','/')
  $srt = ($row.srt -replace '\\','/')

  Write-Host ""
  Write-Host ("---- Processing {0} : {1} ----" -f $id, $theme)

  $itemWork = Join-Path $absOutputsRoot ("trend_" + $id)
  $itemOutputs = Join-Path $itemWork "outputs"
  New-Item -ItemType Directory -Path $itemWork -Force | Out-Null
  New-Item -ItemType Directory -Path $itemOutputs -Force | Out-Null

  $outFinal = Join-Path $itemOutputs ("final_" + $id + ".mp4")
  $outNoSubs = Join-Path $itemOutputs ("no_subs_" + $id + ".mp4")
  $logFile1 = Join-Path $itemOutputs ("ffmpeg_stage1_" + $id + ".log")
  $logFile2 = Join-Path $itemOutputs ("ffmpeg_stage2_" + $id + ".log")

  # box params (from manifest if present)
  $boxWidth = 760
  if ($row.box_width) { $boxWidth = [int]$row.box_width }
  $boxAlpha = 0.35
  if ($row.box_alpha) { $boxAlpha = [double]$row.box_alpha }

  $boxHeight = [int]([Math]::Round($boxWidth * 0.9))
  $radius = [int]([Math]::Round($boxWidth * 0.05))
  $boxPng = Join-Path $itemWork "rounded_box.png"

  # make rounded box if missing
  if (-not (Test-Path $boxPng)) {
    if (Get-Command magick -ErrorAction SilentlyContinue) {
      $fill = "rgba(0,0,0,$boxAlpha)"
      $draw = "roundrectangle 0,0,$($boxWidth-1),$($boxHeight-1),$radius,$radius"
      Write-Host ("Creating rounded box ({0}x{1}, alpha={2}) -> {3}" -f $boxWidth,$boxHeight,$boxAlpha,$boxPng)
      magick -size ("{0}x{1}" -f $boxWidth,$boxHeight) xc:none -fill $fill -draw $draw $boxPng
    } else {
      Write-Warning ("magick not found; skipping rounded box creation for {0}. Provide {1} manually if you want it." -f $id,$boxPng)
    }
  }

  # ---------- AUDIO: generate TTS if needed ----------
  $useAudio = $audio
  $shouldCreateTts = $false
  # detect "silent placeholder" by filename containing "silent" or if audio missing
  if (-not (Test-Path $audio) -or ($audio -match "silent")) { $shouldCreateTts = $true }
  if ($shouldCreateTts) {
    $wav = Join-Path $itemWork ("tts_" + $id + ".wav")
    $m4a = Join-Path $itemWork ("tts_" + $id + ".m4a")
    $ok = New-TTSWav -text $theme -wavPath $wav
    if ($ok -and (Test-Path $wav)) {
      Write-Host "Converting WAV -> m4a for $id ..."
      $ff = "ffmpeg"
      $args = @("-y","-i",$wav,"-c:a","aac","-b:a","128k",$m4a)
      try { & $ff @args 2>&1 | Out-Null } catch {}
      if (Test-Path $m4a) { $useAudio = $m4a; Write-Host "TTS m4a ready -> $useAudio" } else {
        Write-Warning "Failed to create m4a from $wav. Will attempt to use wav directly if supported.";
        if (Test-Path $wav) { $useAudio = $wav } else { Write-Warning "No usable audio for $id"; $useAudio = $null }
      }
    } else { Write-Warning "TTS not created for $id"; $useAudio = $null }
  }

  # ---------- VERIFY required inputs ----------
  $missing = @()
  if (-not (Test-Path $bg))    { $missing += ("background ({0})" -f $bg) }
  if (-not $useAudio)          { $missing += ("audio (missing or failed)") }
  if (-not (Test-Path $srt))   { $missing += ("srt ({0})" -f $srt) }
  if (-not (Test-Path $boxPng)) { Write-Host "Note: box png missing for $id (this is optional)" }

  if ($missing.Count -gt 0) {
    Write-Warning ("Skipping {0}: missing: {1}" -f $id, ($missing -join ", "))
    $fail++; continue
  }

  # --------- Stage 1: background + box overlay + attach audio (no subtitles) -----
  $boxWidthStr = $boxWidth.ToString()
  $filter1 = "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=rgba[bg];[1:v]scale=${boxWidthStr}:-1,format=rgba[box];[bg][box]overlay=x=(W-w)/2:y=(H-h)/2[tmpv]"
  $ff = "ffmpeg"
  $args1 = @("-y","-loop","1","-i",$bg,"-i",$boxPng,"-i",$useAudio,"-filter_complex",$filter1,"-map","[tmpv]","-map","2:a","-c:v","libx264","-preset","medium","-crf","18","-c:a","aac","-b:a","128k","-shortest",$outNoSubs)
  Write-Host ("Stage1 -> {0} (log -> {1})" -f $outNoSubs, $logFile1)
  try {
    & $ff @args1 2>&1 | Tee-Object -FilePath $logFile1
    if (-not (Test-Path $outNoSubs)) { Write-Warning ("Stage1 failed for {0}. Check {1}" -f $id,$logFile1); $fail++; continue }
  } catch {
    Write-Warning ("Stage1 ffmpeg error for {0}: {1}" -f $id,$_.Exception.Message)
    $fail++; continue
  }

  # ---------- Stage 2: burn subtitles into a final file ----------
  $srtForFf = $srt -replace '\\','/'
  $vf = "subtitles='$srtForFf':force_style='$assStyle'"
  $args2 = @("-y","-i",$outNoSubs,"-vf",$vf,"-c:v","libx264","-preset","medium","-crf","18","-c:a","copy",$outFinal)
  Write-Host ("Stage2 -> {0} (log -> {1})" -f $outFinal, $logFile2)
  try {
    & $ff @args2 2>&1 | Tee-Object -FilePath $logFile2
    if (Test-Path $outFinal) { Write-Host ("✅ Rendered: {0}" -f $outFinal); $success++ } else { Write-Warning ("Stage2 finished but final output missing for {0}. Check: {1}" -f $id,$logFile2); $fail++ }
  } catch {
    Write-Warning ("Stage2 ffmpeg error for {0}: {1}" -f $id, $_.Exception.Message)
    $fail++
  }
}

Write-Host "`nDone. Success: $success, Failed: $fail"
Write-Host "All saved outputs (central): $absOutputsRoot"
