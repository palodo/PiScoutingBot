# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for PDF generation, image processing, and cron
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    cron \
    tzdata \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Create necessary directories if they don't exist
RUN mkdir -p data logs reportes debug_html imagenes player_photos_cache scouting_output

# Copy and set permissions for entrypoint and task scripts
COPY docker-entrypoint.sh /usr/local/bin/
COPY run_weekly_task.sh /app/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh /app/run_weekly_task.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Madrid

# Run the entrypoint script
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
