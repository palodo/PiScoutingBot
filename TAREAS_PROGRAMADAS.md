# ⏰ Tareas Programadas - PI Scouting Bot

## 📋 Resumen

El bot está configurado para ejecutar automáticamente la generación masiva de PDFs cada **lunes a las 3:00 AM** (hora de Madrid/España).

Después de completar la generación de PDFs, el bot se reinicia automáticamente para liberar memoria y aplicar un estado limpio.

## 🔧 Componentes

### 1. `weekly_pdf_task.py`
Script Python que:
- Carga todos los jugadores de la temporada actual
- Genera el PDF completo para cada jugador
- Registra logs detallados del proceso
- Reporta estadísticas de éxito/fallos

### 2. `run_weekly_task.sh`
Script bash wrapper que:
- Ejecuta `weekly_pdf_task.py`
- Reinicia el bot de Telegram después
- Registra todo el proceso en logs

### 3. `docker-entrypoint.sh`
Script de inicialización que:
- Configura la zona horaria
- Crea la tarea cron
- Inicia el servicio cron
- Ejecuta el bot de Telegram

## 📅 Configuración del Cron

```bash
# Cada lunes a las 3:00 AM
0 3 * * 1 root /app/run_weekly_task.sh
```

**Formato explicado:**
- `0` = minuto 0
- `3` = hora 3 (3:00 AM)
- `*` = cualquier día del mes
- `*` = cualquier mes
- `1` = lunes (0=domingo, 1=lunes, ..., 6=sábado)

## 🕐 Zona Horaria

Por defecto está configurado para **Europe/Madrid** (GMT+1 / GMT+2 en verano).

Para cambiar la zona horaria, edita en `docker-entrypoint.sh`:
```bash
export TZ=Europe/Madrid  # Cambiar aquí
```

Zonas horarias comunes:
- España: `Europe/Madrid`
- México: `America/Mexico_City`
- Argentina: `America/Argentina/Buenos_Aires`
- Colombia: `America/Bogota`
- Chile: `America/Santiago`

## 📊 Logs

Los logs se guardan en diferentes archivos:

### Logs del Bot
```bash
docker-compose logs -f
```

### Logs de Cron (general)
```bash
cat logs/cron.log
```

### Logs de Generación Semanal
```bash
# Por mes
cat logs/weekly_pdf_generation_202501.log

# Por ejecución específica
cat logs/weekly_task_20250113_030000.log
```

## 🔍 Verificar Configuración

### Ver la configuración de cron actual
```bash
docker-compose exec telegram-bot crontab -l
```

### Ver la zona horaria del contenedor
```bash
docker-compose exec telegram-bot date
```

### Ver próximas ejecuciones programadas
```bash
# Esto no muestra las próximas ejecuciones directamente
# pero puedes verificar que cron está corriendo
docker-compose exec telegram-bot service cron status
```

### Ver logs de cron en tiempo real
```bash
docker-compose exec telegram-bot tail -f /app/logs/cron.log
```

## 🧪 Probar Manualmente

### Ejecutar la generación de PDFs manualmente (sin esperar al lunes)
```bash
# Desde fuera del contenedor
docker-compose exec telegram-bot /app/run_weekly_task.sh

# O solo la generación de PDFs sin reiniciar el bot
docker-compose exec telegram-bot python /app/weekly_pdf_task.py
```

### Cambiar el horario para pruebas

Edita `docker-entrypoint.sh` temporalmente:
```bash
# Para ejecutar cada 5 minutos (solo para pruebas!)
*/5 * * * * root /app/run_weekly_task.sh >> /app/logs/cron.log 2>&1
```

Luego reconstruye:
```bash
docker-compose down
docker-compose up --build
```

**⚠️ IMPORTANTE:** Recuerda volver a poner el horario original después de las pruebas.

## 🔄 Cambiar el Horario de Ejecución

### Ejemplo: Ejecutar los Domingos a las 2:00 AM
Edita `docker-entrypoint.sh`:
```bash
# Cambia de:
0 3 * * 1 root /app/run_weekly_task.sh

# A (0=domingo):
0 2 * * 0 root /app/run_weekly_task.sh
```

### Ejemplo: Ejecutar Todos los Días a las 4:00 AM
```bash
0 4 * * * root /app/run_weekly_task.sh
```

### Ejemplo: Ejecutar Primer Día de Cada Mes a las 1:00 AM
```bash
0 1 1 * * root /app/run_weekly_task.sh
```

Después de cualquier cambio, reconstruye el contenedor:
```bash
docker-compose down
docker-compose up --build -d
```

## 📈 Monitoreo

### Ver el estado después de una ejecución programada

```bash
# Ver logs recientes
docker-compose logs --tail=100

# Ver log específico de la tarea semanal
ls -lh logs/weekly_task_*

# Ver el último log de tarea semanal
cat $(ls -t logs/weekly_task_* | head -n1)
```

### Alertas por Email (Opcional)

Si quieres recibir emails cuando la tarea falla, puedes configurar `msmtp` en el contenedor o usar un servicio externo como:
- SendGrid
- Mailgun
- AWS SES

## 🐛 Troubleshooting

### La tarea no se ejecuta

1. **Verificar que cron está corriendo:**
```bash
docker-compose exec telegram-bot service cron status
```

2. **Ver logs de cron:**
```bash
cat logs/cron.log
```

3. **Verificar la configuración de cron:**
```bash
docker-compose exec telegram-bot cat /etc/cron.d/weekly-pdf-generation
```

4. **Verificar zona horaria:**
```bash
docker-compose exec telegram-bot date
```

### El bot no se reinicia después de la tarea

Revisa el log de la tarea semanal:
```bash
cat logs/weekly_task_*.log
```

Busca mensajes de error en el reinicio del bot.

### Probar manualmente la tarea

```bash
# Ejecutar todo el proceso
docker-compose exec telegram-bot /app/run_weekly_task.sh

# Solo generar PDFs
docker-compose exec telegram-bot python /app/weekly_pdf_task.py
```

## 🔐 Permisos

Si tienes problemas de permisos con los logs:
```bash
# Desde el servidor
chmod -R 777 logs/
```

O ajusta el docker-compose.yml para que el usuario del contenedor coincida con tu usuario del host.

## 💡 Consejos

1. **Revisa los logs semanalmente** para asegurarte de que todo funciona correctamente
2. **Mantén espacio en disco suficiente** para los PDFs generados
3. **Considera hacer backup** de los PDFs periódicamente
4. **Monitorea el uso de memoria** durante la generación masiva de PDFs
5. **Ajusta el horario** según tu zona horaria y carga del servidor

## 📞 Notificaciones a Telegram (Opcional)

Puedes modificar `weekly_pdf_task.py` para enviar un mensaje de Telegram cuando complete:

```python
# Al final de la función main(), agregar:
try:
    import requests
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = "TU_CHAT_ID"  # ID del chat donde enviar notificación
    mensaje = f"✅ Generación semanal completada\n\n"
    mensaje += f"Exitosos: {exitosos}\n"
    mensaje += f"Fallidos: {fallidos}\n"
    mensaje += f"Total: {total_jugadores}"
    
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": mensaje}
    )
except Exception as e:
    logger.error(f"No se pudo enviar notificación: {e}")
```

## 🎯 Resumen de Comandos Útiles

```bash
# Ver logs en tiempo real
docker-compose logs -f

# Ejecutar tarea manualmente
docker-compose exec telegram-bot /app/run_weekly_task.sh

# Ver estado de cron
docker-compose exec telegram-bot service cron status

# Ver hora actual del contenedor
docker-compose exec telegram-bot date

# Ver últimos logs de generación
tail -100 logs/weekly_pdf_generation_*.log

# Reiniciar todo después de cambios
docker-compose down && docker-compose up --build -d
```
