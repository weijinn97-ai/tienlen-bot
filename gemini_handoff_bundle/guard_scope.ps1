param(
    [string]$PolicyPath = "gemini_handoff_bundle/ACTIVE_TASK.json"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $PolicyPath)) {
    Write-Error "Active task policy not found: $PolicyPath"
    exit 1
}

$policy = Get-Content -Raw -LiteralPath $PolicyPath | ConvertFrom-Json
if ($policy.status -ne "ACTIVE") {
    Write-Error "No ACTIVE Gemini task is authorized."
    exit 1
}

git rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Run the guard inside the Git repository."
    exit 1
}

git rev-parse --verify $policy.baseline_ref *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Baseline ref does not exist: $($policy.baseline_ref)"
    exit 1
}

$branch = (git branch --show-current).Trim()
if ($branch -ne $policy.required_branch) {
    Write-Error "Wrong branch '$branch'. Required: $($policy.required_branch)"
    exit 1
}

git merge-base --is-ancestor $policy.baseline_ref HEAD
if ($LASTEXITCODE -ne 0) {
    Write-Error "HEAD is not based on $($policy.baseline_ref)."
    exit 1
}

function Convert-GlobToRegex([string]$Glob) {
    $escaped = [Regex]::Escape($Glob.Replace('\', '/'))
    $escaped = $escaped.Replace('\*\*', '.*')
    $escaped = $escaped.Replace('\*', '[^/]*')
    return '^' + $escaped + '$'
}

function Matches-Any([string]$Path, $Patterns) {
    foreach ($pattern in $Patterns) {
        if ($Path -match (Convert-GlobToRegex $pattern)) {
            return $true
        }
    }
    return $false
}

$nameStatus = @(git diff --name-status $policy.baseline_ref --)
$untracked = @(git ls-files --others --exclude-standard)
$changes = @{}
$violations = @()

foreach ($line in $nameStatus) {
    if (-not $line) { continue }
    $parts = $line -split "`t"
    $status = $parts[0]
    if ($status -match '^[DRC]') {
        $violations += "Delete/rename/copy is forbidden: $line"
        continue
    }
    $changes[$parts[-1].Replace('\', '/')] = $status
}

foreach ($path in $untracked) {
    $changes[$path.Replace('\', '/')] = "?"
}

foreach ($path in $changes.Keys) {
    git cat-file -e "$($policy.baseline_ref):$path" 2>$null
    $existedAtBaseline = $LASTEXITCODE -eq 0
    if ($existedAtBaseline) {
        if (-not (Matches-Any $path $policy.allowed_existing_file_modifications)) {
            $violations += "Existing file modification is forbidden: $path"
        }
    }
    elseif (-not (Matches-Any $path $policy.allowed_new_paths)) {
        $violations += "New file is outside whitelist: $path"
    }
}

if ($violations.Count -gt 0) {
    Write-Error ("Gemini scope violation:`n" + ($violations -join "`n"))
    exit 1
}

Write-Output "Gemini scope check passed. Task=$($policy.task_id); branch=$branch; changed=$($changes.Count)"
