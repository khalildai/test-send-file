$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
Write-Host 'Checking Node.js...'
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) { throw 'Need Node.js 18+ in PATH.' }
if (-not (Test-Path 'node_modules')) {
    Write-Host 'npm install...'
    npm install
    if ($LASTEXITCODE -ne 0) { throw 'npm install failed.' }
}
Write-Host 'Local URL: http://127.0.0.1:5174'
Write-Host 'Keep this window open. Ctrl+C to stop.'
npm run dev
exit $LASTEXITCODE
