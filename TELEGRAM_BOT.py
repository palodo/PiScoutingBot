import os
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Configurar matplotlib para modo headless ANTES de cualquier importación
import matplotlib
matplotlib.use('Agg')  # Backend sin interfaz gráfica

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# Import de la función generar_pdf
from pdf_generator.final_pdf import generar_pdf_final

# ==========================
# CONFIGURACIÓN
# ==========================
BASE_DIR = Path(__file__).parent.resolve()
DATA_PATH = BASE_DIR / "data" / "datos_historicos.json"  # Archivo multi-temporada
USER_LIMITS_PATH = BASE_DIR / "data" / "user_limits.json"  # Archivo para guardar contadores
TEMPORADA_ACTUAL = "2025"  # Temporada a usar

# Lee el token desde variable de entorno (recomendado)
TELEGRAM_TOKEN = "8275548769:AAEM7BiUHVpfeQb9B6zh6QS5piHtg_dR53I"
#387041904:AAFhVMH9jeplmN289-4hRDOec5T65xmQQPI
#

# ==========================
# SISTEMA DE COLA PARA PETICIONES (CON LOCK)
# ==========================
processing_lock = asyncio.Lock()  # Lock para procesar PDFs uno a la vez
processing_queue: List[Dict[str, Any]] = []  # Cola de peticiones pendientes

def get_queue_position(user_id: int) -> int:
    """Retorna la posición en la cola (1-indexed). 0 si no está en la cola."""
    for idx, item in enumerate(processing_queue):
        if item.get("user_id") == user_id:
            return idx + 1
    return 0

def add_to_queue(user_id: int, data: Dict[str, Any]) -> int:
    """Añade una petición a la cola y retorna su posición."""
    # Verificar si el usuario ya está en la cola
    existing_pos = get_queue_position(user_id)
    if existing_pos > 0:
        return existing_pos
    
    # Añadir nueva petición
    queue_item = {
        "user_id": user_id,
        "data": data,
        "timestamp": asyncio.get_event_loop().time()
    }
    processing_queue.append(queue_item)
    return len(processing_queue)

def remove_from_queue(user_id: int) -> None:
    """Elimina un usuario de la cola."""
    global processing_queue
    processing_queue = [item for item in processing_queue if item.get("user_id") != user_id]

def get_queue_length() -> int:
    """Retorna el número de peticiones en la cola."""
    return len(processing_queue)

# ==========================
# SISTEMA DE LÍMITES POR USUARIO (DESDE JSON)
# ==========================

def load_user_config() -> Dict[str, Any]:
    """Carga la configuración completa de usuarios desde el archivo JSON"""
    if USER_LIMITS_PATH.exists():
        try:
            with USER_LIMITS_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error cargando configuración de usuarios: {e}")
            return create_default_config()
    return create_default_config()

def create_default_config() -> Dict[str, Any]:
    """Crea una configuración por defecto"""
    return {
        "config": {
            "default_max_generations": 50
        },
        "users": {}
    }

def save_user_config(config: Dict[str, Any]) -> None:
    """Guarda la configuración completa de usuarios en el archivo JSON"""
    try:
        # Crear directorio si no existe
        USER_LIMITS_PATH.parent.mkdir(exist_ok=True)
        with USER_LIMITS_PATH.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando configuración de usuarios: {e}")

def get_user_data(user_id: int) -> Dict[str, Any]:
    """Obtiene los datos de un usuario específico"""
    config = load_user_config()
    user_key = str(user_id)
    
    if user_key not in config["users"]:
        # Usuario nuevo - crear entrada por defecto
        default_max = config["config"]["default_max_generations"]
        config["users"][user_key] = {
            "authorized": False,  # Por defecto no autorizado
            "admin": False,
            "max_generations": default_max,
            "remaining_generations": default_max,
            "name": f"User {user_id}"
        }
        save_user_config(config)
    
    return config["users"][user_key]

def get_default_max_generations() -> int:
    """Obtiene el número máximo por defecto de generaciones"""
    config = load_user_config()
    return config["config"].get("default_max_generations", 50)

def is_user_authorized(user_id: int) -> bool:
    """Verifica si el usuario está autorizado para usar el bot"""
    user_data = get_user_data(user_id)
    return user_data.get("authorized", False)

def is_user_admin(user_id: int) -> bool:
    """Verifica si el usuario es administrador"""
    user_data = get_user_data(user_id)
    return user_data.get("admin", False)

def get_user_remaining_generations(user_id: int) -> int:
    """Obtiene el número de generaciones restantes para un usuario"""
    user_data = get_user_data(user_id)
    return user_data.get("remaining_generations", 0)

def decrease_user_generations(user_id: int) -> bool:
    """Decrementar el contador de un usuario. Retorna True si era válido, False si ya no tiene más"""
    config = load_user_config()
    user_key = str(user_id)
    
    if user_key not in config["users"]:
        return False
    
    current = config["users"][user_key].get("remaining_generations", 0)
    if current <= 0:
        return False
    
    config["users"][user_key]["remaining_generations"] = current - 1
    save_user_config(config)
    return True

def reset_user_generations(user_id: int, new_count: int = None) -> None:
    """Resetea el contador de un usuario específico y actualiza max_generations si es necesario"""
    config = load_user_config()
    user_key = str(user_id)
    
    if user_key not in config["users"]:
        get_user_data(user_id)  # Crear usuario si no existe
        config = load_user_config()  # Recargar
    
    if new_count is None:
        # Si no se especifica cantidad, resetear a su máximo actual
        new_count = config["users"][user_key].get("max_generations", get_default_max_generations())
    else:
        # Si se especifica una cantidad, actualizar también el max_generations
        current_max = config["users"][user_key].get("max_generations", get_default_max_generations())
        if new_count > current_max:
            # Si la nueva cantidad es mayor que el máximo actual, actualizar el máximo
            config["users"][user_key]["max_generations"] = new_count
            print(f"📈 Máximo actualizado para usuario {user_id}: {current_max} → {new_count}")
    
    config["users"][user_key]["remaining_generations"] = new_count
    save_user_config(config)

def reset_all_generations() -> None:
    """Resetea todos los contadores a su máximo personal"""
    config = load_user_config()
    for user_key, user_data in config["users"].items():
        user_data["remaining_generations"] = user_data.get("max_generations", get_default_max_generations())
    save_user_config(config)

def update_user_permissions(user_id: int, authorized: bool = None, admin: bool = None, max_generations: int = None, name: str = None) -> None:
    """Actualiza los permisos y configuración de un usuario"""
    config = load_user_config()
    user_key = str(user_id)
    
    if user_key not in config["users"]:
        get_user_data(user_id)  # Crear usuario si no existe
        config = load_user_config()  # Recargar
    
    user_data = config["users"][user_key]
    
    if authorized is not None:
        user_data["authorized"] = authorized
    if admin is not None:
        user_data["admin"] = admin
    if max_generations is not None:
        user_data["max_generations"] = max_generations
        user_data["remaining_generations"] = max_generations  # Resetear también el restante
    if name is not None:
        user_data["name"] = name
    
    save_user_config(config)

# Eliminar las listas hardcoded ya que ahora se definen en el JSON
# AUTHORIZED_USERS y ADMIN_USERS ahora se cargan dinámicamente

# Para obtener tu user_id, puedes usar el bot @userinfobot en Telegram
# o usar el comando /info del bot

# (Las funciones de autenticación ahora están arriba definidas usando el JSON)

async def check_user_authorization(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Verifica solo si el usuario está en la lista autorizada"""
    user_id = update.effective_user.id
    if not is_user_authorized(user_id):
        await update.message.reply_text(
            "❌ Acceso denegado. No tienes permisos para usar este bot.\n"
            f"Tu user_id es: {user_id}"
        )
        return False
    return True

# Estados de la conversación
ELEGIR_COMPETICION, ELEGIR_GRUPO, ELEGIR_EQUIPO, CONFIRMAR_EQUIPO = range(4)

# ==========================
# CARGA Y EXTRACCIÓN DEL JSON
# ==========================

def load_data_json(path: Path = DATA_PATH, temporada: str = TEMPORADA_ACTUAL) -> dict:
    """
    Carga el archivo JSON de datos. 
    Si es un archivo histórico multi-temporada, extrae la temporada especificada.
    """
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra el JSON en: {path}")
    
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Detectar si es archivo histórico multi-temporada
    if "temporadas" in data:
        print(f"📚 Archivo histórico detectado. Extrayendo temporada {temporada}...")
        if temporada not in data["temporadas"]:
            available = list(data["temporadas"].keys())
            raise ValueError(f"Temporada {temporada} no encontrada. Disponibles: {available}")
        return data["temporadas"][temporada]
    
    # Archivo simple (formato antiguo)
    print(f"📄 Archivo simple detectado (formato antiguo)")
    return data


def _as_team_name(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("nombre", "")).strip()
    return str(item).strip()


def extract_structures(data: dict) -> Tuple[List[str], Dict[str, List[str]], Dict[Tuple[str, str], List[str]]]:
    """
    Devuelve:
      - COMPETICIONES: lista de categorías
      - GRUPOS: {categoria -> [grupos]}
      - EQUIPOS: {(categoria, grupo) -> [equipos]}
    """
    categorias = data.get("categorias", {})
    if not isinstance(categorias, dict):
        raise ValueError("El JSON no tiene 'categorias' con el formato esperado.")

    competiciones: List[str] = []
    grupos_por_categoria: Dict[str, List[str]] = {}
    equipos_por_cat_grp: Dict[Tuple[str, str], List[str]] = {}

    for cat_name, cat_obj in categorias.items():
        competiciones.append(cat_name)
        grupos_obj = (cat_obj or {}).get("grupos", {})
        if not isinstance(grupos_obj, dict):
            grupos_obj = {}

        grupos: List[str] = []
        for grp_name, grp_obj in grupos_obj.items():
            grupos.append(grp_name)
            equipos_list = (grp_obj or {}).get("equipos", [])
            if not isinstance(equipos_list, list):
                equipos_list = []
            team_names = [_as_team_name(e) for e in equipos_list if _as_team_name(e)]
            equipos_por_cat_grp[(cat_name, grp_name)] = team_names

        grupos_por_categoria[cat_name] = grupos

    return competiciones, grupos_por_categoria, equipos_por_cat_grp


# Cargamos estructuras en memoria al iniciar
DATA = load_data_json()
COMPETICIONES, GRUPOS, EQUIPOS = extract_structures(DATA)

# Crear directorio data si no existe
BASE_DIR.joinpath("data").mkdir(exist_ok=True)


# ==========================
# HOOK DE INTEGRACIÓN: AQUÍ TE LLEGO LA SELECCIÓN
# ==========================

async def on_selection(competicion: str, grupo: str, equipo: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reemplaza el contenido de esta función con tu lógica real.
    Aquí tienes los parámetros seleccionados para usarlos en Python.
    """
    # Ejemplo 1: imprimir en consola (verás esto en el terminal)
    print(f"[SELECCION] competicion={competicion} | grupo={grupo} | equipo={equipo}")

    # Ejemplo 2 (opcional): llamar a una función síncrona pesada
    # def mi_pipeline(c, g, e):
    #     ...
    # await asyncio.to_thread(mi_pipeline, competicion, grupo, equipo)

    # Ejemplo 3 (opcional): escribir a un archivo local
    # Path("ultima_seleccion.txt").write_text(f"{competicion};{grupo};{equipo}", encoding="utf-8")


# ==========================
# HANDLERS
# ==========================

async def menu_categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de categorías, tanto si viene de /start como de un callback (restart)."""
    user_id = update.effective_user.id
    remaining = get_user_remaining_generations(user_id)
    user_data = get_user_data(user_id)
    max_generations = user_data.get("max_generations", get_default_max_generations())
    user_name = user_data.get("name", update.effective_user.first_name or f"Usuario {user_id}")
    
    # Crear botones con bloqueo para "1ª FEB"
    teclado = []
    for i, comp in enumerate(COMPETICIONES):
        if comp == "1ª FEB":
            # Botón bloqueado - no hace nada al presionarse
            teclado.append([InlineKeyboardButton(text=f"🔒 {comp} [BLOQUEADO]", callback_data="locked_1feb")])
        else:
            teclado.append([InlineKeyboardButton(text=f"🏆 {comp}", callback_data=f"comp::{i}")])

    
    text = (f"🏀 **¡Hola {user_name}!**\n\n"
            f"📋 *Selecciona la competición que quieres analizar:*\n\n"
            f"📊 **Generaciones disponibles:** {remaining} de {max_generations}\n\n"
            f"💡 Usa `/help` para ver todos los comandos disponibles\n"
            f"⚡ Si no responde, escribe /start para arrancar el bot")
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(teclado), parse_mode='Markdown')
    else:
        # CallbackQuery; reutilizamos el mismo mensaje
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(teclado), parse_mode='Markdown')
    return ELEGIR_COMPETICION


async def menu_categorias_silencioso(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Envía el menú de categorías sin responder a un mensaje específico."""
    # Necesitamos obtener el user_id desde el contexto o pasarlo como parámetro
    # Por ahora asumimos que está en el contexto de la conversación
    user_id = context._user_id if hasattr(context, '_user_id') else None
    remaining = get_user_remaining_generations(user_id) if user_id else get_default_max_generations()
    
    if user_id:
        user_data = get_user_data(user_id)
        max_generations = user_data.get("max_generations", get_default_max_generations())
        user_name = user_data.get("name", f"Usuario {user_id}")
    else:
        max_generations = get_default_max_generations()
        user_name = "Usuario"
    
    # Crear botones con bloqueo para "1ª FEB"
    teclado = []
    for i, comp in enumerate(COMPETICIONES):
        if comp == "1ª FEB":
            # Botón bloqueado - no hace nada al presionarse
            teclado.append([InlineKeyboardButton(text=f"🔒 {comp} [BLOQUEADO]", callback_data="locked_1feb")])
        else:
            teclado.append([InlineKeyboardButton(text=f"🏆 {comp}", callback_data=f"comp::{i}")])

    
    text = (f"🏀 **¡Hola {user_name}!**\n\n"
            f"📋 *Selecciona la competición que quieres analizar:*\n\n"
            f"📊 **Generaciones disponibles:** {remaining} de {max_generations}\n\n"
            f"💡 Usa `/help` para ver todos los comandos disponibles\n"
            f"⚡ Si no responde, escribe /start para arrancar el bot")
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(teclado),
        parse_mode='Markdown'
    )
    return ELEGIR_COMPETICION


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Verificar si el usuario está en la lista autorizada
    if not await check_user_authorization(update, context):
        return ConversationHandler.END
    
    # Limpiar contexto y mostrar menú de categorías
    context.user_data.clear()
    return await menu_categorias(update, context)


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Verificar autorización para callbacks
    user_id = update.effective_user.id
    if not is_user_authorized(user_id):
        query = update.callback_query
        await query.answer("❌ Usuario no autorizado", show_alert=True)
        return ConversationHandler.END
    
    # Viene de un callback "restart": limpia y envía NUEVO mensaje (no edita)
    context.user_data.clear()
    context._user_id = user_id  # Guardar user_id para menu_categorias_silencioso
    
    query = update.callback_query
    await query.answer()
    
    # Enviar nuevo mensaje en lugar de editar el existente
    return await menu_categorias_silencioso(query.message.chat_id, context)


async def elegir_competicion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, idx_str = query.data.split("::", maxsplit=1)
    cidx = int(idx_str)

    if cidx < 0 or cidx >= len(COMPETICIONES):
        await query.edit_message_text("Competición inválida. Usa /start para empezar de nuevo.")
        return ConversationHandler.END

    competicion = COMPETICIONES[cidx]
    context.user_data["competicion"] = competicion

    grupos = GRUPOS.get(competicion, [])
    teclado = [[InlineKeyboardButton(text=f"👥 {g}", callback_data=f"grupo::{i}")]
               for i, g in enumerate(grupos)]
    teclado.append([InlineKeyboardButton("⬅️ Volver", callback_data="back_comp"),
                    InlineKeyboardButton("🔁 Reiniciar", callback_data="restart")])

    await query.edit_message_text(
        f"🏆 **Competición:** {competicion}\n\n👥 **Ahora elige el grupo:**\n\n⚡ Si no responde, escribe /start para arrancar el bot",
        reply_markup=InlineKeyboardMarkup(teclado),
        parse_mode='Markdown'
    )
    return ELEGIR_GRUPO


async def elegir_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, idx_str = query.data.split("::", maxsplit=1)
    gidx = int(idx_str)

    competicion = context.user_data.get("competicion")
    grupos = GRUPOS.get(competicion, [])
    if gidx < 0 or gidx >= len(grupos):
        await query.edit_message_text("Grupo inválido. Usa /start para empezar de nuevo.")
        return ConversationHandler.END

    grupo = grupos[gidx]
    context.user_data["grupo"] = grupo

    equipos = EQUIPOS.get((competicion, grupo), [])
    context.user_data["equipos_list"] = equipos  # para mapear índice -> nombre

    teclado = [[InlineKeyboardButton(text=f"🏀 {e}", callback_data=f"equipo::{i}")]
               for i, e in enumerate(equipos)]
    teclado.append([InlineKeyboardButton("⬅️ Volver", callback_data="back_grupo"),
                    InlineKeyboardButton("🔁 Reiniciar", callback_data="restart")])

    await query.edit_message_text(
        f"👥 **Grupo:** {grupo}\n\n🏀 **Elige el equipo:**\n\n⚡ Si no responde, escribe /start para arrancar el bot",
        reply_markup=InlineKeyboardMarkup(teclado),
        parse_mode='Markdown'
    )
    return ELEGIR_EQUIPO


async def elegir_equipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Selección final de equipo por índice
    _, idx_str = query.data.split("::", maxsplit=1)
    eidx = int(idx_str)

    equipos_list: List[str] = context.user_data.get("equipos_list", [])
    if eidx < 0 or eidx >= len(equipos_list):
        await query.answer("Equipo inválido", show_alert=True)
        return ConversationHandler.END

    equipo = equipos_list[eidx]
    context.user_data["equipo"] = equipo

    competicion = context.user_data.get("competicion")
    grupo = context.user_data.get("grupo")

    # Pantalla de confirmación
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirmar", callback_data="confirm_equipo")],
        [InlineKeyboardButton("🔄 Cambiar equipo", callback_data="back_equipos")],
        [InlineKeyboardButton("⬅️ Volver a grupos", callback_data="back_grupo")],
        [InlineKeyboardButton("🔁 Reiniciar", callback_data="restart")]
    ])
    await query.edit_message_text(
        f"📋 **Confirma tu selección:**\n\n"
        f"🏆 **Competición:** {competicion}\n"
        f"👥 **Grupo:** {grupo}\n"
        f"🏀 **Equipo:** {equipo}\n\n"
        f"✅ ¿Generar informe PDF?",
        reply_markup=kb,
        parse_mode='Markdown'
    )
    return CONFIRMAR_EQUIPO


async def locked_1feb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para el botón bloqueado de 1º FEB"""
    query = update.callback_query
    await query.answer(
        "🔒 Primera FEB no está disponible aún.\n\n"
        "Esta competición estará habilitada próximamente. 🏀",
        show_alert=True
    )
    # No cambiar el estado, mantener en el mismo menú
    return ELEGIR_COMPETICION


async def get_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para obtener información del usuario (útil para configurar autorización)"""
    user = update.effective_user
    chat = update.effective_chat
    remaining = get_user_remaining_generations(user.id)
    user_data = get_user_data(user.id)
    max_generations = user_data.get("max_generations", get_default_max_generations())
    user_name = user_data.get("name", user.first_name or f"Usuario {user.id}")
    is_auth = "✅ Autorizado" if user_data.get("authorized", False) else "❌ No autorizado"
    is_admin = "👑 Administrador" if user_data.get("admin", False) else "👤 Usuario regular"
    
    info_text = f"""
🆔 **¡Hola {user_name}!**

**Información del Usuario:**
• User ID: `{user.id}`
• Username: @{user.username if user.username else 'Sin username'}
• Nombre Telegram: {user.first_name} {user.last_name if user.last_name else ''}
• Chat ID: `{chat.id}`
• Estado: {is_auth}
• Rol: {is_admin}
• 📊 Generaciones restantes: {remaining} de {max_generations}

Para autorizar este usuario, agrega su User ID ({user.id}) al archivo JSON.
    """
    
    await update.message.reply_text(info_text, parse_mode='Markdown')

async def check_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para verificar las generaciones restantes del usuario"""
    user_id = update.effective_user.id
    remaining = get_user_remaining_generations(user_id)
    user_data = get_user_data(user_id)
    max_generations = user_data.get("max_generations", get_default_max_generations())
    user_name = user_data.get("name", update.effective_user.first_name or f"Usuario {user_id}")
    
    await update.message.reply_text(
        f"📊 **¡Hola {user_name}!**\n\n"
        f"**Tus generaciones de PDF:**\n\n"
        f"• Restantes: {remaining}\n"
        f"• Máximo personal: {max_generations}\n"
        f"• Utilizadas: {max_generations - remaining}",
        parse_mode='Markdown'
    )

async def admin_reset_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando administrativo para resetear el contador de un usuario específico"""
    user_id = update.effective_user.id
    
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ No tienes permisos de administrador.")
        return
    
    try:
        # Formato: /reset_user <user_id> [cantidad]
        args = context.args
        if len(args) < 1:
            await update.message.reply_text(
                "❌ **Uso incorrecto**\n\n"
                "Formato: `/reset_user <user_id> [cantidad]`\n\n"
                "**Ejemplos:**\n"
                "• `/reset_user 123456789` (resetea a su máximo actual)\n"
                "• `/reset_user 123456789 25` (asigna 25 generaciones)\n"
                "• `/reset_user 123456789 150` (asigna 150 y actualiza máximo si es necesario)\n\n"
                "**Nota:** Si la cantidad es mayor que el máximo actual, se actualizará automáticamente el límite máximo.",
                parse_mode='Markdown'
            )
            return
        
        target_user_id = int(args[0])
        
        # Obtener datos actuales del usuario antes del cambio
        old_user_data = get_user_data(target_user_id)
        old_remaining = old_user_data.get("remaining_generations", 0)
        old_max = old_user_data.get("max_generations", get_default_max_generations())
        
        new_count = int(args[1]) if len(args) > 1 else old_max
        
        reset_user_generations(target_user_id, new_count)
        
        # Obtener datos actualizados
        new_user_data = get_user_data(target_user_id)
        new_max = new_user_data.get("max_generations", get_default_max_generations())
        user_name = new_user_data.get("name", f"Usuario {target_user_id}")
        
        # Crear mensaje informativo
        message = f"✅ **Usuario actualizado: {user_name}**\n\n"
        message += f"• User ID: `{target_user_id}`\n"
        message += f"• Generaciones: {old_remaining} → {new_count}\n"
        
        if new_max != old_max:
            message += f"• Máximo: {old_max} → {new_max} 📈\n"
            message += f"\n💡 Se aumentó el límite máximo porque {new_count} > {old_max}"
        else:
            message += f"• Máximo: {new_max} (sin cambios)\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except ValueError:
        await update.message.reply_text("❌ Error: User ID debe ser un número.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def admin_reset_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando administrativo para resetear todos los contadores"""
    user_id = update.effective_user.id
    
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ No tienes permisos de administrador.")
        return
    
    reset_all_generations()
    await update.message.reply_text(
        f"✅ **Todos los contadores reseteados**\n\n"
        f"Todos los usuarios vuelven a tener sus generaciones máximas disponibles.",
        parse_mode='Markdown'
    )

async def admin_list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando administrativo para listar usuarios y sus contadores"""
    user_id = update.effective_user.id
    
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ No tienes permisos de administrador.")
        return
    
    config = load_user_config()
    users = config.get("users", {})
    
    if not users:
        await update.message.reply_text("📊 No hay usuarios registrados.")
        return
    
    text = "📊 **Lista de usuarios:**\n\n"
    for user_str, user_data in users.items():
        name = user_data.get("name", f"User {user_str}")
        remaining = user_data.get("remaining_generations", 0)
        max_gen = user_data.get("max_generations", 0)
        authorized = "✅" if user_data.get("authorized", False) else "❌"
        admin = "👑" if user_data.get("admin", False) else "👤"
        
        text += f"• {admin} {name} ({user_str})\n"
        text += f"  {authorized} Auth | {remaining}/{max_gen} PDFs\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para mostrar la lista de comandos disponibles"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    user_name = user_data.get("name", update.effective_user.first_name or f"Usuario {user_id}")
    is_admin = user_data.get("admin", False)
    is_authorized = user_data.get("authorized", False)
    
    if not is_authorized:
        await update.message.reply_text(
            f"❌ **Hola {user_name}**\n\n"
            "No estás autorizado para usar este bot.\n"
            "Contacta con el administrador para obtener acceso.",
            parse_mode='Markdown'
        )
        return
    
    # Comandos básicos para todos los usuarios autorizados
    help_text = f"🤖 **¡Hola {user_name}!**\n\n"
    help_text += "**📋 Comandos disponibles:**\n\n"
    
    help_text += "**🏀 Uso Principal:**\n"
    help_text += "• `/start` - Iniciar el bot y generar PDFs\n"
    help_text += "• `Botones interactivos` - Navegar por competiciones/equipos\n\n"
    
    help_text += "**📊 Información Personal:**\n"
    help_text += "• `/info` - Ver tu información completa\n"
    help_text += "• `/limits` - Ver tus generaciones restantes\n"
    help_text += "• `/help` - Mostrar esta ayuda\n\n"
    
    # Comandos adicionales para administradores
    if is_admin:
        help_text += "**👑 Comandos de Administrador:**\n\n"
        
        help_text += "**👥 Gestión de Usuarios:**\n"
        help_text += "• `/list_users` - Ver todos los usuarios\n"
        help_text += "• `/authorize_user <id> <true/false> [admin] [max] [name]`\n"
        help_text += "  Ejemplo: `/authorize_user 123 true admin 100 Juan`\n\n"
        
        help_text += "**📊 Gestión de Contadores:**\n"
        help_text += "• `/reset_user <id> [cantidad]` - Resetear contador\n"
        help_text += "  Ejemplo: `/reset_user 123 50`\n"
        help_text += "• `/reset_all` - Resetear todos los contadores\n\n"
        
        help_text += "**💡 Notas de Admin:**\n"
        help_text += "• Si asignas generaciones > máximo actual, se actualiza el máximo\n"
        help_text += "• Los cambios se guardan automáticamente en el JSON\n"
    
    help_text += "\n**🔧 Soporte:**\n"
    help_text += "Si tienes problemas, contacta con el administrador del bot."
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def commands_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias para el comando help"""
    await help_command(update, context)

async def admin_authorize_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando administrativo para autorizar/desautorizar usuarios"""
    user_id = update.effective_user.id
    
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ No tienes permisos de administrador.")
        return
    
    try:
        # Formato: /authorize_user <user_id> <true/false> [admin] [max_generations] [name]
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "❌ **Uso incorrecto**\n\n"
                "Formato: `/authorize_user <user_id> <true/false> [admin] [max_gen] [name]`\n\n"
                "Ejemplos:\n"
                "• `/authorize_user 123456789 true` (autorizar usuario)\n"
                "• `/authorize_user 123456789 true admin 100 Juan` (admin con 100 PDFs)\n"
                "• `/authorize_user 123456789 false` (desautorizar)",
                parse_mode='Markdown'
            )
            return
        
        target_user_id = int(args[0])
        authorized = args[1].lower() == 'true'
        admin = len(args) > 2 and args[2].lower() == 'admin'
        max_gen = int(args[3]) if len(args) > 3 and args[3].isdigit() else get_default_max_generations()
        name = " ".join(args[4:]) if len(args) > 4 else f"User {target_user_id}"
        
        update_user_permissions(
            target_user_id, 
            authorized=authorized, 
            admin=admin, 
            max_generations=max_gen,
            name=name
        )
        
        status = "✅ Autorizado" if authorized else "❌ Desautorizado"
        role = "👑 Admin" if admin else "👤 Usuario"
        
        await update.message.reply_text(
            f"✅ **Usuario actualizado**\n\n"
            f"• User ID: `{target_user_id}`\n"
            f"• Nombre: {name}\n"
            f"• Estado: {status}\n"
            f"• Rol: {role}\n"
            f"• Generaciones: {max_gen}",
            parse_mode='Markdown'
        )
        
    except ValueError:
        await update.message.reply_text("❌ Error: User ID debe ser un número.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada. Usa /start para comenzar de nuevo.")
    return ConversationHandler.END


async def mensaje_no_permitido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes de texto cuando el usuario debe usar solo botones."""
    # Eliminar el mensaje del usuario
    try:
        await update.message.delete()
    except:
        pass  # Si no se puede eliminar, continuar sin error
    
    # No enviar mensaje de advertencia, solo borrar
    return None


async def back_competicion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await menu_categorias(update, context)


async def back_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    competicion = context.user_data.get("competicion")
    grupos = GRUPOS.get(competicion, [])
    teclado = [[InlineKeyboardButton(text=g, callback_data=f"grupo::{i}")]
               for i, g in enumerate(grupos)]
    teclado.append([InlineKeyboardButton("⬅️ Volver", callback_data="back_comp"),
                    InlineKeyboardButton("🔁 Reiniciar", callback_data="restart")])
    await query.edit_message_text(
        f"Competición: {competicion}\nElige el grupo:\n\n* Si no responde, escribe /start para arrancar el bot",
        reply_markup=InlineKeyboardMarkup(teclado)
    )
    return ELEGIR_GRUPO


async def back_equipos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    competicion = context.user_data.get("competicion")
    grupo = context.user_data.get("grupo")
    equipos = EQUIPOS.get((competicion, grupo), [])
    context.user_data["equipos_list"] = equipos
    teclado = [[InlineKeyboardButton(text=e, callback_data=f"equipo::{i}")]
               for i, e in enumerate(equipos)]
    teclado.append([InlineKeyboardButton("⬅️ Volver", callback_data="back_grupo"),
                    InlineKeyboardButton("🔁 Reiniciar", callback_data="restart")])
    await query.edit_message_text(
        f"Grupo: {grupo}\nElige el equipo:\n\n* Si no responde, escribe /start para arrancar el bot",
        reply_markup=InlineKeyboardMarkup(teclado)
    )
    return ELEGIR_EQUIPO


async def confirm_equipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Verificar si el usuario tiene generaciones restantes
    remaining = get_user_remaining_generations(user_id)
    user_data = get_user_data(user_id)
    max_generations = user_data.get("max_generations", get_default_max_generations())
    
    if remaining <= 0:
        await query.edit_message_text(
            f"❌ **Límite alcanzado**\n\n"
            f"Has agotado tus {max_generations} generaciones de PDF disponibles.\n\n"
            f"Contacta con el administrador si necesitas más generaciones.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Volver al menú", callback_data="restart")]
            ]),
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    # Decrementar el contador INMEDIATAMENTE
    if not decrease_user_generations(user_id):
        await query.edit_message_text(
            f"❌ Error: No tienes generaciones disponibles.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Volver al menú", callback_data="restart")]
            ])
        )
        return ConversationHandler.END
    
    competicion = context.user_data.get("competicion")
    grupo = context.user_data.get("grupo")
    equipo = context.user_data.get("equipo")
    
    # Añadir a la cola
    queue_data = {
        "competicion": competicion,
        "grupo": grupo,
        "equipo": equipo,
        "remaining": remaining - 1,  # Ya decrementado
        "max_generations": max_generations,
        "chat_id": query.message.chat_id,
        "message_id": query.message.message_id
    }
    queue_position = add_to_queue(user_id, queue_data)
    
    # Mostrar mensaje inicial con posición en cola
    queue_text = f"📍 **Posición en cola:** {queue_position}\n" if queue_position > 1 else ""
    
    await query.edit_message_text(
        f"✅ **Petición recibida y confirmada**\n\n"
        f"🏆 **Competición:** {competicion}\n"
        f"👥 **Grupo:** {grupo}\n"
        f"🏀 **Equipo:** {equipo}\n\n"
        f"{queue_text}"
        f"📊 **Generaciones restantes:** {remaining - 1} de {max_generations}\n\n"
        f"📬 *Te enviaré el PDF cuando esté listo. Puedes seguir usando el bot.*\n\n"
        f"⏳ Tiempo estimado: ~{queue_position * 2} minutos",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔁 Volver al menú", callback_data="restart")]
        ]),
        parse_mode='Markdown'
    )
    
    # Crear tarea en background (NO BLOQUEA)
    asyncio.create_task(
        process_pdf_background(
            user_id=user_id,
            chat_id=query.message.chat_id,
            competicion=competicion,
            grupo=grupo,
            equipo=equipo,
            remaining=remaining - 1,
            max_generations=max_generations,
            context=context
        )
    )
    
    # Retornar END inmediatamente - la interfaz NO se bloquea
    return ConversationHandler.END


async def process_pdf_background(
    user_id: int,
    chat_id: int,
    competicion: str,
    grupo: str,
    equipo: str,
    remaining: int,
    max_generations: int,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    Procesa la generación del PDF en segundo plano.
    Esta función se ejecuta sin bloquear la interfaz del bot.
    """
    try:
        # ESPERAR TURNO: Solo un PDF puede generarse a la vez
        async with processing_lock:
            # Notificar que ahora es el turno del usuario
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🔄 **Generando tu PDF ahora**\n\n"
                         f"🏀 **Equipo:** {equipo}\n"
                         f"⏳ *Tiempo aproximado: 2 minutos...*",
                    parse_mode='Markdown'
                )
            except:
                pass  # Si falla el envío, continuar igual
            
            # Generar el PDF (bloquea solo este proceso, no la interfaz)
            pdf_path = await asyncio.to_thread(
                generar_pdf_final,
                DATA_PATH,  # JSON_PATH
                competicion,  # liga
                grupo,  # grupo
                equipo,  # equipo
                None,  # datos_json_path
                None,  # results_csv_path
                None,  # court_image_path
                None,  # jugadores
                None,  # max_matches
                TEMPORADA_ACTUAL  # temporada
            )
        
        # Eliminar de la cola después de completar (fuera del lock)
        remove_from_queue(user_id)
        
        # Enviar el archivo PDF
        if pdf_path and Path(pdf_path).exists():
            # Mensaje de notificación
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🏀 Generar otro informe", callback_data="restart")]
            ])
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ **¡PDF listo!**\n\n"
                     f"🏀 Equipo: {equipo}\n"
                     f"📊 Te quedan {remaining} generaciones de {max_generations}",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            # Enviar el PDF
            with open(pdf_path, 'rb') as pdf_file:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=pdf_file,
                    filename=f"Informe_{equipo.replace(' ', '_')}.pdf",
                    caption=f"📊 Informe de scouting\n\n"
                           f"🏀 {equipo}\n"
                           f"🏆 {competicion} - {grupo}\n\n"
                           f"📊 Generaciones restantes: {remaining}"
                )
        else:
            # Si el PDF falló, devolver la generación al usuario
            remove_from_queue(user_id)
            reset_user_generations(user_id, remaining + 1)  # +1 porque ya se decrementó
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ **Error al generar el PDF**\n\n"
                     f"El archivo no fue encontrado.\n\n"
                     f"📊 Generación devuelta - Restantes: {remaining + 1}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔁 Reintentar", callback_data="restart")]
                ]),
                parse_mode='Markdown'
            )
            
    except Exception as e:
        print(f"Error generando PDF en background: {e}")
        
        # Si hubo error, devolver la generación al usuario
        remove_from_queue(user_id)
        reset_user_generations(user_id, remaining + 1)  # +1 porque ya se decrementó
        
        # Enviar mensaje de error
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ **Error generando el informe**\n\n"
                 f"```\n{str(e)}\n```\n\n"
                 f"📊 Generación devuelta - Restantes: {remaining + 1}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Reintentar", callback_data="restart")]
            ]),
            parse_mode='Markdown'
        )


# ==========================
# MAIN
# ==========================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja errores del bot"""
    print(f"Update {update} caused error {context.error}")

def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("Falta la variable de entorno TELEGRAM_TOKEN")

    # Configurar timeouts más largos para operaciones que toman tiempo
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .read_timeout(300)      # 5 minutos para leer respuestas
        .write_timeout(300)     # 5 minutos para enviar datos
        .connect_timeout(30)    # 30 segundos para conectar
        .pool_timeout(30)       # 30 segundos para obtener conexión del pool
        .build()
    )

    # Agregar manejador de errores
    app.add_error_handler(error_handler)

    # Agregar comandos independientes
    app.add_handler(CommandHandler("info", get_user_info))
    app.add_handler(CommandHandler("limits", check_limits))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("commands", commands_command))
    
    # Comandos administrativos
    app.add_handler(CommandHandler("reset_user", admin_reset_user))
    app.add_handler(CommandHandler("reset_all", admin_reset_all))
    app.add_handler(CommandHandler("list_users", admin_list_users))
    app.add_handler(CommandHandler("authorize_user", admin_authorize_user))
    
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            # Permite que el botón "restart" funcione incluso si la conversación terminó
            CallbackQueryHandler(restart, pattern=r"^restart$")
        ],
        states={
            ELEGIR_COMPETICION: [
                CallbackQueryHandler(elegir_competicion, pattern=r"^comp::"),
                CallbackQueryHandler(locked_1feb_handler, pattern=r"^locked_1feb$"),
                CallbackQueryHandler(restart, pattern=r"^restart$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje_no_permitido)
            ],
            ELEGIR_GRUPO: [
                CallbackQueryHandler(elegir_grupo, pattern=r"^grupo::"),
                CallbackQueryHandler(back_competicion, pattern=r"^back_comp$"),
                CallbackQueryHandler(restart, pattern=r"^restart$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje_no_permitido)
            ],
            ELEGIR_EQUIPO: [
                CallbackQueryHandler(elegir_equipo, pattern=r"^equipo::"),
                CallbackQueryHandler(back_grupo, pattern=r"^back_grupo$"),
                CallbackQueryHandler(restart, pattern=r"^restart$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje_no_permitido)
            ],
            CONFIRMAR_EQUIPO: [
                CallbackQueryHandler(confirm_equipo, pattern=r"^confirm_equipo$"),
                CallbackQueryHandler(back_equipos, pattern=r"^back_equipos$"),
                CallbackQueryHandler(back_grupo, pattern=r"^back_grupo$"),
                CallbackQueryHandler(restart, pattern=r"^restart$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje_no_permitido)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancelar)],
        per_user=True,
        per_chat=True,
        per_message=False,  # Esto elimina el warning
    )
    app.add_handler(conv)   
    app.run_polling()


# ==========================


if __name__ == "__main__":
        main()