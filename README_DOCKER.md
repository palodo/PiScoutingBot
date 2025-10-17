# PI Scouting Bot - Guía de Despliegue en Digital Ocean

## ⭐ Características

- 🤖 **Bot de Telegram 24/7** - Siempre disponible para tus usuarios
- 📄 **Generación automática de PDFs** - Cada lunes a las 3 AM genera PDFs de todos los jugadores
- 🔄 **Reinicio automático** - El bot se reinicia después de la generación semanal para optimizar memoria
- 🐳 **Dockerizado** - Fácil de desplegar y mantener
- 📊 **Logs detallados** - Monitorea todas las operaciones
- 🌍 **Zona horaria configurable** - Ajusta según tu ubicación

## 📋 Requisitos Previos

1. **Cuenta de Digital Ocean**: Crea una cuenta en [DigitalOcean.com](https://www.digitalocean.com/)
2. **Token del Bot de Telegram**: Obtén tu token de [@BotFather](https://t.me/BotFather) en Telegram
3. **Repositorio Git**: Tu código debe estar en un repositorio Git (GitHub, GitLab, etc.)

## 🚀 Pasos para Desplegar en Digital Ocean

### Paso 1: Crear un Droplet

1. Inicia sesión en Digital Ocean
2. Click en **"Create"** → **"Droplets"**
3. Selecciona las siguientes opciones:
   - **Imagen**: Ubuntu 22.04 LTS
   - **Plan**: Basic ($6/mes - 1GB RAM, 1 vCPU) es suficiente para empezar
   - **Región**: Elige la más cercana a tus usuarios (ej: Frankfurt para Europa)
   - **Autenticación**: SSH Key (recomendado) o contraseña
   - **Hostname**: `pi-scouting-bot` (o el nombre que prefieras)
4. Click en **"Create Droplet"**

### Paso 2: Conectar al Servidor

Desde tu terminal local (PowerShell, CMD, o WSL):

```bash
ssh root@TU_IP_DEL_DROPLET
```

### Paso 3: Configuración Inicial del Servidor

Ejecuta estos comandos en el servidor:

```bash
# Descargar script de configuración inicial
curl -o setup_server.sh https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/feature/dev_ivan/setup_server.sh

# Dar permisos de ejecución
chmod +x setup_server.sh

# Ejecutar configuración inicial
sudo ./setup_server.sh
```

**Alternativa manual**: Si prefieres hacerlo manualmente, copia el contenido de `setup_server.sh` y ejecútalo paso a paso.

### Paso 4: Configurar el Token de Telegram

```bash
# Editar archivo .env
nano /opt/pi-scouting-bot/.env
```

Reemplaza `your_telegram_bot_token_here` con tu token real:
```
TELEGRAM_TOKEN=8275548769:AAEM7BiUHVpfeQb9B6zh6QS5piHtg_dR53I
```

Guarda con `Ctrl+X`, luego `Y`, luego `Enter`.

### Paso 5: Desplegar el Bot

```bash
cd /opt/pi-scouting-bot
./deploy.sh
```

¡Listo! Tu bot debería estar corriendo ahora.

## 📝 Comandos Útiles

### Ver logs del bot en tiempo real
```bash
cd /opt/pi-scouting-bot
docker-compose logs -f
```

### Detener el bot
```bash
cd /opt/pi-scouting-bot
docker-compose down
```

### Reiniciar el bot
```bash
cd /opt/pi-scouting-bot
docker-compose restart
```

### Ver estado del bot
```bash
cd /opt/pi-scouting-bot
docker-compose ps
```

### Actualizar el bot con nuevos cambios
```bash
cd /opt/pi-scouting-bot
./deploy.sh
```

### Ver uso de recursos
```bash
docker stats
```

### Ver logs de la generación semanal de PDFs
```bash
cd /opt/pi-scouting-bot
cat logs/weekly_pdf_generation_*.log
```

### Ejecutar generación de PDFs manualmente (sin esperar al lunes)
```bash
cd /opt/pi-scouting-bot
docker-compose exec telegram-bot /app/run_weekly_task.sh
```

## ⏰ Tareas Programadas

El bot está configurado para ejecutar automáticamente la **generación masiva de PDFs cada lunes a las 3:00 AM** (hora de Madrid). Después de completar la generación, el bot se reinicia automáticamente.

### Configuración
- **Frecuencia**: Cada lunes
- **Hora**: 3:00 AM (zona horaria: Europe/Madrid)
- **Acción**: Genera PDFs de todos los jugadores y reinicia el bot

### Cambiar horario o frecuencia
Consulta el archivo `TAREAS_PROGRAMADAS.md` para instrucciones detalladas sobre cómo modificar el horario, cambiar la zona horaria, o configurar diferentes frecuencias.

## 🔄 Actualizaciones Futuras

Cuando hagas cambios en tu código:

1. **Commit y push** tus cambios a GitHub
2. Conéctate a tu servidor
3. Ejecuta el script de despliegue:
```bash
cd /opt/pi-scouting-bot
./deploy.sh
```

El script automáticamente:
- Descargará los últimos cambios
- Reconstruirá la imagen Docker
- Reiniciará el bot

## 🛠️ Desarrollo Local con Docker

Si quieres probar el Docker localmente antes de subir a Digital Ocean:

### En Windows (PowerShell):

```powershell
# 1. Asegúrate de tener Docker Desktop instalado
# Descárgalo de: https://www.docker.com/products/docker-desktop/

# 2. Crea archivo .env con tu token
Copy-Item .env.example .env
# Edita .env y añade tu token

# 3. Construir y ejecutar
docker-compose up --build

# Para detener: Ctrl+C y luego
docker-compose down
```

### En Linux/Mac:

```bash
# 1. Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# 2. Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 3. Configurar y ejecutar
cp .env.example .env
# Edita .env con tu token
docker-compose up --build
```

## 🔐 Seguridad

### Recomendaciones:

1. **Nunca subas tu archivo `.env` a Git** - Ya está en `.gitignore`
2. **Usa SSH Keys** en lugar de contraseñas para el servidor
3. **Mantén el sistema actualizado**:
   ```bash
   apt-get update && apt-get upgrade -y
   ```
4. **Considera configurar un firewall**:
   ```bash
   ufw allow ssh
   ufw enable
   ```

## 📊 Monitoreo

### Ver logs históricos
```bash
cd /opt/pi-scouting-bot
docker-compose logs --tail=100
```

### Ver solo errores
```bash
docker-compose logs | grep -i error
```

### Verificar espacio en disco
```bash
df -h
```

### Limpiar imágenes Docker antiguas
```bash
docker system prune -a
```

## 🆘 Solución de Problemas

### El bot no se inicia
```bash
# Ver logs detallados
docker-compose logs

# Verificar que el contenedor está corriendo
docker-compose ps

# Reiniciar desde cero
docker-compose down
docker-compose up --build
```

### Error de memoria
Si el bot se queda sin memoria, edita `docker-compose.yml` y aumenta `mem_limit`:
```yaml
mem_limit: 2g  # Aumentar a 2GB
```

### Verificar conectividad con Telegram
```bash
# Desde el servidor
curl https://api.telegram.org/bot<TU_TOKEN>/getMe
```

## 💰 Costos Estimados

- **Droplet básico**: $6/mes (1GB RAM, 1 vCPU)
- **Droplet recomendado**: $12/mes (2GB RAM, 1 vCPU) - Para mejor rendimiento
- **Storage adicional**: Incluido (25GB SSD)
- **Transferencia**: 1TB/mes incluida

## 📱 Configurar Inicio Automático

El bot se iniciará automáticamente cuando el servidor se reinicie gracias a la configuración `restart: unless-stopped` en `docker-compose.yml`.

Para verificar:
```bash
# Reiniciar servidor
reboot

# Después del reinicio, verificar que el bot está corriendo
docker-compose ps
```

## 🔗 Enlaces Útiles

- [Documentación Digital Ocean](https://docs.digitalocean.com/)
- [Documentación Docker](https://docs.docker.com/)
- [python-telegram-bot Docs](https://docs.python-telegram-bot.org/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)

## 📞 Soporte

Si encuentras problemas:
1. Revisa los logs: `docker-compose logs`
2. Verifica que el token es correcto
3. Asegúrate de que el servidor tiene suficiente memoria
4. Revisa la conectividad de red del servidor
