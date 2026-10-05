$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot '.env'
if (Test-Path -LiteralPath $envPath) {
    Write-Host 'O arquivo .env já existe e foi preservado.'
    exit 0
}
function New-RandomSecret {
    $bytes = New-Object byte[] 48
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($bytes)
}
$lines = @(
    "DJANGO_SECRET_KEY=$(New-RandomSecret)",
    "POSTGRES_PASSWORD=$(New-RandomSecret)",
    'POSTGRES_DB=sme',
    'POSTGRES_USER=sme'
)
[System.IO.File]::WriteAllLines($envPath, $lines, [System.Text.UTF8Encoding]::new($false))
Write-Host 'Configuração local criada. Os segredos não foram exibidos.'
Write-Host 'Próximo passo: docker compose up --build -d'
