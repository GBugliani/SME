$ErrorActionPreference = 'Continue'
Write-Host 'Ferramentas disponíveis no PATH:'
foreach ($tool in @('docker', 'git', 'python', 'node', 'npm')) {
    $found = Get-Command $tool -ErrorAction SilentlyContinue
    if ($found) { Write-Host "$tool : $($found.Source)" }
    else { Write-Host "$tool : não encontrado" }
}
if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker --version
    docker compose version
    docker info --format '{{.ServerVersion}}'
}
Write-Host 'Para executar com Docker, Python/Node/PostgreSQL locais são opcionais.'
