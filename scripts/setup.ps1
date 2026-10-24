$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot '.env'
function New-RandomSecret {
    $bytes = New-Object byte[] 48
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($bytes)
}
if (Test-Path -LiteralPath $envPath) {
    $existing = [System.IO.File]::ReadAllText($envPath)
    $addedSettings = @()
    if ($existing -notmatch '(?m)^COLETA_TOKEN=.+$') {
        $existing = $existing -replace '(?m)^COLETA_TOKEN=.*\r?\n?', ''
        $existing = $existing.TrimEnd() + "`nCOLETA_TOKEN=$(New-RandomSecret)`n"
        $addedSettings += 'Credencial local de coleta'
    }
    if ($existing -notmatch '(?m)^DJANGO_DEBUG=') {
        $existing = $existing.TrimEnd() + "`nDJANGO_DEBUG=true`n"
        $addedSettings += 'DJANGO_DEBUG=true para desenvolvimento local'
    }
    if ($addedSettings.Count -gt 0) {
        [System.IO.File]::WriteAllText($envPath, $existing, [System.Text.UTF8Encoding]::new($false))
        Write-Host "$($addedSettings -join ' e ') adicionados ao .env. Os demais valores foram preservados."
    } else { Write-Host 'O arquivo .env já existe e foi preservado.' }
    exit 0
}
$lines = @(
    "DJANGO_SECRET_KEY=$(New-RandomSecret)",
    "POSTGRES_PASSWORD=$(New-RandomSecret)",
    'POSTGRES_DB=sme',
    'POSTGRES_USER=sme',
    'DJANGO_DEBUG=true',
    "COLETA_TOKEN=$(New-RandomSecret)"
)
[System.IO.File]::WriteAllLines($envPath, $lines, [System.Text.UTF8Encoding]::new($false))
Write-Host 'Configuração local criada. Os segredos não foram exibidos.'
Write-Host 'Próximo passo: docker compose up --build -d'
