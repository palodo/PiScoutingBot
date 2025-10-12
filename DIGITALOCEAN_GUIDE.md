# Guía de Despliegue en DigitalOcean

## Paso 1: Crear Droplet en DigitalOcean

1. Accede a https://cloud.digitalocean.com/
2. Click en "Create" → "Droplets"
3. Selecciona:
   - **Imagen**: Ubuntu 22.04 LTS
   - **Plan**: Basic ($6/mes - 1GB RAM, 25GB SSD)
   - **Datacenter**: Closest to your location (e.g., Frankfurt)
   - **Authentication**: SSH Key (recomendado) o Password
   - **Hostname**: pi-scouting-bot
4. Click "Create Droplet"
5. Espera 1-2 minutos a que se cree
6. Anota la IP del droplet

## Paso 2: Configurar Droplet

### Desde PowerShell en Windows:

```powershell
# Conectar al droplet
ssh root@TU_IP_DROPLET

# Copiar y pegar el script de instalación
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo apt-get install -y docker-compose-plugin
mkdir -p ~/pi-scouting-bot
cd ~/pi-scouting-bot
mkdir -p logs data reportes imagenes
```

## Paso 3: Subir Archivos al Droplet

### Desde PowerShell en Windows:

```powershell
# Reemplaza TU_IP_DROPLET con la IP real
$IP = "TU_IP_DROPLET"

# Subir archivos
scp pi-scouting-bot-image.tar.zip root@${IP}:~/pi-scouting-bot/
scp pi-scouting-bot-data.zip root@${IP}:~/pi-scouting-bot/
scp docker-compose.yml root@${IP}:~/pi-scouting-bot/
scp .env root@${IP}:~/pi-scouting-bot/
scp start_bot.sh root@${IP}:~/pi-scouting-bot/
```

## Paso 4: Iniciar Bot en el Droplet

### En el droplet (via SSH):

```bash
cd ~/pi-scouting-bot
chmod +x start_bot.sh
./start_bot.sh
```

## Paso 5: Verificar que Funciona

```bash
# Ver logs en tiempo real
docker logs -f pi-scouting-bot

# Verificar estado
docker ps

# Verificar cron
docker exec pi-scouting-bot ps aux | grep cron
```

## Comandos Útiles

```bash
# Ver logs
docker logs -f pi-scouting-bot

# Reiniciar bot
docker-compose restart

# Detener bot
docker-compose down

# Actualizar datos manualmente
docker exec pi-scouting-bot /bin/bash /app/update_weekly.sh

# Entrar al contenedor
docker exec -it pi-scouting-bot /bin/bash

# Ver logs de actualizaciones semanales
docker exec pi-scouting-bot cat /app/logs/update.log
```

## Configuración Firewall (Opcional)

El bot usa polling, no necesita puertos abiertos, pero por seguridad:

```bash
# Configurar UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable
```

## Costos Estimados

- **Droplet Basic**: $6/mes (1GB RAM, 25GB SSD)
- **Snapshots** (backups opcionales): $1.20/mes por 20GB
- **Total**: ~$6-7/mes

## Backup y Recuperación

### Crear backup:

```bash
# En el droplet
cd ~/pi-scouting-bot
docker-compose down
tar -czf backup-$(date +%Y%m%d).tar.gz data/ imagenes/ logs/ .env
docker-compose up -d
```

### Descargar backup:

```powershell
# Desde Windows
scp root@TU_IP_DROPLET:~/pi-scouting-bot/backup-*.tar.gz .
```

## Actualizar el Bot

### Cuando hagas cambios en el código:

```powershell
# Desde Windows: rebuild y exportar
docker-compose down
docker-compose up --build -d
docker save deploy-scouting-bot:latest -o pi-scouting-bot-image.tar
Compress-Archive -Path pi-scouting-bot-image.tar -DestinationPath pi-scouting-bot-image.tar.zip -Force

# Subir nueva imagen
scp pi-scouting-bot-image.tar.zip root@TU_IP_DROPLET:~/pi-scouting-bot/

# En el droplet
cd ~/pi-scouting-bot
docker-compose down
unzip -o pi-scouting-bot-image.tar.zip
docker load -i pi-scouting-bot-image.tar
docker-compose up -d
```

## Monitoreo

### Ver uso de recursos:

```bash
docker stats pi-scouting-bot
```

### Ver espacio en disco:

```bash
df -h
```

## Troubleshooting

### Bot no responde:

```bash
docker logs pi-scouting-bot
# Revisar errores
docker restart pi-scouting-bot
```

### Sin espacio en disco:

```bash
# Limpiar imágenes Docker antiguas
docker system prune -a

# Limpiar logs antiguos
docker exec pi-scouting-bot truncate -s 0 /app/logs/*.log
```

### Cron no ejecuta:

```bash
# Verificar cron
docker exec pi-scouting-bot cat /etc/cron.d/scouting-cron
docker exec pi-scouting-bot ps aux | grep cron
```
