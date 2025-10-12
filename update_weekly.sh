#!/bin/bash

# Script de actualización semanal
# Se ejecuta los lunes a las 3 AM

echo "$(date): Iniciando actualización semanal..." >> /app/logs/update.log

# 1. Ejecutar multi_season_scraper
echo "$(date): Ejecutando multi_season_scraper..." >> /app/logs/update.log
cd /app
python scrapping_folder/multi_season_scraper.py >> /app/logs/scraper.log 2>&1

if [ $? -eq 0 ]; then
    echo "$(date): multi_season_scraper completado con éxito" >> /app/logs/update.log
else
    echo "$(date): ERROR en multi_season_scraper" >> /app/logs/update.log
    exit 1
fi

# 2. Ejecutar shortchart_scraper
echo "$(date): Ejecutando shortchart_scraper..." >> /app/logs/update.log
python scrapping_folder/shortchart_scraper.py >> /app/logs/scraper.log 2>&1

if [ $? -eq 0 ]; then
    echo "$(date): shortchart_scraper completado con éxito" >> /app/logs/update.log
else
    echo "$(date): ERROR en shortchart_scraper" >> /app/logs/update.log
    exit 1
fi

# 3. Reiniciar el bot de Telegram
echo "$(date): Reiniciando bot de Telegram..." >> /app/logs/update.log
pkill -f TELEGRAM_BOT.py
sleep 2
nohup python /app/TELEGRAM_BOT.py >> /app/logs/bot.log 2>&1 &

echo "$(date): Actualización completada y bot reiniciado" >> /app/logs/update.log
