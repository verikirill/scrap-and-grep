# Stop the model server in the middle of a digest build and check that the
# digest is still delivered, finished by the offline algorithm.
#
#   pwsh scripts/model_outage_test.ps1 [-Base http://localhost:8080] [-ProfileIndex 2]
#
# Needs the stack in Ollama mode.
param(
    [string]$Base = "http://localhost:8080",
    [int]$ProfileIndex = 2,
    [double]$StopAtProgress = 0.3,
    [string]$Container = "radar-ollama-1"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$api = "$Base/api/v1"

$profile = (Invoke-RestMethod "$api/profiles")[$ProfileIndex]
$digest = Invoke-RestMethod -Method Post "$api/digests" -ContentType "application/json" `
    -Body (@{ profile_id = $profile.id; period_days = 7 } | ConvertTo-Json)
$started = Get-Date
Write-Output "digest $($digest.id) for '$($profile.spec.name)' queued"

do {
    Start-Sleep -Milliseconds 700
    $state = Invoke-RestMethod "$api/digests/$($digest.id)"
} while ($state.status -ne "failed" -and $state.progress -lt $StopAtProgress)
Write-Output "progress $($state.progress) at stage '$($state.stage)' after $([int]((Get-Date) - $started).TotalSeconds) s, stopping $Container"

docker stop $Container | Out-Null
$stopped = Get-Date
try {
    do {
        Start-Sleep -Seconds 2
        $state = Invoke-RestMethod "$api/digests/$($digest.id)"
    } while ($state.status -in @("queued", "running"))
    $stats = $state.stats
    Write-Output "status: $($state.status), $([int]((Get-Date) - $stopped).TotalSeconds) s after the model server went down"
    Write-Output "selected=$($stats.selected) of $($stats.candidates) candidates in $($stats.topics) topics"
    Write-Output "graded_by_model=$($stats.graded_by_model) written_by_model=$($stats.written_by_model) degraded=$($stats.degraded)"
}
finally {
    docker start $Container | Out-Null
    Write-Output "$Container started again"
}
