$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$logPath = Join-Path $PSScriptRoot 'startup.log'

function Write-Step([string]$Message) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Write-Host $Message
    Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
}

Set-Content -LiteralPath $logPath -Value "V2.0.14-1 startup log - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -Encoding UTF8
$env:PYTHONUTF8 = '1'
$env:MATURITY_PORT = '5000'

try {
    Write-Step '[0/3] Checking Python...'
    $candidates = @()
    if (Get-Command python -ErrorAction SilentlyContinue) { $candidates += ,@('python') }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($version in @('3.13','3.12','3.11','3.10')) { $candidates += ,@('py', "-$version") }
    }
    $launcher = $null; $runtimeInfo = $null
    foreach ($candidate in $candidates) {
        try {
            $command = $candidate[0]; $prefix = @($candidate | Select-Object -Skip 1)
            $runtime = & $command @prefix -c "import json,platform,struct,sys; print(json.dumps({'version':list(sys.version_info[:2]),'bits':struct.calcsize('P')*8,'impl':platform.python_implementation()}))" 2>> $logPath
            if ($LASTEXITCODE -ne 0) { continue }
            $info = $runtime | ConvertFrom-Json
            if ($info.impl -eq 'CPython' -and $info.bits -in @(32,64) -and $info.version[0] -eq 3 -and $info.version[1] -ge 10 -and $info.version[1] -le 13) { $launcher = $candidate; $runtimeInfo = $info; break }
        } catch { continue }
    }
    if (-not $launcher) { throw 'No compatible Python was found. Install Windows CPython 3.10-3.13 (32-bit or 64-bit) and enable Add Python to PATH.' }
    Write-Step "Detected CPython $($runtimeInfo.version -join '.') $($runtimeInfo.bits)-bit."
    if (-not (Test-Path -LiteralPath 'packages')) { throw 'The packages folder is missing. Extract the complete ZIP before starting.' }

    $needsInstall = $false
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        Write-Step '[1/3] Creating local Python environment...'
        $command = $launcher[0]; $prefix = @($launcher | Select-Object -Skip 1)
        & $command @prefix -m venv .venv 2>> $logPath
        if ($LASTEXITCODE -ne 0) { throw 'Unable to create the Python environment.' }
        $needsInstall = $true
    } else { Write-Step '[1/3] Existing local Python environment found.' }

    Write-Step '[2/3] Checking offline dependencies...'
    if (-not $needsInstall) {
        $probe = Start-Process -FilePath '.\.venv\Scripts\python.exe' -ArgumentList @('-c','import flask, waitress') -Wait -PassThru -WindowStyle Hidden
        $needsInstall = $probe.ExitCode -ne 0
    }
    if ($needsInstall) {
        Write-Step 'Installing dependencies from bundled offline packages...'
        $env:PIP_NO_INDEX = '1'
        $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
        & '.\.venv\Scripts\python.exe' -m pip install --no-index --find-links packages -r requirements.txt 2>&1 | Tee-Object -FilePath $logPath -Append
        if ($LASTEXITCODE -ne 0) { throw 'Offline dependency installation failed. Check startup.log.' }
    }

    Write-Step '[3/3] Starting V2.0.14 service...'
    Write-Host "Local URL: http://127.0.0.1:$env:MATURITY_PORT"
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
        ForEach-Object { Write-Host "LAN URL: http://$($_.IPAddress):$env:MATURITY_PORT" }
    Write-Host 'Keep this window open. Press Ctrl+C to stop.'
    & '.\.venv\Scripts\python.exe' run_server.py 2>&1 | Tee-Object -FilePath $logPath -Append
    exit $LASTEXITCODE
}
catch {
    Write-Step "ERROR: $($_.Exception.Message)"
    Write-Host "Details were saved to: $logPath" -ForegroundColor Yellow
    exit 1
}
finally {
    Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue
    Remove-Item Env:MATURITY_PORT -ErrorAction SilentlyContinue
    Remove-Item Env:PIP_NO_INDEX -ErrorAction SilentlyContinue
    Remove-Item Env:PIP_DISABLE_PIP_VERSION_CHECK -ErrorAction SilentlyContinue
}
