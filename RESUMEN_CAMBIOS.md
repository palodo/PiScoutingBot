# 📝 Resumen de Cambios - Dockerización + Tareas Programadas

## ✅ Archivos Creados

### 🐳 Docker y Despliegue

1. **`Dockerfile`**
   - Imagen base: Python 3.11-slim
   - Instala dependencias del sistema (cron, tzdata, supervisor)
   - Configura zona horaria Europe/Madrid
   - Instala dependencias Python desde requirements.txt
   - Copia el código de la aplicación
   - Configura entrypoint para inicialización

2. **`.dockerignore`**
   - Excluye archivos innecesarios del build de Docker
   - Evita incluir cache, logs, y archivos de desarrollo

3. **`docker-compose.yml`**
   - Orquesta el contenedor
   - Configura reinicio automático (`restart: unless-stopped`)
   - Monta volúmenes para persistencia de datos
   - Configura límites de memoria (1GB)

4. **`.env.example`**
   - Plantilla para variables de entorno
   - Template para el TELEGRAM_TOKEN

### ⏰ Tareas Programadas

5. **`weekly_pdf_task.py`**
   - Script Python que genera PDFs de todos los jugadores
   - Lee datos de `data/datos_historicos.json`
   - Genera logs detallados del proceso
   - Reporta estadísticas de éxito/fallos

6. **`run_weekly_task.sh`**
   - Script wrapper bash
   - Ejecuta `weekly_pdf_task.py`
   - Reinicia el bot después de completar
   - Registra todo en logs

7. **`docker-entrypoint.sh`**
   - Script de inicialización del contenedor
   - Configura zona horaria
   - Crea y activa tarea cron
   - Inicia servicio cron
   - Ejecuta el bot de Telegram

### 📚 Documentación

8. **`README_DOCKER.md`**
   - Guía completa de despliegue en Digital Ocean
   - Instrucciones paso a paso
   - Comandos útiles
   - Troubleshooting

9. **`TAREAS_PROGRAMADAS.md`**
   - Documentación detallada de cron
   - Cómo cambiar horarios
   - Cómo cambiar zona horaria
   - Cómo monitorear las tareas
   - Ejemplos de diferentes configuraciones

### 🚀 Scripts de Despliegue

10. **`setup_server.sh`**
    - Configuración inicial del servidor Digital Ocean
    - Instala Docker y Docker Compose
    - Clona el repositorio
    - Prepara el entorno

11. **`deploy.sh`**
    - Script de despliegue y actualización
    - Pull de últimos cambios
    - Rebuild de imagen Docker
    - Reinicio de contenedores

## 🎯 Funcionalidades Implementadas

### ✨ Nueva: Generación Automática Semanal de PDFs

**Configuración:**
- 📅 **Frecuencia**: Cada lunes
- 🕒 **Hora**: 3:00 AM
- 🌍 **Zona horaria**: Europe/Madrid (GMT+1 / GMT+2 en verano)
- 🔄 **Post-ejecución**: Reinicio automático del bot

**Proceso:**
1. Cada lunes a las 3:00 AM, cron ejecuta `run_weekly_task.sh`
2. El script ejecuta `weekly_pdf_task.py`
3. Se generan PDFs para todos los jugadores de la temporada 2025
4. Se registran logs detallados
5. El bot se reinicia automáticamente
6. Todo vuelve a funcionar normalmente

**Logs generados:**
- `/app/logs/cron.log` - Log general de cron
- `/app/logs/weekly_pdf_generation_YYYYMM.log` - Log mensual consolidado
- `/app/logs/weekly_task_YYYYMMDD_HHMMSS.log` - Log de cada ejecución específica

### 🐳 Dockerización Completa

**Beneficios:**
- ✅ Entorno reproducible y consistente
- ✅ Fácil despliegue en cualquier servidor
- ✅ Reinicio automático en caso de errores
- ✅ Persistencia de datos fuera del contenedor
- ✅ Fácil actualización con un solo comando
- ✅ Aislamiento del sistema host

**Volúmenes persistentes:**
```yaml
- ./data:/app/data           # Datos de jugadores
- ./logs:/app/logs           # Logs de operaciones
- ./reportes:/app/reportes   # PDFs generados
- ./debug_html:/app/debug_html  # HTML de debug
```

## 🚀 Cómo Usar

### Prueba Local (Desarrollo)

```powershell
# 1. Crear archivo .env
Copy-Item .env.example .env
# Edita .env y añade tu TELEGRAM_TOKEN

# 2. Construir y ejecutar
docker-compose up --build

# Ver logs
docker-compose logs -f

# Detener
docker-compose down
```

### Despliegue en Digital Ocean (Producción)

```bash
# 1. Crear Droplet en Digital Ocean (Ubuntu 22.04)

# 2. Conectar por SSH
ssh root@IP_DEL_DROPLET

# 3. Ejecutar setup inicial
curl -o setup_server.sh https://raw.githubusercontent.com/palodo/PiScoutingBot/feature/dev_ivan/setup_server.sh
chmod +x setup_server.sh
sudo ./setup_server.sh

# 4. Configurar token
nano /opt/pi-scouting-bot/.env
# Añadir: TELEGRAM_TOKEN=tu_token_aqui

# 5. Desplegar
cd /opt/pi-scouting-bot
./deploy.sh
```

### Actualizaciones Futuras

```bash
# Solo necesitas ejecutar:
cd /opt/pi-scouting-bot
./deploy.sh

# El script automáticamente:
# - Descarga últimos cambios
# - Reconstruye imagen
# - Reinicia el bot
```

## 📊 Comandos Útiles

```bash
# Ver logs en tiempo real
docker-compose logs -f

# Ver logs de generación semanal
cat logs/weekly_pdf_generation_*.log

# Ejecutar generación manual (sin esperar al lunes)
docker-compose exec telegram-bot /app/run_weekly_task.sh

# Ver estado del bot
docker-compose ps

# Reiniciar el bot
docker-compose restart

# Ver uso de recursos
docker stats

# Ver hora del contenedor
docker-compose exec telegram-bot date

# Ver configuración de cron
docker-compose exec telegram-bot crontab -l
```

## 🔧 Personalización

### Cambiar horario de generación de PDFs

Edita `docker-entrypoint.sh`:

```bash
# Actual: Cada lunes a las 3:00 AM
0 3 * * 1 root /app/run_weekly_task.sh

# Cambiar a: Domingos a las 2:00 AM
0 2 * * 0 root /app/run_weekly_task.sh

# Cambiar a: Todos los días a las 4:00 AM
0 4 * * * root /app/run_weekly_task.sh
```

Luego reconstruye:
```bash
docker-compose down
docker-compose up --build -d
```

### Cambiar zona horaria

Edita `docker-entrypoint.sh`:

```bash
# Actual: España
export TZ=Europe/Madrid

# México
export TZ=America/Mexico_City

# Argentina
export TZ=America/Argentina/Buenos_Aires
```

## ⚙️ Variables de Entorno

### Requeridas

- `TELEGRAM_TOKEN` - Token del bot de Telegram (obtener de @BotFather)

### Opcionales (ya configuradas)

- `TZ=Europe/Madrid` - Zona horaria del contenedor
- `PYTHONUNBUFFERED=1` - Output inmediato de Python

## 📦 Estructura del Proyecto

```
deploy/
├── TELEGRAM_BOT.py              # Bot principal
├── weekly_pdf_task.py           # Script de generación semanal (NUEVO)
├── run_weekly_task.sh           # Wrapper para tarea semanal (NUEVO)
├── docker-entrypoint.sh         # Inicialización del contenedor (NUEVO)
├── Dockerfile                   # Configuración Docker (NUEVO)
├── docker-compose.yml           # Orquestación (NUEVO)
├── .dockerignore               # Exclusiones Docker (NUEVO)
├── .env.example                # Template variables (NUEVO)
├── setup_server.sh             # Setup inicial servidor (NUEVO)
├── deploy.sh                   # Script de despliegue (NUEVO)
├── README_DOCKER.md            # Guía de despliegue (NUEVO)
├── TAREAS_PROGRAMADAS.md       # Docs de cron (NUEVO)
├── requirements.txt            # Dependencias Python
├── data/                       # Datos persistentes
├── logs/                       # Logs persistentes
├── reportes/                   # PDFs generados
└── pdf_generator/              # Módulo de PDFs
    └── final_pdf.py
```

## 🔐 Seguridad

✅ **Implementado:**
- Token en variable de entorno (no en código)
- `.env` en `.gitignore`
- `.dockerignore` excluye archivos sensibles

⚠️ **Recomendaciones adicionales:**
- Usa SSH keys en lugar de contraseñas
- Configura firewall en servidor
- Mantén el sistema actualizado
- Considera backups automáticos de datos

## 💰 Costos Estimados (Digital Ocean)

- **Droplet básico**: $6/mes (1GB RAM) - Suficiente para empezar
- **Droplet recomendado**: $12/mes (2GB RAM) - Para mejor rendimiento
- **Storage**: Incluido (25GB SSD)
- **Transferencia**: 1TB/mes incluida

## 🎓 Próximos Pasos Recomendados

1. ✅ **Probar localmente** con Docker Desktop
2. ✅ **Crear Droplet** en Digital Ocean
3. ✅ **Desplegar** el bot
4. 📊 **Monitorear** los logs la primera semana
5. 🔧 **Ajustar** horarios/configuración según necesidades
6. 💾 **Configurar backups** de datos (opcional)
7. 📱 **Configurar notificaciones** de Telegram (opcional)

## 📞 Soporte

Si tienes problemas:

1. **Revisa logs**: `docker-compose logs`
2. **Verifica configuración**: `docker-compose ps`
3. **Consulta documentación**: `README_DOCKER.md` y `TAREAS_PROGRAMADAS.md`
4. **Ejecuta manualmente**: `docker-compose exec telegram-bot /app/run_weekly_task.sh`

## 📝 Notas Importantes

- ⚠️ **El archivo `.env` nunca se debe subir a Git** (ya está en `.gitignore`)
- 📅 **La primera ejecución automática** será el próximo lunes a las 3:00 AM
- 🔄 **El bot se reiniciará automáticamente** después de la generación
- 📊 **Revisa los logs semanalmente** para asegurar que todo funciona
- 💾 **Los datos persisten** aunque el contenedor se reinicie

## ✨ Mejoras Futuras Posibles

- [ ] Notificaciones por Telegram cuando completa la generación
- [ ] Dashboard web para monitoreo
- [ ] Backups automáticos a S3 o similar
- [ ] Métricas con Prometheus/Grafana
- [ ] Alertas por email en caso de errores
- [ ] CI/CD automático con GitHub Actions
