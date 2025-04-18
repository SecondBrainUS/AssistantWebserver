# load-env.ps1
Get-Content .env.build | ForEach-Object {
    if ($_ -match "^\s*#") { return }       # skip comments
    if ($_ -match "^\s*$") { return }       # skip blank lines
    $parts = $_ -split '=', 2
    $key = $parts[0].Trim()
    $val = $parts[1].Trim()
    $env:$key = $val
    Write-Host "Loaded: $key"
}