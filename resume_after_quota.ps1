$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root

$Python = "C:\ProgramData\anaconda3\python.exe"
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "$(Resolve-Path .kaggle-cli-current);$(Resolve-Path .deps)"
$Task = "reading-or-guessing-urdu-font-twins"
$LogDir = Join-Path $Root "results\all_models"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir "quota_resume.log"
Start-Transcript -Path $Log -Append

try {
    $deadline = (Get-Date).AddHours(2)
    do {
        $quotaJson = & $Python -m kaggle benchmarks quota --format json
        $quota = $quotaJson | ConvertFrom-Json
        $daily = $quota | Where-Object period -eq "Daily"
        $remaining = [decimal](($daily.remaining -replace '[^0-9.]', ''))
        Write-Output "Daily quota remaining: $($daily.remaining); refill: $($daily.refillAt)"
        if ($remaining -gt 0) { break }
        Start-Sleep -Seconds 300
    } while ((Get-Date) -lt $deadline)
    if ($remaining -le 0) { throw "Daily AI quota did not refill before the retry deadline." }

    $retryReasons = @(
        "empty_response_under_token_cap",
        "quota_error",
        "canary_api_error",
        "task_configuration_error"
    )
    $status = Import-Csv -LiteralPath "results\all_models\model_run_status.csv"
    $models = @(
        $status |
            Where-Object {
                $_.classification -in @("unscheduled", "image_partial", "image_complete_prior_partial") -or
                $_.canary_failure_reason -in $retryReasons
            } |
            Select-Object -ExpandProperty model
    )
    Write-Output "Scheduling $($models.Count) unresolved models on task version 9."

    for ($index = 0; $index -lt $models.Count; $index += 5) {
        $last = [Math]::Min($index + 4, $models.Count - 1)
        $batch = $models[$index..$last]
        $arguments = @("benchmarks", "tasks", "run", $Task)
        foreach ($model in $batch) { $arguments += @("-m", $model) }
        & $Python -m kaggle @arguments
        if ($LASTEXITCODE -ne 0) { throw "Failed to schedule: $($batch -join ', ')" }
    }

    $runDeadline = (Get-Date).AddHours(4)
    Start-Sleep -Seconds 120
    do {
        $taskStatus = (& $Python -m kaggle benchmarks tasks status $Task) -join "`n"
        Write-Output $taskStatus
        if ($taskStatus -notmatch "\sRunning\s") { break }
        Start-Sleep -Seconds 120
    } while ((Get-Date) -lt $runDeadline)

    & $Python -m kaggle benchmarks tasks download $Task -o "results\kaggle_all_models_v9" --force
    & $Python collect_kaggle_results.py `
        --run-root "results\kaggle_runs\reading-or-guessing-urdu-font-twins\5" `
        --run-root "results\kaggle_all_models_v8\reading-or-guessing-urdu-font-twins\8" `
        --run-root "results\kaggle_all_models_v9\reading-or-guessing-urdu-font-twins\9" `
        --output-dir "results\all_models"
    & $Python analysis.py `
        --predictions "results\all_models\all_model_predictions.csv" `
        --text-prior "results\all_models\all_model_text_prior_predictions.csv" `
        --output-dir "results\analysis\all_models"
} finally {
    Stop-Transcript
}
