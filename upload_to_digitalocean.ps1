# Script automatizado para subir a DigitalOcean desde Windows

# Configuración
$DROPLET_IP = Read-Host "Ingresa la IP de tu droplet de DigitalOcean"
$DROPLET_USER = "root"

Write-Host "==================================="
Write-Host "  Deploy a DigitalOcean"
Write-Host "  IP: $DROPLET_IP"
Write-Host "==================================="
Write-Host ""

# Verificar archivos locales
Write-Host "Verificando archivos locales..." -ForegroundColor Yellow
$archivos_necesarios = @(
    "pi-scouting-bot-image.tar.zip",
    "pi-scouting-bot-data.zip",
    "docker-compose.yml",
    ".env",
    "start_bot.sh"
)

foreach ($archivo in $archivos_necesarios) {
    if (-not (Test-Path $archivo)) {
        Write-Host "ERROR: No se encuentra $archivo" -ForegroundColor Red
        exit 1
    }
}
Write-Host "Todos los archivos encontrados" -ForegroundColor Green
Write-Host ""

# Subir archivos
Write-Host "Subiendo archivos al droplet..." -ForegroundColor Yellow
Write-Host "Esto puede tardar varios minutos dependiendo de tu conexión..."
Write-Host ""

foreach ($archivo in $archivos_necesarios) {
    Write-Host "Subiendo $archivo..." -ForegroundColor Cyan
    scp $archivo "${DROPLET_USER}@${DROPLET_IP}:~/pi-scouting-bot/"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  $archivo subido correctamente" -ForegroundColor Green
    } else {
        Write-Host "  ERROR subiendo $archivo" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Archivos subidos correctamente" -ForegroundColor Green
Write-Host ""
Write-Host "Siguiente paso: Conecta al droplet e inicia el bot" -ForegroundColor Yellow
Write-Host ""
Write-Host "Comandos:" -ForegroundColor Cyan
Write-Host "  ssh ${DROPLET_USER}@${DROPLET_IP}"
Write-Host "  cd ~/pi-scouting-bot"
Write-Host "  chmod +x start_bot.sh"
Write-Host "  ./start_bot.sh"
Write-Host ""
Write-Host "¿Quieres conectar ahora? (S/N)" -ForegroundColor Yellow
$respuesta = Read-Host
if ($respuesta -eq "S" -or $respuesta -eq "s") {
    ssh "${DROPLET_USER}@${DROPLET_IP}"
}
