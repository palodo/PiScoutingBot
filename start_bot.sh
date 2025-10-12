#!/bin/bash

# Script para iniciar el bot en DigitalOcean
# Ejecutar después de subir los archivos

set -e

cd ~/pi-scouting-bot

echo "==================================="
echo "  Iniciando PI Scouting Bot"
echo "==================================="
echo ""

# Verificar que existen los archivos necesarios
if [ ! -f "pi-scouting-bot-image.tar.zip" ]; then
    echo "❌ ERROR: No se encuentra pi-scouting-bot-image.tar.zip"
    exit 1
fi

if [ ! -f "docker-compose.yml" ]; then
    echo "❌ ERROR: No se encuentra docker-compose.yml"
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "❌ ERROR: No se encuentra .env"
    echo "Crea el archivo .env con:"
    echo "TELEGRAM_TOKEN=tu_token"
    echo "OPENAI_API_KEY=tu_key"
    exit 1
fi

# Instalar unzip si no está disponible
if ! command -v unzip &> /dev/null; then
    echo "📦 Instalando unzip..."
    sudo apt-get update
    sudo apt-get install -y unzip
fi

# Descomprimir imagen Docker
if [ ! -f "pi-scouting-bot-image.tar" ]; then
    echo "📦 Descomprimiendo imagen Docker..."
    unzip -q pi-scouting-bot-image.tar.zip
fi

# Cargar imagen en Docker
echo "🐳 Cargando imagen en Docker..."
docker load -i pi-scouting-bot-image.tar

# Descomprimir datos si existen
if [ -f "pi-scouting-bot-data.zip" ]; then
    echo "📦 Descomprimiendo datos..."
    unzip -o pi-scouting-bot-data.zip 2>&1 | grep -v "warning" || true
    echo "✅ Datos descomprimidos"
fi

# Iniciar contenedor
echo "🚀 Iniciando contenedor..."
docker compose up -d

# Esperar a que inicie
sleep 5

# Verificar estado
echo ""
echo "✅ Bot desplegado correctamente"
echo ""
echo "Estado del contenedor:"
docker ps | grep pi-scouting-bot

echo ""
echo "📊 Ver logs en tiempo real:"
echo "   docker logs -f pi-scouting-bot"
echo ""
echo "🔄 Reiniciar bot:"
echo "   docker compose restart"
echo ""
echo "🛑 Detener bot:"
echo "   docker compose down"
