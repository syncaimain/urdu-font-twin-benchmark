$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root

$Python = "C:\ProgramData\anaconda3\python.exe"
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "$(Resolve-Path .kaggle-cli-current);$(Resolve-Path .deps)"
$Task = "reading-or-guessing-urdu-font-twins"
$ModelsFile = "assets\full\selected_models.txt"
$DownloadRoot = "results\kaggle_full"
$OutputDir = "results\full\all_models"
$AnalysisDir = "results\full\analysis"
$LogDir = "results\full"
$ScheduledTaskName = "UrduFontTwinFullRun"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Start-Transcript -Path (Join-Path $LogDir "quota_run.log") -Append

try {
    $deadline = (Get-Date).AddHours(4)
    do {
        $quotaJson = & $Python -m kaggle benchmarks quota --format json
        if ($LASTEXITCODE -ne 0) { throw "Could not read Kaggle quota." }
        $quota = $quotaJson | ConvertFrom-Json
        $daily = $quota | Where-Object period -eq "Daily"
        $remaining = [decimal](($daily.remaining -replace '[^0-9.]', ''))
        Write-Output "Daily quota remaining: $($daily.remaining); refill: $($daily.refillAt)"
        if ($remaining -gt 0) { break }
        Start-Sleep -Seconds 300
    } while ((Get-Date) -lt $deadline)
    if ($remaining -le 0) { throw "Daily AI quota did not refill before the run deadline." }

    $models = @(Get-Content -LiteralPath $ModelsFile | Where-Object { $_.Trim() })
    $statusFile = Join-Path $OutputDir "model_run_status.csv"
    if (Test-Path -LiteralPath $statusFile) {
        $retryable = @(
            "unscheduled",
            "run_error",
            "image_partial",
            "image_complete_prior_partial"
        )
        $retryableCanaryReasons = @("quota_error", "canary_api_error", "task_configuration_error")
        $status = Import-Csv -LiteralPath $statusFile
        $models = @(
            $status |
                Where-Object {
                    $_.classification -in $retryable -or
                    $_.canary_failure_reason -in $retryableCanaryReasons
                } |
                Select-Object -ExpandProperty model
        )
    }

    if ($models.Count -eq 0) {
        Write-Output "No retryable full-run models remain."
        exit 0
    }

    Write-Output "Scheduling $($models.Count) full-run models: $($models -join ', ')"
    for ($index = 0; $index -lt $models.Count; $index += 4) {
        $last = [Math]::Min($index + 3, $models.Count - 1)
        $batch = $models[$index..$last]
        $arguments = @("benchmarks", "tasks", "run", $Task)
        foreach ($model in $batch) { $arguments += @("-m", $model) }
        & $Python -m kaggle @arguments
        if ($LASTEXITCODE -ne 0) { throw "Failed to schedule: $($batch -join ', ')" }
    }

    $runDeadline = (Get-Date).AddHours(8)
    Start-Sleep -Seconds 120
    do {
        $taskStatus = (& $Python -m kaggle benchmarks tasks status $Task) -join "`n"
        Write-Output $taskStatus
        if ($taskStatus -notmatch "\s(Running|Queued)\s") { break }
        Start-Sleep -Seconds 120
    } while ((Get-Date) -lt $runDeadline)

    & $Python -m kaggle benchmarks tasks download $Task -o $DownloadRoot --force
    if ($LASTEXITCODE -ne 0) { throw "Failed to download Kaggle run artifacts." }

    $taskRoot = Join-Path $DownloadRoot $Task
    $versionDirs = @(Get-ChildItem -LiteralPath $taskRoot -Directory | Sort-Object Name)
    if ($versionDirs.Count -eq 0) { throw "No downloaded task-version directories were found." }

    $collectorArgs = @(
        "collect_kaggle_results.py",
        "--expected-models", $ModelsFile,
        "--expected-images", "360",
        "--expected-priors", "180",
        "--output-dir", $OutputDir
    )
    foreach ($versionDir in $versionDirs) {
        $collectorArgs += @("--run-root", $versionDir.FullName)
    }
    & $Python @collectorArgs
    if ($LASTEXITCODE -ne 0) { throw "Failed to consolidate full-run outputs." }

    $predictions = Join-Path $OutputDir "all_model_predictions.csv"
    $priors = Join-Path $OutputDir "all_model_text_prior_predictions.csv"
    if (Test-Path -LiteralPath $predictions) {
        $analysisArgs = @(
            "analysis.py",
            "--manifest", "assets\full\manifest.jsonl",
            "--predictions", $predictions,
            "--output-dir", $AnalysisDir
        )
        if (Test-Path -LiteralPath $priors) {
            $analysisArgs += @("--text-prior", $priors)
        }
        & $Python @analysisArgs
        if ($LASTEXITCODE -ne 0) { throw "Full-run analysis failed." }
    }

    $finalStatus = Import-Csv -LiteralPath $statusFile
    $complete = @($finalStatus | Where-Object classification -eq "complete").Count
    Write-Output "Full-run completion: $complete / $($finalStatus.Count) models."
    if ($complete -eq $finalStatus.Count) {
        Unregister-ScheduledTask -TaskName $ScheduledTaskName -Confirm:$false -ErrorAction SilentlyContinue
        Write-Output "All selected models completed; removed the daily scheduled task."
    }
} finally {
    Stop-Transcript
}
