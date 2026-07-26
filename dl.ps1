# dl.ps1 — show GitHub release download counts + change since last run.
# State is kept in your home dir so it never touches the repo.

$repo      = 'amirarasteh1990/amirarasteh1990.github.io'
$tag       = 'books'
$stateFile = Join-Path $HOME '.sedaha_download_counts.json'
$firstRun  = -not (Test-Path $stateFile)

# --- fetch current counts (single JSON array so ConvertFrom-Json is happy) ---
$data = gh api "repos/$repo/releases/tags/$tag" `
    --jq '[.assets[] | {name: .name, count: .download_count}]' | ConvertFrom-Json

$current = @{}
foreach ($a in $data) { $current[$a.name] = [int]$a.count }

# --- load previous snapshot ---
$prev = @{}
if (-not $firstRun) {
    $p = Get-Content $stateFile -Raw | ConvertFrom-Json
    foreach ($prop in $p.PSObject.Properties) { $prev[$prop.Name] = [int]$prop.Value }
}

# --- print ---
$totalCur = 0; $totalDelta = 0
foreach ($name in ($current.Keys | Sort-Object)) {
    $cur = $current[$name]
    $old = if ($prev.ContainsKey($name)) { $prev[$name] } else { 0 }
    $delta = $cur - $old
    $totalCur += $cur; $totalDelta += $delta
    $tag2 = if ($firstRun) { '     ' }
            elseif ($delta -gt 0) { '(+{0})' -f $delta }
            elseif ($delta -lt 0) { '({0})'  -f $delta }
            else { '(=)' }
    '{0,4}  {1,-7}  {2}' -f $cur, $tag2, $name
}
'-' * 40
$ttag = if ($firstRun) { '(first run)' } elseif ($totalDelta -ge 0) { '(+{0})' -f $totalDelta } else { '({0})' -f $totalDelta }
'{0,4}  {1,-7}  {2}' -f $totalCur, $ttag, 'TOTAL'

# --- save snapshot for next time ---
$current | ConvertTo-Json | Set-Content -Path $stateFile -Encoding utf8
