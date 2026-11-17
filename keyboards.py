from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from config import (
    ROL_SUPERVISOR,
    ROL_CAT,
    ROL_CAR,
    BTN_LEER_NUEVOS_CASOS,
    BTN_HISTORIAL_CAT,
    BTN_LEER_CASOS_RESUELTOS,
    BTN_HISTORIAL_SUPERVISOR,
    BTN_PLANTILLA_CAR
)


def obtener_teclado_por_rol(rol: str):
    """
    Retorna el teclado apropiado según el rol del usuario:
    - Supervisor: Teclado con 'Leer casos resueltos' y 'Ver últimos resueltos'
    - CAT: Teclado con 'Leer nuevos casos' y 'Ver últimos reportes'
    - CAR: Teclado con 'Copiar Plantilla de Cierre'
    - Sin rol / Desconocido: ReplyKeyboardRemove
    """
    if rol == ROL_SUPERVISOR:
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            KeyboardButton(BTN_LEER_CASOS_RESUELTOS),
            KeyboardButton(BTN_HISTORIAL_SUPERVISOR)
        )
        return markup
    elif rol == ROL_CAT:
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            KeyboardButton(BTN_LEER_NUEVOS_CASOS),
            KeyboardButton(BTN_HISTORIAL_CAT)
        )
        return markup
    elif rol == ROL_CAR:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton(BTN_PLANTILLA_CAR))
        return markup
    else:
        return ReplyKeyboardRemove()
