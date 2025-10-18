# Sistema de Solicitud de Acceso - Bot PiScouting

## 📋 Descripción

Se ha implementado un sistema automático de solicitud de acceso para usuarios no autorizados del bot de Telegram.

## 🔄 Flujo de Funcionamiento

### 1. Usuario sin acceso intenta usar el bot

Cuando un usuario no autorizado escribe `/start`, en lugar de recibir un mensaje de error directo:

```
❌ Acceso denegado. No tienes permisos para usar este bot.

Para solicitar acceso, por favor indica el nombre de tu equipo:
Ejemplo: CB Estudiantes, Real Madrid, etc.
```

### 2. Usuario indica el nombre de su equipo

El usuario simplemente escribe el nombre de su equipo en el chat. Por ejemplo:
- "CB Estudiantes"
- "Real Madrid Baloncesto"
- "Valencia Basket"

### 3. Confirmación al usuario

El usuario recibe una confirmación inmediata:

```
✅ Solicitud enviada

Equipo: CB Estudiantes

Los administradores revisarán tu solicitud pronto. 
Te notificaremos cuando tengas acceso al bot.
```

### 4. Notificación a los administradores

Los administradores reciben un mensaje en el grupo de administración con:

```
🔔 NUEVA SOLICITUD DE ACCESO

👤 Usuario:
• Nombre: Pablo García
• Username: @pablo_garcia
• User ID: 123456789

🏀 Equipo solicitado:
• CB Estudiantes

¿Aprobar acceso?
Selecciona cuántas generaciones asignar:

[✅ 10 PDFs] [✅ 25 PDFs]
[✅ 50 PDFs] [✅ 100 PDFs]
[❌ Rechazar]
```

### 5. Decisión de los administradores

Los administradores solo necesitan presionar un botón:

#### Si APRUEBAN:
- El usuario recibe automáticamente:
  ```
  🎉 ¡Acceso aprobado!
  
  Ya puedes usar el bot PiScouting.
  Tienes 50 generaciones de PDFs disponibles.
  
  Escribe /start para comenzar.
  ```
- El usuario queda autorizado con el número de generaciones seleccionado
- Se actualiza automáticamente el archivo `user_limits.json`

#### Si RECHAZAN:
- El usuario recibe:
  ```
  ❌ Solicitud de acceso rechazada
  
  Tu solicitud de acceso al bot ha sido rechazada.
  Si crees que esto es un error, contacta con los administradores.
  ```

## 🛠️ Cambios Técnicos Implementados

### 1. Nuevo estado de conversación
```python
SOLICITAR_ACCESO_EQUIPO = 4
```

### 2. Modificación en la función `start()`
- Ya no termina inmediatamente para usuarios no autorizados
- Redirige al estado `SOLICITAR_ACCESO_EQUIPO`

### 3. Nueva función `handle_access_request()`
- Captura el nombre del equipo
- Envía notificación a los admins con botones interactivos
- Confirma al usuario que la solicitud fue enviada

### 4. Nueva función `handle_access_approval()`
- Procesa las respuestas de los admins (aprobar/rechazar)
- Actualiza permisos automáticamente
- Notifica al usuario del resultado
- Verifica que solo admins puedan aprobar solicitudes

### 5. Integración en el ConversationHandler
```python
states={
    SOLICITAR_ACCESO_EQUIPO: [
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_access_request)
    ],
    # ... otros estados
}
```

### 6. Callback Handler para botones de admin
```python
app.add_handler(CallbackQueryHandler(
    handle_access_approval, 
    pattern=r"^(approve_access|reject_access)::"
))
```

## 📊 Opciones de Generaciones Disponibles

Los administradores pueden aprobar con las siguientes cantidades predeterminadas:
- **10 PDFs** - Para uso limitado o prueba
- **25 PDFs** - Para usuarios ocasionales
- **50 PDFs** - Opción estándar
- **100 PDFs** - Para usuarios frecuentes

## ✨ Ventajas del Sistema

1. **Automatización completa**: No requiere comandos complejos
2. **Interfaz simple**: El usuario solo escribe el nombre de su equipo
3. **Decisión rápida**: Los admins solo presionan un botón
4. **Trazabilidad**: Se registra toda la información del solicitante
5. **Notificaciones automáticas**: El usuario es informado del resultado
6. **Seguridad**: Solo admins autorizados pueden aprobar solicitudes

## 🔒 Seguridad

- Solo usuarios con el flag `admin: true` en `user_limits.json` pueden aprobar solicitudes
- Los botones verifican permisos antes de ejecutar acciones
- Toda la información se registra en el grupo de administradores

## 📝 Notas Adicionales

- El ID del chat de admins se configura en `ADMIN_LOG_CHAT_ID`
- Las solicitudes no afectan al rendimiento del bot
- Los usuarios pueden reintentar escribiendo `/start` nuevamente
- No hay límite en el número de solicitudes que un usuario puede hacer
