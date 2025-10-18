# Comando Shortchart Scraper - Bot PiScouting

## 📋 Descripción

Se ha implementado un nuevo comando administrativo para ejecutar el scraper de shotcharts directamente desde Telegram.

## 🎯 Comando

```
/run_shortchart_scraper
```

## 🔑 Requisitos

- **Permisos de administrador**: Solo usuarios con `admin: true` en `user_limits.json` pueden ejecutar este comando
- El bot debe tener acceso al archivo `scrapping_folder/shortchart_scraper.py`

## 🔄 Flujo de Funcionamiento

### 1. Ejecución del comando

El administrador escribe `/run_shortchart_scraper` en el chat del bot.

### 2. Confirmación inicial

El bot responde con:

```
🎯 Scraper de Shotcharts

👑 Solicitado por: [Nombre del Admin]
🕒 Iniciando proceso...

⚠️ IMPORTANTE:
• Este proceso puede tardar varios minutos
• Actualiza datos de shotcharts de jugadores
• No interrumpir durante la ejecución

📊 Te mantendré informado del progreso...
```

### 3. Inicio del scraper

```
🚀 Scraper de Shotcharts iniciado

📁 Directorio: [ruta del bot]
📅 Hora inicio: HH:MM:SS

⏳ Ejecutando comando...
```

### 4. Actualizaciones de progreso

Cada 2 minutos, el bot envía un mensaje de estado:

```
⏳ Scraper en progreso...

🕒 Tiempo transcurrido: Xm Ys
🔄 El proceso sigue ejecutándose...

💡 No interrumpir, el scraper está funcionando
```

### 5. Finalización exitosa

```
✅ Scraper de Shotcharts completado exitosamente

⏱️ Tiempo total: Xm Ys
📁 Archivos generados en: scrapping_folder/shotcharts/
📅 Hora finalización: HH:MM:SS

🎯 Los datos de shotcharts están actualizados
```

### 6. En caso de error

```
❌ Scraper de Shotcharts falló

⏱️ Tiempo transcurrido: Xm Ys
🔴 Código de salida: [código]

Error:
[mensaje de error]
```

## 📊 Logs de Administración

Si `SEND_ADMIN_LOGS` está activado, se envía un log al grupo de administradores:

### Log de éxito:
```
🎯 Scraper de Shotcharts ejecutado exitosamente

👑 Administrador: [Nombre]
• User ID: [ID]
• Tiempo: Xm Ys
• Resultado: ✅ Éxito
• Timestamp: HH:MM:SS - DD/MM/YYYY
```

### Log de error:
```
❌ Scraper de Shotcharts falló

👑 Administrador: [Nombre]
• User ID: [ID]
• Tiempo: Xm Ys
• Código salida: [código]
• Error: [mensaje]...
• Timestamp: HH:MM:SS - DD/MM/YYYY
```

## 🛠️ Implementación Técnica

### Función principal
```python
async def admin_run_shortchart_scraper(update: Update, context: ContextTypes.DEFAULT_TYPE)
```

### Función de ejecución en background
```python
async def run_shortchart_scraper_background(
    chat_id: int,
    admin_user_id: int,
    admin_name: str,
    context: ContextTypes.DEFAULT_TYPE
)
```

### Características técnicas:
- **Ejecución asíncrona**: No bloquea el bot mientras se ejecuta
- **Subprocess**: Ejecuta el script Python en un proceso separado
- **Actualizaciones periódicas**: Envía mensajes cada 2 minutos
- **Captura de output**: Registra stdout y stderr del proceso
- **Manejo de errores**: Captura y reporta cualquier error

## 📝 Comparación con `/run_scraper`

| Característica | `/run_scraper` | `/run_shortchart_scraper` |
|----------------|----------------|---------------------------|
| Script ejecutado | `multi_season_scraper.py` | `shortchart_scraper.py` |
| Función | Datos FEB 2024/2025 | Shotcharts de jugadores |
| Tiempo estimado | 15-45 minutos | Varios minutos |
| Recarga automática | Sí (recarga bot) | No (solo shotcharts) |
| Logs a admins | Sí | Sí |

## ⚙️ Configuración

El comando se registra en la función `main()`:

```python
app.add_handler(CommandHandler("run_shortchart_scraper", admin_run_shortchart_scraper))
```

## 💡 Notas Importantes

1. **No interrumpir**: El proceso debe completarse sin interrupciones
2. **Ejecución única**: No ejecutar múltiples instancias simultáneamente
3. **Tiempo variable**: Depende del número de jugadores a procesar
4. **Archivos generados**: Se guardan en `scrapping_folder/shotcharts/`
5. **Verificación de permisos**: Solo admins pueden ejecutar el comando

## 🔒 Seguridad

- Verificación de permisos de administrador antes de ejecutar
- Solo usuarios con flag `admin: true` pueden usar el comando
- Logs completos de quién ejecutó el comando y cuándo
- Aislamiento del proceso mediante subprocess

## 🎯 Uso Recomendado

1. Ejecutar cuando sea necesario actualizar datos de shotcharts
2. Preferiblemente en momentos de poco uso del bot
3. Monitorear los mensajes de progreso
4. Verificar la finalización exitosa antes de generar PDFs

## 📚 Ayuda en el Bot

El comando aparece en `/help` para administradores en la sección:

```
🔄 Gestión de Datos:
• /run_scraper - Ejecutar scraper multi-temporada
  Actualiza datos de FEB 2024 y 2025
• /run_shortchart_scraper - Ejecutar scraper de shotcharts
  Actualiza datos de shotcharts de jugadores
```
