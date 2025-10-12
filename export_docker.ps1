# Exportar imagen Docker
docker save deploy-scouting-bot:latest -o pi-scouting-bot-image.tar

# Comprimir imagen
gzip pi-scouting-bot-image.tar

# Crear backup de datos usando tar (mejor compatibilidad Linux)
tar -czf pi-scouting-bot-data.tar.gz data/ imagenes/

Write-Host ""
Write-Host "Archivos generados:" -ForegroundColor Green
Write-Host "  - pi-scouting-bot-image.tar.gz (imagen Docker)"
Write-Host "  - pi-scouting-bot-data.tar.gz (datos)"
Write-Host ""
Write-Host "Transfiere estos archivos a la maquina destino junto con:"
Write-Host "  - docker-compose.yml"
Write-Host "  - .env"
Write-Host "  - deploy_remote.sh"
