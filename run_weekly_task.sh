#!/bin/bash

# Script wrapper para ejecutar la tarea semanal y reiniciar el bot
# Este script es llamado por cron cada lunes a las 3 AM

set -e

LOG_FILE="/app/logs/weekly_task_$(date +\%Y\%m\%d_\%H\%M\%S).log"

echo "=========================================="  | tee -a "$LOG_FILE"
echo "Iniciando tarea semanal de generación de PDFs" | tee -a "$LOG_FILE"
echo "Fecha: $(date)" | tee -a "$LOG_FILE"
echo "=========================================="  | tee -a "$LOG_FILE"

# Ejecutar el script de generación de PDFs
echo "Ejecutando generación de PDFs..." | tee -a "$LOG_FILE"
cd /app
/usr/local/bin/python /app/weekly_pdf_task.py 2>&1 | tee -a "$LOG_FILE"

PDF_EXIT_CODE=${PIPESTATUS[0]}

if [ $PDF_EXIT_CODE -eq 0 ]; then
    echo "✓ Generación de PDFs completada exitosamente" | tee -a "$LOG_FILE"
else
    echo "✗ Generación de PDFs terminó con errores (código: $PDF_EXIT_CODE)" | tee -a "$LOG_FILE"
fi

# Reiniciar el bot
echo "" | tee -a "$LOG_FILE"
echo "Reiniciando bot de Telegram..." | tee -a "$LOG_FILE"

# Encontrar el PID del proceso del bot
BOT_PID=$(pgrep -f "python.*TELEGRAM_BOT.py" | head -n 1)

if [ -n "$BOT_PID" ]; then
    echo "Bot encontrado con PID: $BOT_PID" | tee -a "$LOG_FILE"
    kill -TERM "$BOT_PID"
    sleep 2
    
    # Verificar si terminó
    if ps -p "$BOT_PID" > /dev/null; then
        echo "Bot no terminó, forzando..." | tee -a "$LOG_FILE"
        kill -9 "$BOT_PID"
    fi
    
    echo "✓ Bot detenido" | tee -a "$LOG_FILE"
else
    echo "⚠ No se encontró proceso del bot en ejecución" | tee -a "$LOG_FILE"
fi

# Iniciar el bot nuevamente
echo "Iniciando bot nuevamente..." | tee -a "$LOG_FILE"
cd /app
nohup /usr/local/bin/python /app/TELEGRAM_BOT.py >> /app/logs/bot.log 2>&1 &
NEW_PID=$!

echo "✓ Bot reiniciado con PID: $NEW_PID" | tee -a "$LOG_FILE"

echo "=========================================="  | tee -a "$LOG_FILE"
echo "Tarea semanal completada" | tee -a "$LOG_FILE"
echo "=========================================="  | tee -a "$LOG_FILE"

exit 0
