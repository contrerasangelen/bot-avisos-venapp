import logging
import os
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import telebot
from telebot import types

from config import (
    TELEGRAM_BOT_TOKEN,
    ROL_SUPERVISOR,
    ROL_CAT,
    ROL_CAR,
    MUNICIPIO_MARACAIBO,
    MUNICIPIO_SAN_FRANCISCO,
    MUNICIPIO_TODOS,
    ESTADO_PENDIENTE_CAT,
    ESTADO_LEIDO_CAT,
    ESTADO_RESPUESTA_CAR,
    ESTADO_LEIDO_SUPERVISOR,
    BTN_LEER_NUEVOS_CASOS,
    BTN_HISTORIAL_CAT,
    BTN_LEER_CASOS_RESUELTOS,
    BTN_HISTORIAL_SUPERVISOR,
    BTN_PLANTILLA_CAR
)
from database import (
    init_db,
    registrar_usuario_si_no_existe,
    asignar_rol,
    obtener_rol,
    obtener_usuario,
    obtener_municipio_usuario,
    obtener_usuarios_por_rol,
    crear_caso,
    obtener_casos_por_estado,
    marcar_casos_como_leidos,
    obtener_caso_por_id,
    obtener_ultimos_casos_por_tipo,
    buscar_casos_por_texto
)
from keyboards import obtener_teclado_por_rol
from formato_car import PLANTILLA_CAR, parsear_formato_car, formatear_respuesta_car_supervisor

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("VenAppBot")

if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "tu_token_aqui_de_botfather":
    logger.warning("ATENCIÓN: 'TELEGRAM_BOT_TOKEN' no ha sido configurado en el archivo .env o variables de entorno.")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode="HTML")

BANNER_PATH = Path(__file__).resolve().parent / "assets" / "banner.jpg"


def enviar_bienvenida_con_banner(chat_id: int, texto: str, reply_markup=None):
    """Envía la imagen institucional con el texto en caption, con fallback a send_message si falla."""
    if BANNER_PATH.exists():
        try:
            with open(BANNER_PATH, "rb") as photo:
                bot.send_photo(chat_id, photo=photo, caption=texto, reply_markup=reply_markup)
                return
        except Exception as e:
            logger.warning(f"Error al enviar banner con imagen: {e}")
    bot.send_message(chat_id, texto, reply_markup=reply_markup)


def enviar_caso_a_chat(chat_id: int, texto: str, foto_id: str = None):
    """Envía el caso al usuario: con foto si existe (y caption si cabe), o mensaje de texto plano."""
    if foto_id:
        try:
            if len(texto) <= 1024:
                bot.send_photo(chat_id, photo=foto_id, caption=texto)
            else:
                bot.send_photo(chat_id, photo=foto_id)
                bot.send_message(chat_id, texto)
            return
        except Exception as e:
            logger.warning(f"No se pudo enviar la foto con ID {foto_id} a {chat_id}: {e}")
    try:
        bot.send_message(chat_id, texto)
    except Exception as e:
        logger.warning(f"No se pudo enviar mensaje a {chat_id}: {e}")


def notificar_a_todos_los_cat(texto: str, foto_id: str = None):
    """Envía una notificación push automática a todos los usuarios con rol CAT (reciben todos los municipios)."""
    usuarios_cat = obtener_usuarios_por_rol(ROL_CAT)
    for u in usuarios_cat:
        try:
            enviar_caso_a_chat(u["user_id"], texto, foto_id)
        except Exception as e:
            logger.warning(f"Error al notificar al CAT {u['user_id']}: {e}")


def notificar_a_supervisores_de_municipio(texto: str, foto_id: str = None, municipio: str = "Maracaibo"):
    """Envía una notificación push automática únicamente a los Supervisores del municipio correspondiente."""
    usuarios_sup = obtener_usuarios_por_rol(ROL_SUPERVISOR, municipio=municipio)
    for u in usuarios_sup:
        try:
            enviar_caso_a_chat(u["user_id"], texto, foto_id)
        except Exception as e:
            logger.warning(f"Error al notificar al Supervisor {u['user_id']} ({municipio}): {e}")


def obtener_nombre_remitente(message: types.Message) -> str:
    """Extrae un nombre legible del usuario de Telegram."""
    if message.from_user.username:
        return f"@{message.from_user.username}"
    nombre = message.from_user.first_name or ""
    apellido = message.from_user.last_name or ""
    return f"{nombre} {apellido}".strip() or f"Usuario_{message.from_user.id}"


# ==========================================
# COMANDO START Y AYUDA
# ==========================================

@bot.message_handler(commands=["start"])
def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    registrar_usuario_si_no_existe(user_id, username, first_name)
    rol = obtener_rol(user_id)

    if not rol:
        markup = obtener_teclado_por_rol(None)
        texto = (
            "⚡ <b>SISTEMA 1x10 + PEGASUS (VENAPP)</b>\n"
            "<i>Gestión Integral de Reportes Eléctricos</i>\n\n"
            "🔒 <b>Estado:</b> Sin permisos / Sin rol asignado.\n\n"
            "Para comenzar a operar, solicita autorización o ejecuta tu comando de rol asignado."
        )
        enviar_bienvenida_con_banner(message.chat.id, texto, reply_markup=markup)
        return

    markup = obtener_teclado_por_rol(rol)
    municipio = obtener_municipio_usuario(user_id)
    texto = (
        f"⚡ <b>SISTEMA 1x10 + PEGASUS</b>\n"
        f"Bienvenido/a, <b>{first_name or 'Usuario'}</b>\n"
        f"Rol activo: <b>{rol}</b> (📍 <i>{municipio}</i>)\n\n"
    )

    if rol == ROL_SUPERVISOR:
        texto += (
            "📌 <b>Funciones de Supervisor:</b>\n"
            "• Escribe cualquier mensaje para registrar un nuevo reporte (<i>Pendiente CAT</i>).\n"
            "• Presiona <b>'📋 Leer casos resueltos'</b> para consultar soluciones de cuadrillas."
        )
    elif rol == ROL_CAT:
        texto += (
            "📌 <b>Funciones de CAT:</b>\n"
            "• Presiona el botón <b>'📥 Leer nuevos casos'</b> para recibir los reportes pendientes."
        )
    elif rol == ROL_CAR:
        texto += (
            "📌 <b>Funciones de CAR (Cuadrilla):</b>\n"
            "• Envía por aquí la solución técnica y se registrará como <i>Respuesta CAR</i>."
        )

    enviar_bienvenida_con_banner(message.chat.id, texto, reply_markup=markup)


@bot.message_handler(commands=["mirol"])
def cmd_mirol(message: types.Message):
    user_id = message.from_user.id
    rol = obtener_rol(user_id) or "Sin rol asignado"
    municipio = obtener_municipio_usuario(user_id) if rol != "Sin rol asignado" else "N/A"
    markup = obtener_teclado_por_rol(rol)
    
    texto = (
        f"👤 <b>Información del Usuario:</b>\n"
        f"• <b>ID:</b> <code>{user_id}</code>\n"
        f"• <b>Nombre:</b> {message.from_user.first_name}\n"
        f"• <b>Username:</b> @{message.from_user.username or 'N/A'}\n"
        f"• <b>Rol asignado:</b> <b>{rol}</b>\n"
        f"• <b>Municipio:</b> 📍 <b>{municipio}</b>"
    )
    bot.reply_to(message, texto, reply_markup=markup)


# ==========================================
# ASIGNACIÓN DE ROLES (COMANDOS OCULTOS)
# ==========================================

@bot.message_handler(commands=["soysupervisor", "soysupervisormcb"])
def cmd_soy_supervisor(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    asignar_rol(user_id, ROL_SUPERVISOR, municipio=MUNICIPIO_MARACAIBO, username=username, first_name=first_name)
    markup = obtener_teclado_por_rol(ROL_SUPERVISOR)

    texto = (
        "✅ <b>Rol Asignado con Éxito: SUPERVISOR (MARACAIBO)</b>\n\n"
        "A partir de este momento puedes:\n"
        "1. <b>Enviar reportes:</b> Escribe cualquier mensaje con la avería eléctrica de Maracaibo "
        "y quedará guardado como <i>'Pendiente CAT'</i>.\n"
        "2. <b>Revisar soluciones:</b> Presiona <b>'📋 Leer casos resueltos'</b> "
        "para consultar las respuestas emitidas por las cuadrillas de Maracaibo."
    )
    bot.reply_to(message, texto, reply_markup=markup)
    logger.info(f"Usuario {user_id} ({username}) asignado como Supervisor (Maracaibo).")


@bot.message_handler(commands=["soysupervisorsfc"])
def cmd_soy_supervisor_sfc(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    asignar_rol(user_id, ROL_SUPERVISOR, municipio=MUNICIPIO_SAN_FRANCISCO, username=username, first_name=first_name)
    markup = obtener_teclado_por_rol(ROL_SUPERVISOR)

    texto = (
        "✅ <b>Rol Asignado con Éxito: SUPERVISOR (SAN FRANCISCO)</b>\n\n"
        "A partir de este momento puedes:\n"
        "1. <b>Enviar reportes:</b> Escribe cualquier mensaje con la avería eléctrica de San Francisco "
        "y quedará guardado como <i>'Pendiente CAT'</i>.\n"
        "2. <b>Revisar soluciones:</b> Presiona <b>'📋 Leer casos resueltos'</b> "
        "para consultar las respuestas emitidas por las cuadrillas de San Francisco."
    )
    bot.reply_to(message, texto, reply_markup=markup)
    logger.info(f"Usuario {user_id} ({username}) asignado como Supervisor (San Francisco).")


@bot.message_handler(commands=["soycat"])
def cmd_soy_cat(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    asignar_rol(user_id, ROL_CAT, municipio=MUNICIPIO_TODOS, username=username, first_name=first_name)
    markup = obtener_teclado_por_rol(ROL_CAT)

    texto = (
        "✅ <b>Rol Asignado con Éxito: CAT (SALA SITUACIONAL CENTRAL)</b>\n\n"
        "A partir de este momento recibirás y podrás gestionar los reportes de "
        "<b>Maracaibo</b> y <b>San Francisco</b> de forma centralizada.\n\n"
        "• Presiona <b>'📥 Leer nuevos casos'</b> para recibir los reportes pendientes con su etiqueta de municipio."
    )
    bot.reply_to(message, texto, reply_markup=markup)
    logger.info(f"Usuario {user_id} ({username}) asignado como CAT (Central).")


@bot.message_handler(commands=["soycar", "soycarmcb"])
def cmd_soy_car(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    asignar_rol(user_id, ROL_CAR, municipio=MUNICIPIO_MARACAIBO, username=username, first_name=first_name)
    markup = obtener_teclado_por_rol(ROL_CAR)

    texto = (
        "✅ <b>Rol Asignado con Éxito: CAR / CUADRILLA (MARACAIBO)</b>\n\n"
        "A partir de este momento puedes reportar la atención de averías de Maracaibo.\n\n"
        "📝 Presiona el botón <b>'📝 Copiar Plantilla de Cierre'</b> o usa /plantilla "
        "para obtener el formato oficial, complétalo y envíalo."
    )
    bot.reply_to(message, texto, reply_markup=markup)
    logger.info(f"Usuario {user_id} ({username}) asignado como CAR (Maracaibo).")


@bot.message_handler(commands=["soycarsfc"])
def cmd_soy_car_sfc(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    asignar_rol(user_id, ROL_CAR, municipio=MUNICIPIO_SAN_FRANCISCO, username=username, first_name=first_name)
    markup = obtener_teclado_por_rol(ROL_CAR)

    texto = (
        "✅ <b>Rol Asignado con Éxito: CAR / CUADRILLA (SAN FRANCISCO)</b>\n\n"
        "A partir de este momento puedes reportar la atención de averías de San Francisco.\n\n"
        "📝 Presiona el botón <b>'📝 Copiar Plantilla de Cierre'</b> o usa /plantilla "
        "para obtener el formato oficial, complétalo y envíalo."
    )
    bot.reply_to(message, texto, reply_markup=markup)
    logger.info(f"Usuario {user_id} ({username}) asignado como CAR (San Francisco).")


@bot.message_handler(commands=["plantilla"])
def cmd_plantilla(message: types.Message):
    enviar_plantilla_car(message.chat.id)


def enviar_plantilla_car(chat_id: int):
    """Envía la plantilla de CAR en formato de código para copiar con un solo toque."""
    texto = (
        "📋 <b>Formato de Cierre de Cuadrilla (CAR):</b>\n\n"
        "👇 <i>Toca el recuadro inferior para copiar al portapapeles, pégalo en el chat, llena los datos y envíalo:</i>\n\n"
        f"<code>{PLANTILLA_CAR}</code>"
    )
    bot.send_message(chat_id, texto, reply_markup=obtener_teclado_por_rol(ROL_CAR))


# ==========================================
# ACCIONES DE BOTONES (CAT Y SUPERVISOR)
# ==========================================

def normalizar_texto(texto: str) -> str:
    return texto.strip().lower() if texto else ""


@bot.message_handler(commands=["caso", "ver"])
def cmd_ver_caso(message: types.Message):
    """Permite ver cualquier caso por su número de ID cuantas veces sea necesario."""
    user_id = message.from_user.id
    rol = obtener_rol(user_id)
    if not rol:
        bot.reply_to(message, "⚠️ No tienes permisos para consultar casos.")
        return

    partes = message.text.strip().split()
    if len(partes) < 2 or not partes[1].isdigit():
        bot.reply_to(message, "ℹ️ <i>Uso correcto:</i> <code>/caso 1</code> (indica el número de caso)")
        return

    caso_id = int(partes[1])
    caso = obtener_caso_por_id(caso_id)
    if not caso:
        bot.reply_to(message, f"❌ No se encontró ningún caso con el ID #{caso_id}.")
        return

    if caso["tipo"] == "RESPUESTA_CAR":
        texto_caso = formatear_respuesta_car_supervisor(caso)
    else:
        texto_caso = (
            f"⚡ <b>CASO #{caso['id']}</b>\n"
            f"📅 <b>Fecha:</b> <code>{caso['fecha_creacion']}</code>\n"
            f"👤 <b>Supervisor:</b> {caso['remitente_nombre']}\n"
            f"🏷️ <b>Estado actual:</b> <i>{caso['estado']}</i>\n"
            f"📝 <b>Reporte:</b>\n{caso['contenido']}"
        )

    enviar_caso_a_chat(message.chat.id, texto_caso, caso.get("foto_id"))


@bot.message_handler(commands=["buscar"])
def cmd_buscar(message: types.Message):
    """Busca casos por número de VenApp, reclamo o dirección."""
    user_id = message.from_user.id
    rol = obtener_rol(user_id)
    if not rol:
        bot.reply_to(message, "⚠️ No tienes permisos para buscar casos.")
        return

    partes = message.text.strip().split(maxsplit=1)
    if len(partes) < 2:
        bot.reply_to(message, "ℹ️ <i>Uso correcto:</i> <code>/buscar 14161570</code> (indica texto, VenApp o reclamo)")
        return

    termino = partes[1].strip()
    coincidencias = buscar_casos_por_texto(termino, limite=5)

    if not coincidencias:
        bot.reply_to(message, f"🔍 No se encontraron casos con el término: <b>{termino}</b>")
        return

    bot.send_message(message.chat.id, f"🔍 <b>Se encontraron {len(coincidencias)} resultado(s) para '{termino}':</b>")
    for caso in coincidencias:
        if caso["tipo"] == "RESPUESTA_CAR":
            texto_caso = formatear_respuesta_car_supervisor(caso)
        else:
            texto_caso = (
                f"⚡ <b>CASO #{caso['id']}</b>\n"
                f"📅 <b>Fecha:</b> <code>{caso['fecha_creacion']}</code>\n"
                f"👤 <b>Supervisor:</b> {caso['remitente_nombre']}\n"
                f"🏷️ <b>Estado actual:</b> <i>{caso['estado']}</i>\n"
                f"📝 <b>Reporte:</b>\n{caso['contenido']}"
            )
        enviar_caso_a_chat(message.chat.id, texto_caso, caso.get("foto_id"))


@bot.message_handler(func=lambda msg: normalizar_texto(msg.text) in ["🗂️ ver últimos reportes", "ver ultimos reportes", "ultimos reportes"])
def handler_cat_ver_ultimos(message: types.Message):
    user_id = message.from_user.id
    rol = obtener_rol(user_id)
    if rol not in [ROL_CAT, ROL_SUPERVISOR]:
        bot.reply_to(message, "⛔ Opción no permitida para tu rol.")
        return

    ultimos = obtener_ultimos_casos_por_tipo("REPORTE_SUPERVISOR", limite=5)
    if not ultimos:
        bot.reply_to(message, "📭 No hay reportes registrados aún en el sistema.")
        return

    bot.send_message(message.chat.id, f"🗂️ <b>Mostrando los últimos {len(ultimos)} reportes creados:</b>")
    for caso in ultimos:
        texto_caso = (
            f"⚡ <b>CASO #{caso['id']}</b>\n"
            f"📅 <b>Fecha:</b> <code>{caso['fecha_creacion']}</code>\n"
            f"👤 <b>Supervisor:</b> {caso['remitente_nombre']}\n"
            f"🏷️ <b>Estado actual:</b> <i>{caso['estado']}</i>\n"
            f"📝 <b>Reporte:</b>\n{caso['contenido']}"
        )
        enviar_caso_a_chat(message.chat.id, texto_caso, caso.get("foto_id"))


@bot.message_handler(func=lambda msg: normalizar_texto(msg.text) in ["🗂️ ver últimos resueltos", "ver ultimos resueltos", "ultimos resueltos"])
def handler_supervisor_ver_ultimos(message: types.Message):
    user_id = message.from_user.id
    rol = obtener_rol(user_id)
    if rol not in [ROL_SUPERVISOR, ROL_CAT]:
        bot.reply_to(message, "⛔ Opción no permitida para tu rol.")
        return

    municipio_filtro = obtener_municipio_usuario(user_id) if rol == ROL_SUPERVISOR else None
    ultimos = obtener_ultimos_casos_por_tipo("RESPUESTA_CAR", limite=5, municipio=municipio_filtro)
    if not ultimos:
        bot.reply_to(message, f"📭 No hay soluciones de cuadrillas registradas aún{' para ' + municipio_filtro if municipio_filtro else ''}.")
        return

    muni_label = f" ({municipio_filtro})" if municipio_filtro else ""
    bot.send_message(message.chat.id, f"🗂️ <b>Mostrando las últimas {len(ultimos)} soluciones recibidas{muni_label}:</b>")
    for caso in ultimos:
        texto_caso = formatear_respuesta_car_supervisor(caso)
        enviar_caso_a_chat(message.chat.id, texto_caso, caso.get("foto_id"))


@bot.message_handler(func=lambda msg: normalizar_texto(msg.text) in ["📝 copiar plantilla de cierre", "copiar plantilla de cierre", "plantilla"])
def handler_car_solicitar_plantilla(message: types.Message):
    enviar_plantilla_car(message.chat.id)


@bot.message_handler(func=lambda msg: normalizar_texto(msg.text) in ["📥 leer nuevos casos", "leer nuevos casos"])
def handler_cat_leer_nuevos_casos(message: types.Message):
    user_id = message.from_user.id
    rol = obtener_rol(user_id)

    if rol != ROL_CAT:
        bot.reply_to(
            message,
            "⛔ <b>Acceso denegado:</b> Esta opción solo está disponible para usuarios con rol <b>CAT</b>.",
            reply_markup=obtener_teclado_por_rol(rol)
        )
        return

    casos_pendientes = obtener_casos_por_estado(ESTADO_PENDIENTE_CAT)

    if not casos_pendientes:
        bot.reply_to(
            message,
            "✅ <b>No hay nuevos casos pendientes por leer.</b>\nTodos los reportes están al día.",
            reply_markup=obtener_teclado_por_rol(ROL_CAT)
        )
        return

    total = len(casos_pendientes)
    bot.send_message(
        message.chat.id,
        f"📬 <b>Se encontraron {total} caso(s) nuevo(s) 'Pendiente CAT':</b>"
    )

    ids_leidos = []
    for caso in casos_pendientes:
        muni_txt = caso.get("municipio") or "Maracaibo"
        texto_caso = (
            f"⚡ <b>CASO #{caso['id']} [📍 {muni_txt.upper()}]</b>\n"
            f"📅 <b>Fecha:</b> <code>{caso['fecha_creacion']}</code>\n"
            f"📍 <b>Municipio:</b> {muni_txt}\n"
            f"👤 <b>Supervisor:</b> {caso['remitente_nombre']} (ID: <code>{caso['remitente_id']}</code>)\n"
            f"🏷️ <b>Estado anterior:</b> <i>{caso['estado']}</i>\n"
            f"📝 <b>Reporte:</b>\n{caso['contenido']}"
        )
        enviar_caso_a_chat(message.chat.id, texto_caso, caso.get("foto_id"))
        ids_leidos.append(caso["id"])

    # Actualizar a 'Leído CAT'
    marcar_casos_como_leidos(ids_leidos, ESTADO_LEIDO_CAT)
    logger.info(f"CAT {user_id} leyó {len(ids_leidos)} casos: {ids_leidos}")

    bot.send_message(
        message.chat.id,
        f"✅ <i>Se han marcado {len(ids_leidos)} caso(s) como <b>'{ESTADO_LEIDO_CAT}'</b>.</i>",
        reply_markup=obtener_teclado_por_rol(ROL_CAT)
    )


@bot.message_handler(func=lambda msg: normalizar_texto(msg.text) in ["📋 leer casos resueltos", "leer casos resueltos"])
def handler_supervisor_leer_casos_resueltos(message: types.Message):
    user_id = message.from_user.id
    rol = obtener_rol(user_id)

    if rol != ROL_SUPERVISOR:
        bot.reply_to(
            message,
            "⛔ <b>Acceso denegado:</b> Esta opción solo está disponible para usuarios con rol <b>Supervisor</b>.",
            reply_markup=obtener_teclado_por_rol(rol)
        )
        return

    municipio_sup = obtener_municipio_usuario(user_id)
    respuestas_pendientes = obtener_casos_por_estado(ESTADO_RESPUESTA_CAR, municipio=municipio_sup)

    if not respuestas_pendientes:
        bot.reply_to(
            message,
            f"✅ <b>No hay casos resueltos pendientes por leer en {municipio_sup}.</b>\nNo hay nuevas respuestas de cuadrillas pendientes.",
            reply_markup=obtener_teclado_por_rol(ROL_SUPERVISOR)
        )
        return

    total = len(respuestas_pendientes)
    bot.send_message(
        message.chat.id,
        f"📬 <b>Se encontraron {total} caso(s) con 'Respuesta CAR' pendientes de lectura ({municipio_sup}):</b>"
    )

    ids_leidos = []
    for caso in respuestas_pendientes:
        texto_caso = formatear_respuesta_car_supervisor(caso)
        enviar_caso_a_chat(message.chat.id, texto_caso, caso.get("foto_id"))
        ids_leidos.append(caso["id"])

    # Actualizar a 'Leído Supervisor'
    marcar_casos_como_leidos(ids_leidos, ESTADO_LEIDO_SUPERVISOR)
    logger.info(f"Supervisor {user_id} ({municipio_sup}) leyó {len(ids_leidos)} respuestas CAR: {ids_leidos}")

    bot.send_message(
        message.chat.id,
        f"✅ <i>Se han marcado {len(ids_leidos)} caso(s) de {municipio_sup} como <b>'{ESTADO_LEIDO_SUPERVISOR}'</b>.</i>",
        reply_markup=obtener_teclado_por_rol(ROL_SUPERVISOR)
    )


# ==========================================
# MENSAJES DE TEXTO Y FOTOS (FLUJOS 1 Y 2)
# ==========================================

@bot.message_handler(content_types=["text", "photo"])
def handler_mensajes_y_fotos(message: types.Message):
    user_id = message.from_user.id
    remitente_nombre = obtener_nombre_remitente(message)

    # Detectar si incluye fotografía (es opcional)
    foto_id = None
    if message.content_type == "photo" and message.photo:
        foto_id = message.photo[-1].file_id
        contenido = (message.caption or "").strip() or "[Evidencia fotográfica adjunta]"
    else:
        contenido = (message.text or "").strip()

    if not contenido:
        return

    rol = obtener_rol(user_id)

    # 1. Caso sin rol asignado
    if not rol:
        markup = obtener_teclado_por_rol(None)
        bot.reply_to(
            message,
            "⚠️ <b>Acceso Restringido</b>\n\n"
            "No tienes un rol asignado en el sistema 1x10 VenApp para enviar o consultar reportes.\n"
            "Comunícate con el administrador o utiliza tu comando de rol autorizado.",
            reply_markup=markup
        )
        return

    # 2. Flujo 1 (Ida): Supervisor envía nuevo reporte (con o sin foto)
    if rol == ROL_SUPERVISOR:
        municipio_sup = obtener_municipio_usuario(user_id)
        caso_id = crear_caso(
            tipo="REPORTE_SUPERVISOR",
            remitente_id=user_id,
            remitente_nombre=remitente_nombre,
            contenido=contenido,
            estado=ESTADO_PENDIENTE_CAT,
            foto_id=foto_id,
            municipio=municipio_sup
        )
        logger.info(f"Nuevo reporte creado por Supervisor {user_id} ({municipio_sup}). Caso ID: {caso_id} (Foto: {bool(foto_id)})")
        
        adjunto_txt = "\n📸 <b>Evidencia fotográfica adjunta</b>" if foto_id else ""
        texto_confirmacion = (
            f"✅ <b>Reporte Registrado Exitosamente</b>\n\n"
            f"📍 <b>Municipio:</b> {municipio_sup}\n"
            f"🆔 <b>Caso:</b> #{caso_id}\n"
            f"🏷️ <b>Estado:</b> <code>{ESTADO_PENDIENTE_CAT}</code>"
            f"{adjunto_txt}\n"
            f"📝 <b>Detalle:</b>\n{contenido}\n\n"
            f"<i>El reporte ha sido puesto a disposición de la sala CAT.</i>"
        )
        bot.reply_to(message, texto_confirmacion, reply_markup=obtener_teclado_por_rol(ROL_SUPERVISOR))

        # Notificar automáticamente a la sala CAT con etiqueta de municipio
        texto_aviso_cat = (
            f"🔔 <b>¡NUEVO REPORTE ELÉCTRICO! [📍 {municipio_sup.upper()}]</b>\n\n"
            f"🆔 <b>Caso #{caso_id}</b>\n"
            f"📍 <b>Municipio:</b> {municipio_sup}\n"
            f"👤 <b>Supervisor:</b> {remitente_nombre}\n"
            f"📝 <b>Detalle de Avería:</b>\n{contenido}"
        )
        notificar_a_todos_los_cat(texto_aviso_cat, foto_id=foto_id)
        return

    # 3. Flujo 2 (Vuelta): CAR envía solución de la cuadrilla (con o sin foto)
    if rol == ROL_CAR:
        municipio_car = obtener_municipio_usuario(user_id)
        caso_id = crear_caso(
            tipo="RESPUESTA_CAR",
            remitente_id=user_id,
            remitente_nombre=remitente_nombre,
            contenido=contenido,
            estado=ESTADO_RESPUESTA_CAR,
            foto_id=foto_id,
            municipio=municipio_car
        )
        logger.info(f"Nueva respuesta creada por CAR {user_id} ({municipio_car}). Caso ID: {caso_id} (Foto: {bool(foto_id)})")
        
        datos_formato = parsear_formato_car(contenido)
        adjunto_txt = "\n📸 <b>Evidencia fotográfica:</b> Sí" if foto_id else ""

        if datos_formato:
            texto_confirmacion = (
                f"✅ <b>Formato de Atención Registrado con Éxito</b>\n\n"
                f"📍 <b>Municipio:</b> {municipio_car}\n"
                f"🆔 <b>Caso ID:</b> #{caso_id}\n"
                f"🏷️ <b>Estado:</b> <code>{ESTADO_RESPUESTA_CAR}</code>"
                f"{adjunto_txt}\n"
                f"📋 <b>VenApp:</b> <code>{datos_formato.get('venapp') or 'N/A'}</code>\n"
                f"🔢 <b>Reclamo:</b> <code>{datos_formato.get('reclamo') or 'N/A'}</code>\n"
                f"🚛 <b>Unidad MPPEE:</b> {datos_formato.get('unidad_mppee') or 'N/A'}\n"
                f"📍 <b>Dirección:</b> {datos_formato.get('direccion') or 'N/A'}\n"
                f"🔧 <b>Solución reportada:</b>\n{datos_formato.get('solucion') or 'N/A'}\n\n"
                f"<i>La atención fue cargada y se notificó a los Supervisores de {municipio_car}.</i>"
            )
        else:
            texto_confirmacion = (
                f"✅ <b>Solución de Cuadrilla Registrada Exitosamente</b>\n\n"
                f"📍 <b>Municipio:</b> {municipio_car}\n"
                f"🆔 <b>Caso:</b> #{caso_id}\n"
                f"🏷️ <b>Estado:</b> <code>{ESTADO_RESPUESTA_CAR}</code>"
                f"{adjunto_txt}\n"
                f"🔧 <b>Detalle reportado:</b>\n{contenido}\n\n"
                f"<i>La solución fue enviada a los Supervisores de {municipio_car}.</i>"
            )
        bot.reply_to(message, texto_confirmacion, reply_markup=obtener_teclado_por_rol(ROL_CAR))

        # Notificar automáticamente y de forma exclusiva a los supervisores de ese municipio
        caso_dict = {
            "id": caso_id,
            "tipo": "RESPUESTA_CAR",
            "remitente_nombre": remitente_nombre,
            "fecha_creacion": "Recién reportado",
            "estado": ESTADO_RESPUESTA_CAR,
            "contenido": contenido,
            "municipio": municipio_car
        }
        texto_aviso_sup = (
            f"🔔 <b>¡SOLUCIÓN DE CUADRILLA RECIBIDA! [📍 {municipio_car.upper()}]</b>\n\n"
            + formatear_respuesta_car_supervisor(caso_dict)
        )
        notificar_a_supervisores_de_municipio(texto_aviso_sup, foto_id=foto_id, municipio=municipio_car)
        return

    # 4. Caso CAT: No envía reportes por texto libre, consulta mediante el botón
    if rol == ROL_CAT:
        bot.reply_to(
            message,
            "ℹ️ <b>Rol CAT:</b> Tu función es recepcionar y gestionar las incidencias.\n"
            "Presiona el botón <b>'📥 Leer nuevos casos'</b> para revisar los reportes pendientes.",
            reply_markup=obtener_teclado_por_rol(ROL_CAT)
        )
        return


class HealthHandler(BaseHTTPRequestHandler):
    """Mini servidor HTTP para healthcheck en Render, Railway o cualquier nube."""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot 1x10 VenApp Activo 24/7")

    def log_message(self, format, *args):
        pass  # Silenciar logs continuos de healthcheck


def iniciar_servidor_web():
    port = int(os.environ.get("PORT", 10000))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        logger.info(f"Servidor web de healthcheck activo en puerto {port}")
        server.serve_forever()
    except Exception as e:
        logger.warning(f"No se pudo iniciar servidor web de healthcheck: {e}")


def main():
    """Punto de entrada principal para iniciar el bot."""
    print("Iniciando Base de Datos...")
    init_db()
    print("Base de Datos inicializada correctamente.")

    # Iniciar servidor web en segundo plano para Render/Cloud
    t = threading.Thread(target=iniciar_servidor_web, daemon=True)
    t.start()

    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "tu_token_aqui_de_botfather":
        print("\n" + "=" * 60)
        print("ADVERTENCIA: Debes colocar tu TELEGRAM_BOT_TOKEN en el archivo .env")
        print("El bot no puede conectarse a Telegram sin un token válido.")
        print("=" * 60 + "\n")
        sys.exit(1)

    print("Iniciando Bot de Telegram (Polling Infinito y Resistente a Errores)...")
    while True:
        try:
            bot.infinity_polling(skip_pending=False, timeout=20, long_polling_timeout=20)
        except Exception as e:
            logger.error(f"Error en infinity_polling, reconectando automáticamente en 5 segundos: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
