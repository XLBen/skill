# validate-skills.ps1 — unity-engine skill self-validation
# Usage: powershell -File scripts/validate-skills.ps1 [-SkillRoot ..]
# Exit code: 0 = all pass; 1 = failures found
param(
    [string]$SkillRoot = (Join-Path $PSScriptRoot "..")
)

$ErrorActionPreference = "Stop"
$script:failCount = 0

function Check([bool]$ok, [string]$msg) {
    if ($ok) { Write-Output "[PASS] $msg" }
    else { Write-Output "[FAIL] $msg"; $script:failCount++ }
}

Write-Output "== Validating: $(Resolve-Path $SkillRoot) =="

# 1. SKILL.md exists
$skillMd = Join-Path $SkillRoot "SKILL.md"
Check (Test-Path -LiteralPath $skillMd) "SKILL.md exists"

# 2. frontmatter parsing
$content = Get-Content -LiteralPath $skillMd -Raw -Encoding UTF8
$fmMatch = [regex]::Match($content, "---\r?\n(?<fm>.*?)\r?\n---", [System.Text.RegularExpressions.RegexOptions]::Singleline)
Check $fmMatch.Success "frontmatter exists"
$fm = $fmMatch.Groups["fm"].Value

$name = [regex]::Match($fm, '^name:\s*(.+?)\s*$', [System.Text.RegularExpressions.RegexOptions]::Multiline).Groups[1].Value
$desc = [regex]::Match($fm, '^description:\s*(.+?)\s*$', [System.Text.RegularExpressions.RegexOptions]::Multiline).Groups[1].Value

# 3. name rules
Check ($name -match '^[a-z0-9]+(-[a-z0-9]+)*$') "name is lowercase-hyphen: $name"
Check ($name.Length -le 64) "name length <= 64 ($($name.Length))"
Check ($name -eq (Split-Path $SkillRoot -Leaf)) "name matches directory ($name)"

# 4. description rules
Check ($desc.Length -gt 0) "description non-empty"
Check ($desc.Length -le 1024) "description <= 1024 chars ($($desc.Length))"
Check ($desc -notmatch '<[a-zA-Z/]') "description has no XML tags"
Check ($desc -like "Use*") "description starts with Use (third person)"
Check ($desc -match "Unity") "description contains Unity keyword"
Check ($desc -match "Use ONLY for") "description has negative gating (Use ONLY for)"

# 5. SKILL.md line budget
$lineCount = ($content -split "`n").Count
Check ($lineCount -le 500) "SKILL.md <= 500 lines ($lineCount)"

# 6. dispatch-table reference files all exist
$mdFiles = Get-ChildItem -LiteralPath $SkillRoot -Recurse -Filter *.md | ForEach-Object { $_.FullName.Substring((Resolve-Path $SkillRoot).Path.Length + 1).Replace('\','/') }
$refs = [regex]::Matches($content, 'references/[0-9a-z][0-9a-z\-/]*\.md') | ForEach-Object { $_.Value } | Sort-Object -Unique
$missing = @()
foreach ($r in $refs) {
    if (-not (Test-Path -LiteralPath (Join-Path $SkillRoot ($r -replace '/','\')))) { $missing += $r }
}
$refMsg = "SKILL.md references exist ($($refs.Count) refs)"
if ($missing.Count -gt 0) { $refMsg = $refMsg + " MISSING: $($missing -join ', ')" }
Check ($missing.Count -eq 0) $refMsg

# 7. no Windows backslash paths in SKILL.md
$badPaths = [regex]::Matches($content, '(?<![`A-Za-z0-9])(?:references|assets|scripts|evals|genres)\\[a-z0-9]')
Check ($badPaths.Count -eq 0) "no backslash paths in SKILL.md"

# 8. legacy API naming check (code-style rb.velocity usage; doc mentions of the rename are allowed)
$mdFileList = Get-ChildItem -LiteralPath $SkillRoot -Recurse -Filter *.md | Select-Object -ExpandProperty FullName
$oldApi = Select-String -LiteralPath $mdFileList -Pattern '\brb\.velocity\b' -AllMatches
Check ($oldApi.Count -eq 0) "no legacy rb.velocity naming"

# 9. cross-file references resolve
$allRefs = @()
foreach ($f in Get-ChildItem -LiteralPath $SkillRoot -Recurse -Filter *.md) {
    $t = Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8
    [regex]::Matches($t, '(?<!http)\breferences/(?:genres/)?[0-9a-z][0-9a-z\-/]*\.md') | ForEach-Object { $allRefs += $_.Value }
}
$missing2 = @()
foreach ($r in ($allRefs | Sort-Object -Unique)) {
    if (-not (Test-Path -LiteralPath (Join-Path $SkillRoot ($r -replace '/','\')))) { $missing2 += $r }
}
$refMsg2 = "all cross-file references resolve ($($allRefs.Count) refs)"
if ($missing2.Count -gt 0) { $refMsg2 = $refMsg2 + " BROKEN: $($missing2 -join ', ')" }
Check ($missing2.Count -eq 0) $refMsg2

# 10. single doc version across library
$versions = @()
foreach ($f in $mdFileList) {
    $line = Get-Content -LiteralPath $f -Raw -Encoding UTF8
    [regex]::Matches($line, 'docs\.unity3d\.com/6000\.[0-9]') | ForEach-Object { $versions += $_.Value }
}
$uniqueVersions = ($versions | Sort-Object -Unique)
Check ($uniqueVersions.Count -le 1) "single doc version used: $($uniqueVersions -join ', ')"

Write-Output ""
if ($script:failCount -eq 0) { Write-Output "== ALL PASS =="; exit 0 }
else { Write-Output "== $($script:failCount) FAILURES =="; exit 1 }
