param(
    [string]$Baseline = "kimi-data-01-baseline"
)

$ErrorActionPreference = "Stop"
$allowed = @(
    '^tools/build_dataset_inventory\.py$',
    '^tests/test_dataset_inventory\.py$',
    '^data/dataset_inventory/',
    '^docs/acceptance/dataset/0\.1\.0/',
    '^KIMI_DATA_01_OUTPUT/'
)

$tracked = @(git diff --name-only $Baseline --)
$untracked = @(git ls-files --others --exclude-standard)
$changed = @($tracked + $untracked | Sort-Object -Unique)
$violations = @()

foreach ($path in $changed) {
    $normalized = $path.Replace('\', '/')
    $isAllowed = $false
    foreach ($pattern in $allowed) {
        if ($normalized -match $pattern) {
            $isAllowed = $true
            break
        }
    }
    if (-not $isAllowed) {
        $violations += $normalized
    }
}

if ($violations.Count -gt 0) {
    Write-Error ("Kimi scope violation:`n" + ($violations -join "`n"))
    exit 1
}

Write-Output "Kimi scope check passed. Changed files: $($changed.Count)"
