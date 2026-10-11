param(
    [string]$OutputDir = "media"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$out = Join-Path $root $OutputDir
$slides = Join-Path $out "slides"
$shots = Join-Path $out "screenshots"
$audio = Join-Path $out "audio"
$clips = Join-Path $out "clips"
New-Item -ItemType Directory -Force $out, $slides, $shots, $audio, $clips | Out-Null

$ink = [System.Drawing.Color]::FromArgb(24, 27, 32)
$paper = [System.Drawing.Color]::FromArgb(247, 246, 242)
$red = [System.Drawing.Color]::FromArgb(219, 65, 65)
$green = [System.Drawing.Color]::FromArgb(26, 136, 107)
$blue = [System.Drawing.Color]::FromArgb(42, 92, 156)
$muted = [System.Drawing.Color]::FromArgb(92, 98, 108)
$white = [System.Drawing.Color]::White

function New-Stage([int]$width, [int]$height, [System.Drawing.Color]$color = $paper) {
    $bitmap = [System.Drawing.Bitmap]::new($width, $height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
    $graphics.Clear($color)
    return @{ Bitmap = $bitmap; Graphics = $graphics }
}

function New-Font([float]$size, [System.Drawing.FontStyle]$style = [System.Drawing.FontStyle]::Regular) {
    return [System.Drawing.Font]::new("Segoe UI", $size, $style, [System.Drawing.GraphicsUnit]::Pixel)
}

function Draw-Text($g, [string]$text, [float]$x, [float]$y, [float]$w, [float]$h, [float]$size, [System.Drawing.Color]$color, [System.Drawing.FontStyle]$style = [System.Drawing.FontStyle]::Regular) {
    $font = New-Font $size $style
    $brush = [System.Drawing.SolidBrush]::new($color)
    $format = [System.Drawing.StringFormat]::new()
    $format.Trimming = [System.Drawing.StringTrimming]::Word
    $g.DrawString($text, $font, $brush, [System.Drawing.RectangleF]::new($x, $y, $w, $h), $format)
    $format.Dispose(); $brush.Dispose(); $font.Dispose()
}

function Draw-ImageFit($g, [string]$path, [float]$x, [float]$y, [float]$w, [float]$h, [bool]$crop = $false) {
    $image = [System.Drawing.Image]::FromFile($path)
    try {
        $scale = if ($crop) { [Math]::Max($w / $image.Width, $h / $image.Height) } else { [Math]::Min($w / $image.Width, $h / $image.Height) }
        $dw = $image.Width * $scale; $dh = $image.Height * $scale
        $dx = $x + (($w - $dw) / 2); $dy = $y + (($h - $dh) / 2)
        $state = $g.Save()
        $g.SetClip([System.Drawing.RectangleF]::new($x, $y, $w, $h))
        $g.DrawImage($image, $dx, $dy, $dw, $dh)
        $g.Restore($state)
    } finally { $image.Dispose() }
}

function Draw-Rule($g, [System.Drawing.Color]$color, [float]$x, [float]$y, [float]$w, [float]$height = 8) {
    $brush = [System.Drawing.SolidBrush]::new($color)
    $g.FillRectangle($brush, $x, $y, $w, $height)
    $brush.Dispose()
}

function Save-Stage($stage, [string]$path) {
    $stage.Bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $stage.Graphics.Dispose(); $stage.Bitmap.Dispose()
}

function Add-SlideChrome($g, [string]$section, [int]$number) {
    Draw-Text $g $section.ToUpperInvariant() 90 52 1100 40 25 $red ([System.Drawing.FontStyle]::Bold)
    Draw-Text $g ("{0:D2} / 07" -f $number) 1690 52 150 40 23 $muted
    Draw-Rule $g $ink 90 1010 1740 3
}

$naturalNastaliq = Join-Path $root "assets/images/canonical/p01-natural-nastaliq-canonical.png"
$naturalNaskh = Join-Path $root "assets/images/canonical/p01-natural-naskh-canonical.png"
$pseudoNastaliq = Join-Path $root "assets/images/canonical/p01-pseudo-nastaliq-canonical.png"
$pseudoNaskh = Join-Path $root "assets/images/canonical/p01-pseudo-naskh-canonical.png"
$heatmap = Join-Path $root "results/analysis/all_models/cer_heatmap.png"
$paired = Join-Path $root "results/analysis/all_models/paired_font_comparison.png"

# DEV cover: actual rendered pair plus a compact editorial title.
$s = New-Stage 1000 420
$g = $s.Graphics
Draw-Rule $g $red 0 0 1000 12
Draw-Text $g "READING OR`nGUESSING?" 54 54 460 150 54 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "Urdu Font-Twin Benchmark" 58 220 430 45 28 $blue ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "Same Unicode. Two scripts. Paired OCR." 58 278 420 70 21 $muted
Draw-ImageFit $g $pseudoNastaliq 530 48 420 145 $true
Draw-ImageFit $g $pseudoNaskh 530 225 420 145 $true
Draw-Text $g "NASTALIQ" 532 22 150 30 14 $red ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "NASKH" 532 199 150 30 14 $green ([System.Drawing.FontStyle]::Bold)
Save-Stage $s (Join-Path $out "cover.png")

# Post screenshot 1: exact-source pair.
$s = New-Stage 1600 900
$g = $s.Graphics
Draw-Text $g "Same source string, different visual system" 70 45 1400 70 47 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "Pseudo-word pair p01 | Unicode identity verified before evaluation" 72 118 1200 45 25 $muted
Draw-Text $g "Nastaliq" 75 203 220 42 25 $red ([System.Drawing.FontStyle]::Bold)
Draw-ImageFit $g $pseudoNastaliq 70 250 1460 245 $true
Draw-Text $g "Naskh" 75 543 220 42 25 $green ([System.Drawing.FontStyle]::Bold)
Draw-ImageFit $g $pseudoNaskh 70 590 1460 245 $true
Save-Stage $s (Join-Path $shots "01-font-twins.png")

# Post screenshot 2: design summary.
$s = New-Stage 1600 900
$g = $s.Graphics
Draw-Text $g "A paired experiment, not an OCR leaderboard" 70 45 1400 70 46 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "15 public sources x 3 conditions x 2 fonts = 90 images" 72 119 1300 44 25 $muted
$labels = @("NATURAL", "SHUFFLED", "PSEUDO")
$colors = @($blue, $green, $red)
$descs = @("Original Urdu sentences", "Same words, order removed", "Valid Urdu character sequences")
for ($i=0; $i -lt 3; $i++) {
    $x = 70 + ($i * 505)
    Draw-Rule $g $colors[$i] $x 225 445 10
    Draw-Text $g $labels[$i] $x 258 445 48 27 $colors[$i] ([System.Drawing.FontStyle]::Bold)
    Draw-Text $g $descs[$i] $x 318 445 80 24 $ink
    Draw-Text $g "15 exact-text font pairs" $x 414 445 42 22 $muted
}
Draw-Text $g "Primary outcome" 70 580 300 40 22 $muted ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "Nastaliq CER - Naskh CER" 70 628 760 64 42 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "+ paired bootstrap CI + sign-flip test" 72 700 800 42 24 $muted
Draw-Text $g "Strict NFC policy`nNo Urdu-letter folding" 1110 610 390 120 29 $blue ([System.Drawing.FontStyle]::Bold)
Save-Stage $s (Join-Path $shots "02-experimental-design.png")

# Post screenshots 3 and 4 preserve the actual analysis plots inside a titled frame.
$s = New-Stage 1600 1100
$g = $s.Graphics
Draw-Text $g "Character error rate by model, font, and condition" 60 38 1450 60 40 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "Only image-complete runs are included" 62 99 800 38 23 $muted
Draw-ImageFit $g $heatmap 60 160 1480 890 $false
Save-Stage $s (Join-Path $shots "03-cer-heatmap.png")

$s = New-Stage 1600 1100
$g = $s.Graphics
Draw-Text $g "Paired Nastaliq-minus-Naskh CER gaps" 60 38 1450 60 40 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "Positive values mean more errors in Nastaliq" 62 99 900 38 23 $muted
Draw-ImageFit $g $paired 60 160 1480 890 $false
Save-Stage $s (Join-Path $shots "04-paired-font-comparison.png")

# Seven 16:9 video slides.
$s = New-Stage 1920 1080; $g = $s.Graphics; Add-SlideChrome $g "The question" 1
Draw-Text $g "READING OR`nGUESSING?" 90 145 840 250 82 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "Does the same Urdu string produce a different transcription when only its font changes?" 95 445 750 210 38 $muted
Draw-ImageFit $g $pseudoNastaliq 1010 170 820 300 $true
Draw-ImageFit $g $pseudoNaskh 1010 560 820 300 $true
Save-Stage $s (Join-Path $slides "01-question.png")

$s = New-Stage 1920 1080; $g = $s.Graphics; Add-SlideChrome $g "Paired design" 2
Draw-Text $g "15 x 3 x 2" 90 150 900 120 86 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "sources     conditions     fonts" 95 278 950 45 29 $muted
$names = @("NATURAL", "SHUFFLED", "PSEUDO"); $cols = @($blue,$green,$red)
for($i=0;$i -lt 3;$i++){ $x=95+($i*590); Draw-Rule $g $cols[$i] $x 445 500 12; Draw-Text $g $names[$i] $x 485 500 58 34 $cols[$i] ([System.Drawing.FontStyle]::Bold); Draw-Text $g "15 exact-text`nfont pairs" $x 590 500 120 31 $ink }
Draw-Text $g "45 PAIRS  /  90 IMAGES" 95 840 1200 70 44 $ink ([System.Drawing.FontStyle]::Bold)
Save-Stage $s (Join-Path $slides "02-design.png")

$s = New-Stage 1920 1080; $g = $s.Graphics; Add-SlideChrome $g "Rendering validation" 3
Draw-Text $g "The font is the treatment." 90 148 1100 82 56 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "HarfBuzz shaping`nFreeType rasterization`nNo OS fallback`nVisible-height calibration" 95 285 700 390 38 $muted
Draw-Text $g "90 / 90" 1010 230 700 135 105 $green ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "images passed" 1030 375 600 60 38 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "45 / 45 exact-text pairs`n0 missing codepoints`n0 clipped or blank renders" 1030 500 720 210 34 $muted
Save-Stage $s (Join-Path $slides "03-validation.png")

$s = New-Stage 1920 1080; $g = $s.Graphics; Add-SlideChrome $g "Pilot signal" 4
Draw-Text $g "Gemini 3.7 Flash" 90 145 800 70 46 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "Paired CER gap" 95 238 500 45 28 $muted
Draw-Text $g "+0.18" 95 330 430 100 76 $blue ([System.Drawing.FontStyle]::Bold); Draw-Text $g "natural" 105 440 300 45 26 $muted
Draw-Text $g "+0.25" 610 330 430 100 76 $green ([System.Drawing.FontStyle]::Bold); Draw-Text $g "shuffled" 620 440 300 45 26 $muted
Draw-Text $g "+8.75" 1125 330 500 100 76 $red ([System.Drawing.FontStyle]::Bold); Draw-Text $g "pseudo" 1135 440 300 45 26 $muted
Draw-Text $g "percentage points" 95 555 500 45 25 $muted
Draw-Text $g "Pseudo 95% CI: +4.05 to +12.82 points" 95 700 1400 65 43 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "The predictable text hid most of the font gap." 97 800 1400 55 31 $muted
Save-Stage $s (Join-Path $slides "04-signal.png")

$s = New-Stage 1920 1080; $g = $s.Graphics; Add-SlideChrome $g "Across models" 5
Draw-ImageFit $g $paired 75 130 1120 820 $false
Draw-Text $g "7" 1320 185 300 120 100 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "image-complete models" 1330 320 470 90 34 $muted
Draw-Text $g "5 / 7" 1320 510 400 105 84 $red ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "positive pseudo gap`nwith CI above zero" 1330 625 470 150 34 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "Two models did not support the direction." 1330 820 450 90 25 $muted
Save-Stage $s (Join-Path $slides "05-models.png")

$s = New-Stage 1920 1080; $g = $s.Graphics; Add-SlideChrome $g "Honest status" 6
Draw-Text $g "46-model catalog" 90 150 900 85 58 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "4" 100 335 250 105 86 $green ([System.Drawing.FontStyle]::Bold); Draw-Text $g "fully complete" 110 455 380 50 28 $muted
Draw-Text $g "3" 600 335 250 105 86 $blue ([System.Drawing.FontStyle]::Bold); Draw-Text $g "all images,`npartial priors" 610 455 420 110 28 $muted
Draw-Text $g "39" 1130 335 300 105 86 $red ([System.Drawing.FontStyle]::Bold); Draw-Text $g "pending, partial,`nor canary failed" 1140 455 500 110 28 $muted
Draw-Text $g "Quota-limited expansion continues after refresh." 95 730 1500 65 41 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "No missing score is invented or imputed." 97 820 1300 52 29 $muted
Save-Stage $s (Join-Path $slides "06-status.png")

$s = New-Stage 1920 1080; $g = $s.Graphics; Add-SlideChrome $g "Explore" 7
Draw-Text $g "READ THE LETTERS.`nTEST THE PRIORS." 90 160 1500 220 76 $ink ([System.Drawing.FontStyle]::Bold)
Draw-Rule $g $red 95 445 650 12
Draw-Text $g "Kaggle" 95 520 260 45 27 $red ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "kaggle.com/benchmarks/tasks/huzaifa12344/`nreading-or-guessing-urdu-font-twins" 95 575 1400 110 34 $ink
Draw-Text $g "GitHub" 95 735 260 45 27 $green ([System.Drawing.FontStyle]::Bold)
Draw-Text $g "github.com/syncaimain/urdu-font-twin-benchmark" 95 790 1500 60 34 $ink
Save-Stage $s (Join-Path $slides "07-explore.png")

# Narration uses the local Windows speech engine. Each narrated still becomes one clip.
Add-Type -AssemblyName System.Speech
$narration = @(
    "Can a vision model actually read Urdu, or is it guessing from language patterns? This benchmark changes only the font while keeping the source string exactly the same.",
    "Fifteen public Urdu sentences become three conditions: natural text, shuffled words, and controlled pseudo words. Each is rendered in Nastaliq and Naskh, producing forty five exact text pairs and ninety images.",
    "Before any model call, HarfBuzz shapes every string right to left and FreeType renders the selected glyphs directly. Both fonts pass coverage, shaping, bounds, fallback, and pair identity checks.",
    "For Gemini three point seven Flash, the font gap is near zero on natural and shuffled text, then rises to eight point eight character error points on pseudo words. Its paired confidence interval excludes zero.",
    "Seven models completed every image. Five show a positive pseudo word gap with a confidence interval above zero. Two do not, which is why the benchmark reports paired model level results instead of one pooled headline.",
    "The available catalog contains forty six models. Four runs are fully complete, three completed all images with partial prior controls, and other runs are pending or failed canaries. Missing scores are never invented or imputed.",
    "The Kaggle benchmark and reproducible source are public. The next run expands model coverage, adds lower resolution tests, and scales the pilot from fifteen to sixty source items."
)

$slideFiles = Get-ChildItem $slides -Filter "*.png" | Sort-Object Name
$concatLines = @()
for ($i = 0; $i -lt $slideFiles.Count; $i++) {
    $wav = Join-Path $audio ("{0:D2}.wav" -f ($i + 1))
    $clip = Join-Path $clips ("{0:D2}.mp4" -f ($i + 1))
    $speaker = [System.Speech.Synthesis.SpeechSynthesizer]::new()
    $speaker.Rate = -1
    $speaker.SetOutputToWaveFile($wav)
    $speaker.Speak($narration[$i])
    $speaker.Dispose()
    & ffmpeg -y -hide_banner -loglevel error -loop 1 -framerate 30 -i $slideFiles[$i].FullName -i $wav -vf "scale=1920:1080,format=yuv420p" -c:v libx264 -preset medium -tune stillimage -c:a aac -b:a 160k -shortest -movflags +faststart $clip
    if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed for slide $($i + 1)" }
    $concatLines += "file '$($clip.Replace("'", "''"))'"
}

$concatPath = Join-Path $out "concat.txt"
[System.IO.File]::WriteAllLines($concatPath, $concatLines, [System.Text.UTF8Encoding]::new($false))
$video = Join-Path $out "urdu-font-twin-walkthrough.mp4"
& ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i $concatPath -c copy -movflags +faststart $video
if ($LASTEXITCODE -ne 0) { throw "ffmpeg concat failed" }

Write-Output "Created cover, screenshots, slides, narration, and video in $out"
