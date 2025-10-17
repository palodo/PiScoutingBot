#!/bin/bash

# Script de entrada que configura cron y ejecuta el bot
# Este script se ejecuta cuando el contenedor inicia

set -e

echo "Inicializando contenedor del bot PI Scouting..."

# Configurar zona horaria (ajusta según tu ubicación)
# Para España (Madrid):
export TZ=Europe/Madrid
ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Dar permisos de ejecución al script wrapper
chmod +x /app/run_weekly_task.sh

# Crear archivo de cron
echo "Configurando tarea programada (cron)..."

# Cada lunes a las 3:00 AM ejecutar el script de generación de PDFs y reiniciar
# Formato cron: minuto hora día-del-mes mes día-de-la-semana
# 1 = Lunes
cat > /etc/cron.d/weekly-pdf-generation << EOF
# Ejecutar cada lunes a las 3:00 AM (hora de Madrid)
0 3 * * 1 root /app/run_weekly_task.sh >> /app/logs/cron.log 2>&1

# Línea en blanco requerida al final del archivo cron
EOF

# Dar permisos al archivo cron
chmod 0644 /etc/cron.d/weekly-pdf-generation

# Aplicar el crontab
crontab /etc/cron.d/weekly-pdf-generation

echo "Tarea programada configurada: cada lunes a las 3:00 AM"
echo "Zona horaria: $TZ"

# Iniciar cron en background
echo "Iniciando servicio cron..."
service cron start

# Mostrar info de configuración
echo "=========================================="
echo "Bot PI Scouting - Contenedor iniciado"
echo "Fecha actual: $(date)"
echo "Zona horaria: $(cat /etc/timezone)"
echo "=========================================="
echo ""
echo "Próximas ejecuciones programadas:"
echo "  - Generación de PDFs: Cada lunes a las 3:00 AM"
echo ""
echo "Logs disponibles en:"
echo "  - Bot: docker-compose logs -f"
echo "  - Cron: logs/cron.log"
echo "  - PDFs semanales: logs/weekly_pdf_generation_*.log"
echo ""
echo "=========================================="
echo "Iniciando bot de Telegram..."
echo "=========================================="
echo ""

# Ejecutar el bot de Telegram
exec python TELEGRAM_BOT.py
