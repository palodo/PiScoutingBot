# 🚀 Inicio Rápido - PI Scouting Bot con Docker

## ⚡ En 5 minutos en Digital Ocean

### 1️⃣ Crea un Droplet
- Ve a [digitalocean.com](https://digitalocean.com)
- Create → Droplets
- **Ubuntu 22.04 LTS**
- **$12/mes** (2GB RAM - recomendado)
- Click "Create"

### 2️⃣ Conéctate al servidor
```bash
ssh root@TU_IP_DROPLET
```

### 3️⃣ Ejecuta el script de setup
```bash
wget https://raw.githubusercontent.com/palodo/PiScoutingBot/feature/dev_ivan/setup_server.sh
chmod +x setup_server.sh
./setup_server.sh
```

### 4️⃣ Configura tu token
```bash
nano /opt/pi-scouting-bot/.env
```
Cambia `your_telegram_bot_token_here` por tu token real
Guarda: `Ctrl+X` → `Y` → `Enter`

### 5️⃣ Despliega el bot
```bash
cd /opt/pi-scouting-bot
./deploy.sh
```

✅ **¡Listo!** Tu bot está corriendo 24/7

---

## 🧪 Prueba Local (Desarrollo)

### Requisitos
- Docker Desktop instalado
- Git

### Pasos
```powershell
# 1. Clonar el repo (si aún no lo tienes)
cd c:\Users\Pablo\Desktop\deploy

# 2. Crear archivo .env
Copy-Item .env.example .env
notepad .env  # Añade tu TELEGRAM_TOKEN

# 3. Ejecutar
docker-compose up --build

# Ver logs
docker-compose logs -f

# Detener (en otra terminal)
docker-compose down
```

---

## 📋 Comandos Esenciales

```bash
# Ver logs en tiempo real
docker-compose logs -f

# Reiniciar el bot
docker-compose restart

# Actualizar con nuevos cambios
./deploy.sh

# Ver estado
docker-compose ps

# Ejecutar generación de PDFs manualmente
docker-compose exec telegram-bot /app/run_weekly_task.sh

# Ver logs de generación semanal
cat logs/weekly_pdf_generation_*.log
```

---

## ⏰ Generación Automática de PDFs

- **Cuándo**: Cada lunes a las 3:00 AM
- **Qué hace**: Genera PDFs de todos los jugadores
- **Después**: Reinicia el bot automáticamente
- **Zona horaria**: Europe/Madrid

### Cambiar horario
Edita `docker-entrypoint.sh` → línea del cron
Reconstruye: `docker-compose up --build -d`

---

## 📚 Documentación Completa

- **README_DOCKER.md** - Guía completa de despliegue
- **TAREAS_PROGRAMADAS.md** - Configuración de tareas automáticas
- **RESUMEN_CAMBIOS.md** - Todos los archivos y cambios realizados

---

## ❓ Problemas Comunes

### El bot no inicia
```bash
docker-compose logs
# Revisa el error y verifica que el token sea correcto
```

### La tarea programada no se ejecuta
```bash
# Ver configuración de cron
docker-compose exec telegram-bot crontab -l

# Ver hora del contenedor
docker-compose exec telegram-bot date

# Ver logs de cron
cat logs/cron.log
```

### Sin espacio en disco
```bash
# Limpiar imágenes antiguas
docker system prune -a

# Ver espacio disponible
df -h
```

---

## 💰 Costos

- **Droplet básico**: $6/mes (1GB RAM)
- **Droplet recomendado**: $12/mes (2GB RAM)
- Incluye: 25GB SSD + 1TB transferencia

---

## 🎯 Próximos Pasos

1. ✅ Despliega el bot
2. 📊 Monitorea logs la primera semana
3. 🔧 Ajusta horarios según necesidad
4. 💾 Configura backups (opcional)

---

## 📞 Ayuda

¿Problemas? Revisa:
1. `docker-compose logs` para ver errores
2. La documentación completa en `README_DOCKER.md`
3. Configuración de tareas en `TAREAS_PROGRAMADAS.md`

---

**¡Feliz scouting! 🏀**
