param([string]$PythonVersion = "3.11")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
foreach ($Tool in @("git", "py", "ffmpeg", "ffprobe")) {
    if (-not (Get-Command $Tool -ErrorAction SilentlyContinue)) {
        throw "$Tool is missing. Install it using a trusted source and reopen PowerShell."
    }
}
if ($PythonVersion -notmatch '^3\.(11|12|13)$') { throw "Use Python 3.11, 3.12 or 3.13." }
$Upstream = Get-Content -LiteralPath (Join-Path $Root "upstream.json") -Raw | ConvertFrom-Json
if ($Upstream.repository -ne "https://github.com/sun-guannan/VectCutAPI.git" -or
    $Upstream.commit -notmatch '^[a-f0-9]{40}$') { throw "Unexpected upstream manifest." }
$Vendor = Join-Path $Root "vendor\VectCutAPI"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
Push-Location $Root
try {
    if (-not (Test-Path -LiteralPath $Vendor)) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Vendor) | Out-Null
        Invoke-Checked "git" @("clone", "--no-checkout", "--", $Upstream.repository, $Vendor)
        Invoke-Checked "git" @("-C", $Vendor, "checkout", "--detach", $Upstream.commit)
    }
    $Revision = & git -C $Vendor rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or $Revision -ne $Upstream.commit) {
        throw "Existing VectCutAPI checkout is not pinned. It was not changed."
    }
    if (-not (Test-Path -LiteralPath $Python)) {
        Invoke-Checked "py" @("-$PythonVersion", "-m", "venv", ".venv")
    }
    Invoke-Checked $Python @("-m", "pip", "install", "--requirement", "requirements.lock")
    Invoke-Checked $Python @("-m", "pip", "check")
    Invoke-Checked $Python @("-m", "unittest", "discover", "-s", "tests", "-v")
    Write-Host "Setup complete. Copy config.example.json to config.local.json and configure your folders."
    Write-Host "No CapCut projects were created or changed. No HTTP server was started."
} finally {
    Pop-Location
}
