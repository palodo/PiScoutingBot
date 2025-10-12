#!/bin/bash

# Script para exportar la imagen Docker y los datos

echo "=== Exportando imagen Docker ==="
docker save deploy-scouting-bot:latest -o pi-scouting-bot-image.tar

echo "=== Comprimiendo imagen ==="
gzip pi-scouting-bot-image.tar

echo "=== Creando backup de datos ==="
tar -czf pi-scouting-bot-data.tar.gz data/ imagenes/

echo ""
echo "✅ Archivos generados:"
echo "  - pi-scouting-bot-image.tar.gz (imagen Docker)"
echo "  - pi-scouting-bot-data.tar.gz (datos)"
echo ""
echo "Transfiere estos archivos a la máquina destino junto con:"
echo "  - docker-compose.yml"
echo "  - .env"
echo "  - deploy_remote.sh"
