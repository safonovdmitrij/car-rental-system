$ErrorActionPreference = 'Stop'
$mockWorkspace = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$mockExecutables = @{
    prism = (Join-Path $mockWorkspace '.mock-runtime/node-v24.18.0-win-x64/node.exe')
    caddy = (Join-Path $mockWorkspace '.mock-runtime/caddy-2.11.7/caddy.exe')
}
foreach ($mockName in @('caddy', 'prism')) {
    $mockStateFile = Join-Path $PSScriptRoot "runtime/$mockName.process.json"
    if (-not (Test-Path -LiteralPath $mockStateFile)) { continue }
    $mockState = Get-Content -LiteralPath $mockStateFile -Raw | ConvertFrom-Json
    $mockProcessId = [int]$mockState.id
    $mockProcess = Get-Process -Id $mockProcessId -ErrorAction SilentlyContinue
    if ($mockProcess) {
        if ($mockProcess.Path -ine $mockExecutables[$mockName]) {
            throw "PID $mockProcessId no longer belongs to the expected $mockName executable; not stopping it."
        }
        if ($mockProcess.StartTime.ToUniversalTime().Ticks.ToString() -ne $mockState.startedUtcTicks) {
            throw "PID $mockProcessId was reused by a different process; not stopping it."
        }
        Stop-Process -Id $mockProcessId
        Write-Output "Stopped $mockName (PID $mockProcessId)"
    }
    Remove-Item -LiteralPath $mockStateFile
    $mockPidFile = Join-Path $PSScriptRoot "runtime/$mockName.pid"
    if (Test-Path -LiteralPath $mockPidFile) { Remove-Item -LiteralPath $mockPidFile }
}
