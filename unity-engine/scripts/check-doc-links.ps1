# check-doc-links.ps1 — check external doc URLs found in library markdown (PowerShell 5.1 compatible)
# Usage: powershell -File scripts/check-doc-links.ps1 [-SkillRoot ..] [-Concurrency 8] [-TimeoutSec 12]
# Exit code: 0 = no dead links; 1 = dead links found
param(
    [string]$SkillRoot = (Join-Path $PSScriptRoot ".."),
    [int]$Concurrency = 8,
    [int]$TimeoutSec = 12
)

$mdFiles = Get-ChildItem -LiteralPath $SkillRoot -Recurse -Filter *.md
$urls = @()
foreach ($f in $mdFiles) {
    $t = Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8
    [regex]::Matches($t, 'https?://[^\s\)\]]+') | ForEach-Object {
        $u = $_.Value.TrimEnd('.', ',', ';')
        if ($u -match '[<>]') { return }   # skip URL template placeholders like https://docs.unity3d.com/<version>/...
        $urls += [PSCustomObject]@{ Url = $u; File = $f.Name }
    }
}
$unique = @($urls | Select-Object Url, File -Unique)
Write-Output "URLs to check: $($unique.Count)"

$scriptBlock = {
    param($item, $timeout)
    $url = $item.Url
    $status = $null
    try {
        $req = [System.Net.HttpWebRequest]::Create($url)
        $req.Method = "GET"
        $req.Timeout = $timeout * 1000
        $req.UserAgent = "Mozilla/5.0 (skill-link-checker)"
        $req.AllowAutoRedirect = $true
        $resp = $req.GetResponse()
        $status = [int]$resp.StatusCode
        $resp.Close()
    } catch {
        $webEx = $_.Exception
        if ($webEx -is [System.Net.WebException] -and $webEx.Response) {
            try { $status = [int]$webEx.Response.StatusCode; $webEx.Response.Close() } catch { }
        }
    }
    if (-not $status) { $status = 0 }   # transport-level failure (timeout/DNS/invalid URL)
    $ok = ($status -ge 200 -and $status -lt 400)
    return [PSCustomObject]@{ Url = $url; File = $item.File; Ok = $ok; Status = $status }
}

$queue = New-Object System.Collections.Queue
foreach ($u in $unique) { $queue.Enqueue($u) }
$results = @()
$jobs = @()

while ($queue.Count -gt 0 -or $jobs.Count -gt 0) {
    # collect finished jobs
    $finished = @($jobs | Where-Object { $_.State -eq 'Completed' -or $_.State -eq 'Failed' })
    foreach ($j in $finished) {
        $results += Receive-Job -Job $j
        Remove-Job -Job $j -Force
    }
    $jobs = @($jobs | Where-Object { $_.State -eq 'Running' })

    # fill to concurrency
    while ($jobs.Count -lt $Concurrency -and $queue.Count -gt 0) {
        $item = $queue.Dequeue()
        $jobs += Start-Job -ScriptBlock $scriptBlock -ArgumentList $item, $TimeoutSec
    }
    Start-Sleep -Milliseconds 100
}
foreach ($j in $jobs) {
    $results += Receive-Job -Job $j
    Remove-Job -Job $j -Force
}

$dead = @($results | Where-Object { -not $_.Ok })
$okCount = $results.Count - $dead.Count
Write-Output "Reachable: $okCount / $($results.Count)"
if ($dead.Count -gt 0) {
    Write-Output "== Dead/error links ($($dead.Count)) =="
    foreach ($d in $dead) { Write-Output ("[{0}] status={1} {2}" -f $d.File, $d.Status, $d.Url) }
    exit 1
}
Write-Output "== No dead links =="
exit 0
