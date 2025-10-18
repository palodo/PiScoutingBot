# Comando Delete User - Bot PiScouting

## 📋 Descripción

Se ha implementado un comando administrativo para **eliminar completamente** un usuario del registro del sistema, diferente del comando de desautorización.

## 🗑️ Comando

```bash
/delete_user <user_id>
```

## 🔑 Requisitos

- **Permisos de administrador**: Solo usuarios con `admin: true` en `user_limits.json` pueden ejecutar este comando
- El usuario debe existir en el registro

## 🔄 Diferencias entre comandos

### `/authorize_user <id> false` (Desautorizar)
- ❌ Desactiva el acceso del usuario
- ✅ **Mantiene el registro** con toda su información
- 📊 Preserva historial de generaciones
- 🔄 Se puede reautorizar fácilmente

### `/delete_user <id>` (Eliminar)
- 🗑️ **Elimina completamente** el registro del usuario
- ❌ Borra toda la información asociada
- ⚠️ **Acción irreversible**
- 🆕 Si vuelve a usar el bot, se crea como usuario nuevo

## 📖 Uso del Comando

### Sintaxis básica:
```bash
/delete_user 123456789
```

### Ejemplo de error (usuario no encontrado):
```bash
/delete_user 999999999
```
Respuesta:
```
❌ Usuario no encontrado

El usuario con ID 999999999 no existe en el registro.
```

## ✅ Respuesta del comando

Cuando se elimina exitosamente un usuario:

```
🗑️ Usuario eliminado del registro

Datos eliminados:
• User ID: 123456789
• Nombre: Juan Pérez
• Estado: ✅ Autorizado
• Rol: 👤 Usuario
• Generaciones restantes: 35

✅ El usuario ha sido completamente eliminado del sistema.
```

## 📊 Log de Administración

Si `SEND_ADMIN_LOGS` está activado, se envía un log detallado al grupo de administradores:

```
🗑️ Usuario eliminado del registro

👑 Administrador: Admin Name
• Admin ID: 987654321

🚫 Usuario eliminado:
• User ID: 123456789
• Nombre: Juan Pérez
• Autorizado: Sí
• Admin: No
• Timestamp: 14:30:45 - 18/10/2025
```

## ⚠️ Consideraciones Importantes

### Cuándo usar `/delete_user`:
- Usuario ya no necesitará acceso nunca más
- Usuario fue creado por error o prueba
- Limpieza de base de datos
- Usuario duplicado

### Cuándo usar `/authorize_user <id> false`:
- Usuario temporal que puede volver
- Suspensión temporal de acceso
- Preservar historial de uso
- Posible reactivación futura

## 🔒 Seguridad

1. **Verificación de permisos**: Solo administradores pueden ejecutar el comando
2. **Confirmación visual**: Muestra todos los datos antes de eliminar
3. **Log completo**: Registra quién eliminó qué y cuándo
4. **Irreversible**: No se puede deshacer (diseñado así intencionalmente)

## 💻 Implementación Técnica

### Función principal:
```python
async def admin_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE)
```

### Proceso:
1. Verificar que el ejecutor es administrador
2. Validar que el user_id sea un número
3. Verificar que el usuario existe en el registro
4. Capturar información del usuario antes de eliminar
5. Eliminar el registro del diccionario
6. Guardar configuración actualizada
7. Enviar confirmación al admin
8. Enviar log al grupo de administradores

### Registro del comando:
```python
app.add_handler(CommandHandler("delete_user", admin_delete_user))
```

## 📚 Ayuda en el Bot

El comando aparece en `/help` para administradores:

```
👥 Gestión de Usuarios:
• /list_users - Ver todos los usuarios
• /authorize_user <id> <true/false> [admin] [max] [name]
  Autorizar/desautorizar (mantiene registro)
  Ejemplo: /authorize_user 123 true admin 100 Juan
• /delete_user <id> - Eliminar usuario completamente
  ⚠️ Elimina todo el registro del usuario
```

## 🎯 Casos de Uso

### Caso 1: Usuario de prueba
```bash
# Eliminar usuario creado para pruebas
/delete_user 111111111
```

### Caso 2: Usuario duplicado
```bash
# Si un usuario se registró dos veces por error
/delete_user 222222222
```

### Caso 3: Limpieza de usuarios inactivos
```bash
# Usuarios que nunca más volverán a usar el bot
/delete_user 333333333
```

## 🔧 Recuperación

Si eliminas un usuario por error:

1. **No hay función de deshacer**
2. El usuario tendrá que:
   - Volver a escribir `/start`
   - Solicitar acceso nuevamente
   - Los admins aprobarán con las generaciones deseadas
3. Todo el historial previo se habrá perdido

## 📝 Comparación Rápida

| Acción | `/authorize_user false` | `/delete_user` |
|--------|------------------------|----------------|
| Acceso al bot | ❌ Bloqueado | ❌ Bloqueado |
| Mantiene registro | ✅ Sí | ❌ No |
| Historial | ✅ Preservado | 🗑️ Eliminado |
| Reversible | ✅ Fácilmente | ❌ No |
| Uso recomendado | Suspensión temporal | Eliminación definitiva |

## 💡 Buenas Prácticas

1. **Antes de eliminar**, considera si desautorizar es suficiente
2. **Verifica el user_id** dos veces antes de confirmar
3. **Documenta** por qué eliminaste al usuario (en tus notas)
4. **Usa `/list_users`** para verificar antes de eliminar
5. **Prefiere desautorizar** a menos que estés seguro de eliminar

## 🚨 Advertencias

- ⚠️ **Acción permanente**: No se puede deshacer
- ⚠️ **Sin confirmación adicional**: Se ejecuta inmediatamente
- ⚠️ **Pérdida de datos**: Todo el historial se pierde
- ⚠️ **Usuario puede volver**: Pero como usuario nuevo

## 🎓 Ejemplo Completo

```bash
# 1. Ver lista de usuarios
/list_users

# 2. Identificar usuario a eliminar
# Usuario ID: 123456789 - Juan Pérez - 2/50 PDFs

# 3. Eliminar usuario
/delete_user 123456789

# 4. Confirmar eliminación (recibirás el mensaje de confirmación)

# 5. Verificar que ya no está
/list_users
# El usuario ya no aparece en la lista
```
