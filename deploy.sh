#!/bin/bash

# Script de despliegue para Digital Ocean
# Este script automatiza el proceso de despliegue del bot

set -e  # Exit on error

echo "=========================================="
echo "  PI Scouting Bot - Deployment Script"
echo "=========================================="
echo ""

# Variables de configuración
APP_DIR="/opt/pi-scouting-bot"
REPO_URL="https://github.com/palodo/PiScoutingBot.git"
BRANCH="feature/dev_ivan"

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Función para mostrar mensajes
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar que estamos en el directorio correcto
log_info "Verificando directorio de aplicación..."
if [ ! -d "$APP_DIR" ]; then
    log_error "Directorio $APP_DIR no existe. Por favor, ejecuta primero el script de instalación inicial."
    exit 1
fi

cd $APP_DIR

# Pull latest changes
log_info "Descargando últimos cambios del repositorio..."
git fetch origin
git checkout $BRANCH
git pull origin $BRANCH

# Verificar que existe el archivo .env
if [ ! -f .env ]; then
    log_warning "Archivo .env no encontrado. Copiando desde .env.example..."
    cp .env.example .env
    log_error "Por favor, edita el archivo .env con tu TELEGRAM_TOKEN antes de continuar."
    log_info "Usa: nano $APP_DIR/.env"
    exit 1
fi

# Rebuild and restart containers
log_info "Reconstruyendo imagen Docker..."
docker-compose build --no-cache

log_info "Deteniendo contenedores antiguos..."
docker-compose down

log_info "Iniciando contenedores..."
docker-compose up -d

# Wait for container to start
sleep 5

# Check if container is running
if docker-compose ps | grep -q "Up"; then
    log_info "✓ Bot desplegado exitosamente!"
    log_info "Verificando logs..."
    docker-compose logs --tail=20
else
    log_error "✗ El contenedor no está corriendo. Verificando logs..."
    docker-compose logs --tail=50
    exit 1
fi

echo ""
log_info "Comandos útiles:"
echo "  - Ver logs en tiempo real: docker-compose logs -f"
echo "  - Detener el bot: docker-compose down"
echo "  - Reiniciar el bot: docker-compose restart"
echo "  - Ver estado: docker-compose ps"
echo ""
