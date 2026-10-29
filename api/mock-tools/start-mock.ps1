$ErrorActionPreference = 'Stop'
$mockWorkspace = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$mockNode = Join-Path $mockWorkspace '.mock-runtime/node-v24.18.0-win-x64/node.exe'
$mockCaddy = Join-Path $mockWorkspace '.mock-runtime/caddy-2.11.7/caddy.exe'
$mockPrism = Join-Path $PSScriptRoot 'node_modules/@stoplight/prism-cli/dist/index.js'
$mockSpec = Join-Path $PSScriptRoot '../openapi.yaml'
$mockConfig = Join-Path $PSScriptRoot 'Caddyfile'
$mockLogs = Join-Path $PSScriptRoot 'runtime'
foreach ($mockFile in @($mockNode, $mockCaddy, $mockPrism, $mockSpec, $mockConfig)) {
    if (-not (Test-Path -LiteralPath $mockFile)) { throw "Missing mock tool/config: $mockFile" }
}
foreach ($mockPort in @(4010, 4011)) {
    $mockSocket = New-Object System.Net.Sockets.TcpClient
    $mockPortOccupied = $false
    try { $mockSocket.Connect('127.0.0.1', $mockPort); $mockPortOccupied = $true } catch { }
    finally { $mockSocket.Dispose() }
    if ($mockPortOccupied) {
        throw "Port $mockPort is occupied. Stop the previous mock before starting."
    }
}
New-Item -ItemType Directory -Force -Path $mockLogs | Out-Null
$mockPrismProcess = Start-Process -FilePath $mockNode `
    -ArgumentList @(('"' + $mockPrism + '"'), 'mock', ('"' + $mockSpec + '"'), '--host', '127.0.0.1', '--port', '4011') `
    -WorkingDirectory $mockWorkspace -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $mockLogs 'prism.stdout.log') `
    -RedirectStandardError (Join-Path $mockLogs 'prism.stderr.log')
$mockPrismProcess.Id | Set-Content (Join-Path $mockLogs 'prism.pid')
@{ id = $mockPrismProcess.Id; startedUtcTicks = $mockPrismProcess.StartTime.ToUniversalTime().Ticks.ToString() } |
    ConvertTo-Json | Set-Content (Join-Path $mockLogs 'prism.process.json')
try {
    $mockBackendReady = $false
    for ($mockAttempt = 0; $mockAttempt -lt 80; $mockAttempt++) {
        $mockPrismProcess.Refresh()
        if ($mockPrismProcess.HasExited) { throw 'Prism exited during startup; inspect its logs.' }
        $mockSocket = New-Object System.Net.Sockets.TcpClient
        try { $mockSocket.Connect('127.0.0.1', 4011); $mockBackendReady = $true } catch { }
        finally { $mockSocket.Dispose() }
        if ($mockBackendReady) { break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $mockBackendReady) { throw 'Prism did not start listening within the startup timeout.' }
    $mockOriginalDataDirectory = $env:XDG_DATA_HOME
    $mockOriginalConfigDirectory = $env:XDG_CONFIG_HOME
    try {
        $env:XDG_DATA_HOME = Join-Path $mockWorkspace '.mock-runtime/caddy-app-data'
        $env:XDG_CONFIG_HOME = Join-Path $mockWorkspace '.mock-runtime/caddy-app-config'
        $mockCaddyProcess = Start-Process -FilePath $mockCaddy `
            -ArgumentList @('run', '--config', ('"' + $mockConfig + '"'), '--adapter', 'caddyfile') `
            -WorkingDirectory $mockWorkspace -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $mockLogs 'caddy.stdout.log') `
            -RedirectStandardError (Join-Path $mockLogs 'caddy.stderr.log')
    } finally {
        $env:XDG_DATA_HOME = $mockOriginalDataDirectory
        $env:XDG_CONFIG_HOME = $mockOriginalConfigDirectory
    }
    $mockCaddyProcess.Id | Set-Content (Join-Path $mockLogs 'caddy.pid')
    @{ id = $mockCaddyProcess.Id; startedUtcTicks = $mockCaddyProcess.StartTime.ToUniversalTime().Ticks.ToString() } |
        ConvertTo-Json | Set-Content (Join-Path $mockLogs 'caddy.process.json')
    $mockReady = $false
    for ($mockAttempt = 0; $mockAttempt -lt 40; $mockAttempt++) {
        $mockPrismProcess.Refresh()
        $mockCaddyProcess.Refresh()
        if ($mockPrismProcess.HasExited -or $mockCaddyProcess.HasExited) {
            throw "A mock process exited. Inspect logs in $mockLogs"
        }
        try {
            $mockProbe = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:4010/api/v1/cars' `
                -Headers @{ Prefer = 'code=200, example=PublicCarList' } -TimeoutSec 2
            if ($mockProbe.StatusCode -eq 200) { $mockReady = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 250
    }
    if (-not $mockReady) { throw 'Mock did not become ready within the startup timeout.' }
    Write-Output "Mock listening: http://127.0.0.1:4010/api/v1"
    Write-Output "Prism PID: $($mockPrismProcess.Id); Caddy PID: $($mockCaddyProcess.Id)"
    Write-Output "Logs: $mockLogs"
} catch {
    if ($mockCaddyProcess -and -not $mockCaddyProcess.HasExited) { Stop-Process -Id $mockCaddyProcess.Id }
    if (-not $mockPrismProcess.HasExited) { Stop-Process -Id $mockPrismProcess.Id }
    throw
}
