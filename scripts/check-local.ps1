$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing .venv. Create it first, then install the locked dependencies."
}
& $python (Join-Path $PSScriptRoot "local_check.py") @args
exit $LASTEXITCODE
