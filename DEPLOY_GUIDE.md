# Guía de Despliegue en Servidor Remoto

## Opción 1: Transferir imagen Docker (Recomendado)

### En tu máquina local (Windows):

```powershell
# 1. Exportar imagen y datos
.\export_docker.ps1

# 2. Transferir archivos a servidor (elige uno):
# Via SCP:
scp pi-scouting-bot-image.tar.gz usuario@servidor:/home/usuario/
scp pi-scouting-bot-data.tar.gz usuario@servidor:/home/usuario/
scp docker-compose.yml usuario@servidor:/home/usuario/
scp .env usuario@servidor:/home/usuario/
scp deploy_remote.sh usuario@servidor:/home/usuario/
```

### En el servidor remoto (Linux):

```bash
# 1. Dar permisos
chmod +x deploy_remote.sh

# 2. Desplegar
./deploy_remote.sh
```

---

## Opción 2: Build directo en servidor

### Transferir código fuente:

```powershell
# Desde Windows
scp -r * usuario@servidor:/home/usuario/pi-scouting-bot/
```

### En el servidor:

```bash
cd /home/usuario/pi-scouting-bot

# Verificar .env con tokens correctos
nano .env

# Build y ejecutar
docker-compose up --build -d
```

---

## Opción 3: Registry privado

### En tu máquina:

```powershell
# Tag imagen
docker tag deploy-scouting-bot:latest turegistry.com/pi-scouting-bot:latest

# Push a registry
docker push turegistry.com/pi-scouting-bot:latest
```

### En servidor:

```bash
# Pull desde registry
docker pull turegistry.com/pi-scouting-bot:latest

# Actualizar docker-compose.yml con la imagen del registry
docker-compose up -d
```

---

## Comandos útiles en servidor

```bash
# Ver logs en tiempo real
docker logs -f pi-scouting-bot

# Ver estado
docker ps

# Reiniciar
docker-compose restart

# Detener
docker-compose down

# Ver logs de cron
docker exec pi-scouting-bot cat /app/logs/cron.log

# Ejecutar actualización manual
docker exec pi-scouting-bot /bin/bash /app/update_weekly.sh

# Entrar al contenedor
docker exec -it pi-scouting-bot /bin/bash
```

---

## Requisitos del servidor

- Docker y Docker Compose instalados
- Puertos: ninguno expuesto (el bot usa polling)
- Espacio: ~2GB para imagen + datos
- RAM: ~512MB mínimo

---

## Instalación de Docker en servidor Linux

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Instalar Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin
```
