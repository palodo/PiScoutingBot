FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    cron \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de requisitos
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el proyecto
COPY . .

# Crear directorios necesarios
RUN mkdir -p logs data reportes imagenes

# Dar permisos al script de actualización
RUN chmod +x /app/update_weekly.sh

# Copiar el archivo cron
COPY crontab /etc/cron.d/scouting-cron

# Dar permisos al archivo cron
RUN chmod 0644 /etc/cron.d/scouting-cron

# Crear archivo de log para cron
RUN touch /var/log/cron.log

# Crear el script de entrada
RUN echo '#!/bin/bash\n\
set -e\n\
echo "Iniciando servicio de cron..."\n\
cron\n\
echo "Iniciando bot de Telegram..."\n\
python TELEGRAM_BOT.py\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Comando de inicio
CMD ["/app/entrypoint.sh"]
