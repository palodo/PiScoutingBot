#!/bin/bash

# Script de despliegue automatizado en DigitalOcean Droplet
# Ejecutar como: bash deploy_digitalocean.sh

set -e

echo "==================================="
echo "  Despliegue PI Scouting Bot"
echo "  DigitalOcean Droplet"
echo "==================================="
echo ""

# Actualizar sistema
echo "📦 Actualizando sistema..."
sudo apt-get update
sudo apt-get upgrade -y

# Instalar herramientas necesarias
echo "📦 Instalando herramientas necesarias..."
sudo apt-get install -y unzip curl

# Instalar Docker si no está instalado
if ! command -v docker &> /dev/null; then
    echo "🐳 Instalando Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
else
    echo "✅ Docker ya está instalado"
fi

# Instalar Docker Compose si no está instalado
if ! command -v docker-compose &> /dev/null; then
    echo "🐳 Instalando Docker Compose..."
    sudo apt-get install -y docker-compose-plugin
else
    echo "✅ Docker Compose ya está instalado"
fi

# Crear directorio de trabajo
echo "📁 Creando directorio de trabajo..."
mkdir -p ~/pi-scouting-bot
cd ~/pi-scouting-bot

# Crear directorios necesarios
mkdir -p logs data reportes imagenes

echo ""
echo "✅ Instalación completada"
echo ""
echo "Siguiente paso:"
echo "1. Sube los archivos a este droplet:"
echo "   scp pi-scouting-bot-image.tar.zip root@tu-droplet-ip:~/pi-scouting-bot/"
echo "   scp pi-scouting-bot-data.zip root@tu-droplet-ip:~/pi-scouting-bot/"
echo "   scp docker-compose.yml root@tu-droplet-ip:~/pi-scouting-bot/"
echo "   scp .env root@tu-droplet-ip:~/pi-scouting-bot/"
echo ""
echo "2. Ejecuta: bash ~/pi-scouting-bot/start_bot.sh"
