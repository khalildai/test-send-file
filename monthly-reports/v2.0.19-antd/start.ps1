$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$html = Join-Path $PSScriptRoot '测试能力成熟度月报.html'
if (-not (Test-Path -LiteralPath $html)) {
    $html = Join-Path $PSScriptRoot 'dist\index.html'
}
if (-not (Test-Path -LiteralPath $html)) { throw 'Missing 测试能力成熟度月报.html' }
Start-Process $html
