import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", "venapp_bot.db").strip()

# Roles válidos
ROL_SUPERVISOR = "Supervisor"
ROL_CAT = "CAT"
ROL_CAR = "CAR"

ROLES_VALIDOS = {ROL_SUPERVISOR, ROL_CAT, ROL_CAR}

# Estados del flujo
ESTADO_PENDIENTE_CAT = "Pendiente CAT"
ESTADO_LEIDO_CAT = "Leído CAT"
ESTADO_RESPUESTA_CAR = "Respuesta CAR"
ESTADO_LEIDO_SUPERVISOR = "Leído Supervisor"

# Textos de los botones del teclado
BTN_LEER_NUEVOS_CASOS = "📥 Leer nuevos casos"
BTN_HISTORIAL_CAT = "🗂️ Ver últimos reportes"
BTN_LEER_CASOS_RESUELTOS = "📋 Leer casos resueltos"
BTN_HISTORIAL_SUPERVISOR = "🗂️ Ver últimos resueltos"
BTN_PLANTILLA_CAR = "📝 Copiar Plantilla de Cierre"

