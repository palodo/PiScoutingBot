#!/bin/bash

# Script para desplegar en máquina remota

echo "=== Descomprimiendo y cargando imagen Docker ==="
gunzip -c pi-scouting-bot-image.tar.gz | docker load

echo "=== Extrayendo datos ==="
tar -xzf pi-scouting-bot-data.tar.gz

echo "=== Creando directorios necesarios ==="
mkdir -p logs reportes

echo "=== Verificando .env ==="
if [ ! -f .env ]; then
    echo "❌ ERROR: Archivo .env no encontrado"
    echo "Crea el archivo .env con:"
    echo "TELEGRAM_TOKEN=tu_token_aqui"
    echo "OPENAI_API_KEY=tu_api_key_aqui"
    exit 1
fi

echo "=== Iniciando contenedor ==="
docker-compose up -d

echo ""
echo "✅ Despliegue completado"
echo ""
echo "Comandos útiles:"
echo "  Ver logs:        docker logs -f pi-scouting-bot"
echo "  Ver estado:      docker ps"
echo "  Detener:         docker-compose down"
echo "  Actualizar:      docker exec pi-scouting-bot /bin/bash /app/update_weekly.sh"
