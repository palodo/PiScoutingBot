#!/bin/bash

# Script de configuración inicial para servidor Digital Ocean
# Ejecutar este script la primera vez que configures el servidor

set -e  # Exit on error

echo "=========================================="
echo "  PI Scouting Bot - Initial Setup"
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
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar que se ejecuta como root
if [ "$EUID" -ne 0 ]; then 
    log_error "Por favor, ejecuta este script como root (usa sudo)"
    exit 1
fi

# Actualizar sistema
log_info "Actualizando sistema..."
apt-get update && apt-get upgrade -y

# Instalar dependencias del sistema
log_info "Instalando dependencias del sistema..."
apt-get install -y \
    git \
    curl \
    wget \
    ca-certificates \
    gnupg \
    lsb-release

# Instalar Docker
log_info "Instalando Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    log_info "Docker instalado correctamente"
else
    log_warning "Docker ya está instalado"
fi

# Instalar Docker Compose
log_info "Instalando Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    log_info "Docker Compose instalado correctamente"
else
    log_warning "Docker Compose ya está instalado"
fi

# Crear directorio de aplicación
log_info "Creando directorio de aplicación..."
mkdir -p $APP_DIR
cd $APP_DIR

# Clonar repositorio
log_info "Clonando repositorio..."
if [ -d ".git" ]; then
    log_warning "Repositorio ya existe, actualizando..."
    git fetch origin
    git checkout $BRANCH
    git pull origin $BRANCH
else
    git clone -b $BRANCH $REPO_URL .
fi

# Crear archivo .env
log_info "Configurando variables de entorno..."
if [ ! -f .env ]; then
    cp .env.example .env
    log_warning "Archivo .env creado. IMPORTANTE: Debes editar este archivo con tu TELEGRAM_TOKEN"
    log_info "Usa: nano $APP_DIR/.env"
else
    log_warning "Archivo .env ya existe, no se sobrescribirá"
fi

# Crear directorios necesarios
log_info "Creando directorios necesarios..."
mkdir -p data logs reportes debug_html

# Configurar permisos
log_info "Configurando permisos..."
chown -R root:root $APP_DIR
chmod +x deploy.sh

# Configurar Docker para iniciar al boot
log_info "Configurando Docker para iniciar automáticamente..."
systemctl enable docker
systemctl start docker

# Configurar firewall (opcional)
log_warning "Configuración de firewall omitida. El bot solo necesita conectarse a Internet (salida), no necesita puertos de entrada abiertos."

echo ""
log_info "=========================================="
log_info "  Configuración Inicial Completada"
log_info "=========================================="
echo ""
log_info "Próximos pasos:"
echo ""
echo "1. Edita el archivo .env con tu token de Telegram:"
echo "   nano $APP_DIR/.env"
echo ""
echo "2. Una vez configurado el token, ejecuta el script de despliegue:"
echo "   cd $APP_DIR && ./deploy.sh"
echo ""
echo "3. Para actualizaciones futuras, solo ejecuta:"
echo "   cd $APP_DIR && ./deploy.sh"
echo ""
log_info "El bot se iniciará automáticamente cuando el servidor se reinicie."
echo ""
