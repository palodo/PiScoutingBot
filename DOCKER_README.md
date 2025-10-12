# PI Scouting Bot - Docker Setup

## Construir y ejecutar

```bash
docker-compose up --build -d
```

## Ver logs

```bash
# Logs del bot
docker-compose logs -f scouting-bot

# Logs de actualizaciones semanales
docker exec pi-scouting-bot cat /app/logs/update.log

# Logs del scraper
docker exec pi-scouting-bot cat /app/logs/scraper.log
```

## Detener

```bash
docker-compose down
```

## Actualización manual

```bash
docker exec pi-scouting-bot /bin/bash /app/update_weekly.sh
```

## Variables de entorno

Configurar en `.env`:
- TELEGRAM_TOKEN
- OPENAI_API_KEY
