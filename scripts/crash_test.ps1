# Kill the worker that is building a digest and watch another worker finish it.
#
#   pwsh scripts/crash_test.ps1 [-Base http://localhost:8080] [-ProfileIndex 1]
#
# Needs the stack in Ollama mode (a heuristic build takes half a second, too
# fast to interrupt) and at least two worker-digest replicas. Set
# RADAR_DIGEST_TASK_TIMEOUT_SECONDS=300 before starting the stack, otherwise
# the message is handed over only after the default 20 minutes.
param(
    [string]$Base = "http://localhost:8080",
    [int]$ProfileIndex = 1,
    [double]$KillAtProgress = 0.35
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$api = "$Base/api/v1"

$profile = (Invoke-RestMethod "$api/profiles")[$ProfileIndex]
$digest = Invoke-RestMethod -Method Post "$api/digests" -ContentType "application/json" `
    -Body (@{ profile_id = $profile.id; period_days = 7 } | ConvertTo-Json)
$started = Get-Date
Write-Output "digest $($digest.id) for '$($profile.spec.name)' queued at $($started.ToString('HH:mm:ss'))"

# Wait until grading is well under way.
do {
    Start-Sleep -Milliseconds 700
    $state = Invoke-RestMethod "$api/digests/$($digest.id)"
} while ($state.status -ne "failed" -and $state.progress -lt $KillAtProgress)
Write-Output "progress $($state.progress) at stage '$($state.stage)' after $([int]((Get-Date) - $started).TotalSeconds) s"

# Find the worker that logged the start of this digest and kill it.
$victim = docker ps --filter "name=worker-digest" --format "{{.Names}}" | Where-Object {
    (docker logs $_ 2>&1 | Select-String -SimpleMatch $digest.id | Select-String -SimpleMatch "digest_started")
} | Select-Object -First 1
if (-not $victim) { throw "no worker reports this digest" }
docker kill $victim | Out-Null
$killed = Get-Date
Write-Output "killed $victim at $($killed.ToString('HH:mm:ss'))"

# The message stays unacknowledged; another worker claims it after the idle timeout.
do {
    Start-Sleep -Seconds 5
    $state = Invoke-RestMethod "$api/digests/$($digest.id)"
} while ($state.status -in @("queued", "running"))
$finished = Get-Date

Write-Output "status: $($state.status) after $([int]($finished - $killed).TotalSeconds) s from the kill"
Write-Output "stats: selected=$($state.stats.selected) candidates=$($state.stats.candidates) graded_by_model=$($state.stats.graded_by_model) degraded=$($state.stats.degraded)"
docker ps --filter "name=worker-digest" --format "{{.Names}}" | ForEach-Object {
    docker logs $_ 2>&1 | Select-String -SimpleMatch $digest.id | Select-String -SimpleMatch "digest_started" |
        ForEach-Object { "resumed by: $($_.Line)" }
}
