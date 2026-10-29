$ErrorActionPreference = 'Stop'
$mockWorkspace = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$mockRuntime = Join-Path $mockWorkspace '.mock-runtime'
New-Item -ItemType Directory -Force -Path $mockRuntime | Out-Null

function Get-VerifiedMockArchive {
    param([string]$Archive, [string]$BaseUrl, [string]$ChecksumFile, [string]$Algorithm)
    $mockArchivePath = Join-Path $mockRuntime $Archive
    $mockChecksumPath = Join-Path $mockRuntime $ChecksumFile
    if (-not (Test-Path -LiteralPath $mockArchivePath)) {
        Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/$Archive" -OutFile $mockArchivePath
    }
    if (-not (Test-Path -LiteralPath $mockChecksumPath)) {
        Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/$ChecksumFile" -OutFile $mockChecksumPath
    }
    $mockChecksumLines = @(Get-Content -LiteralPath $mockChecksumPath | Where-Object { $_.Trim().EndsWith($Archive) })
    if ($mockChecksumLines.Count -ne 1) { throw "No unique checksum for $Archive" }
    $mockExpectedHash = ($mockChecksumLines[0] -split '\s+')[0]
    $mockActualHash = (Get-FileHash -LiteralPath $mockArchivePath -Algorithm $Algorithm).Hash
    if ($mockActualHash -ne $mockExpectedHash) { throw "$Algorithm mismatch: $Archive" }
    Write-Output "Verified $Archive ($Algorithm)"
    return $mockArchivePath
}

# These are portable Windows x64 tools, with no global Node/npm installation.
$mockNodeArchiveResult = @(Get-VerifiedMockArchive 'node-v24.18.0-win-x64.zip' `
    'https://nodejs.org/dist/v24.18.0' 'SHASUMS256.txt' 'SHA256')
$mockNodeArchive = $mockNodeArchiveResult[-1]
$mockNodeDirectory = Join-Path $mockRuntime 'node-v24.18.0-win-x64'
if (-not (Test-Path -LiteralPath (Join-Path $mockNodeDirectory 'node.exe'))) {
    Expand-Archive -LiteralPath $mockNodeArchive -DestinationPath $mockRuntime -Force
}
$mockCaddyArchiveResult = @(Get-VerifiedMockArchive 'caddy_2.11.7_windows_amd64.zip' `
    'https://github.com/caddyserver/caddy/releases/download/v2.11.7' 'caddy_2.11.7_checksums.txt' 'SHA512')
$mockCaddyArchive = $mockCaddyArchiveResult[-1]
$mockCaddyDirectory = Join-Path $mockRuntime 'caddy-2.11.7'
if (-not (Test-Path -LiteralPath (Join-Path $mockCaddyDirectory 'caddy.exe'))) {
    Expand-Archive -LiteralPath $mockCaddyArchive -DestinationPath $mockCaddyDirectory -Force
}

$mockOriginalPath = $env:Path
try {
    $env:Path = $mockNodeDirectory + ';' + $env:Path
    & (Join-Path $mockNodeDirectory 'npm.cmd') ci --prefix $PSScriptRoot --ignore-scripts --no-audit --no-fund `
        --cache (Join-Path $mockRuntime 'npm-cache')
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed: $LASTEXITCODE" }
    & (Join-Path $mockNodeDirectory 'node.exe') --version
    & (Join-Path $mockNodeDirectory 'node.exe') (Join-Path $PSScriptRoot 'node_modules/@stoplight/prism-cli/dist/index.js') --version
    & (Join-Path $mockCaddyDirectory 'caddy.exe') version
} finally {
    $env:Path = $mockOriginalPath
}
