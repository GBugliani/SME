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
    if ($existing -notmatch '(?m)^COLETA_TOKEN=.+$') {
        $existing = $existing -replace '(?m)^COLETA_TOKEN=.*\r?\n?', ''
        [System.IO.File]::WriteAllText($envPath, $existing.TrimEnd() + "`nCOLETA_TOKEN=$(New-RandomSecret)`n", [System.Text.UTF8Encoding]::new($false))
        Write-Host 'Credencial local de coleta adicionada. Os demais segredos foram preservados.'
    } else { Write-Host 'O arquivo .env já existe e foi preservado.' }
    exit 0
}
$lines = @(
    "DJANGO_SECRET_KEY=$(New-RandomSecret)",
    "POSTGRES_PASSWORD=$(New-RandomSecret)",
    'POSTGRES_DB=sme',
    'POSTGRES_USER=sme',
    "COLETA_TOKEN=$(New-RandomSecret)"
)
[System.IO.File]::WriteAllLines($envPath, $lines, [System.Text.UTF8Encoding]::new($false))
Write-Host 'Configuração local criada. Os segredos não foram exibidos.'
Write-Host 'Próximo passo: docker compose up --build -d'
