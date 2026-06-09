$ErrorActionPreference = "Stop"

$companionRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$tauriRoot = Join-Path $companionRoot "src-tauri"
$releaseDir = Join-Path $tauriRoot "target\release"
$bundleDir = Join-Path $releaseDir "bundle"
$bundleTargets = @(
    Join-Path $bundleDir "nsis"
)

Write-Host "[marouba] Preparing Windows installer output..."

Get-Process marouba-companion -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 300

foreach ($dir in $bundleTargets) {
    if (Test-Path -LiteralPath $dir) {
        Get-ChildItem -LiteralPath $dir -Force -Recurse -ErrorAction SilentlyContinue |
            ForEach-Object {
                try {
                    $_.Attributes = $_.Attributes -band (-bnot [System.IO.FileAttributes]::ReadOnly)
                } catch {
                    Write-Warning "[marouba] Could not clear read-only flag on $($_.FullName): $($_.Exception.Message)"
                }
            }
        Remove-Item -LiteralPath $dir -Recurse -Force
    }

    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $probe = Join-Path $dir ".marouba-write-test"
    Set-Content -LiteralPath $probe -Value "ok" -Encoding ASCII
    Remove-Item -LiteralPath $probe -Force
}

Write-Host "[marouba] Installer output is writable."
