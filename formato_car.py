import re
from typing import Dict, Optional

PLANTILLA_CAR = """ATENDIDO
EL DIA: 
UNIDAD MPPEE: 
RECLAMO: 
VENAPP: 
OPERARIO: 
CHOFER: 
UBT: 
DIRECCION: 
OBSERVACIONES: 
SOLUCION: """


def parsear_formato_car(texto: str) -> Optional[Dict[str, str]]:
    """
    Parsea el formato estándar de cierre de atención de cuadrilla CAR.
    Retorna un diccionario con los campos si detecta la estructura, o None si es texto libre.
    """
    patrones = {
        "el_dia": r"EL DIA\s*:?\s*(.*)",
        "unidad_mppee": r"UNIDAD MPPEE\s*:?\s*(.*)",
        "reclamo": r"RECLAMO\s*:?\s*(.*)",
        "venapp": r"VENAPP\s*:?\s*,?\s*(.*)",
        "operario": r"OPERARIO\s*:?\s*(.*)",
        "chofer": r"CHOFER\s*:?\s*(.*)",
        "ubt": r"UBT\s*:?\s*(.*)",
        "direccion": r"DIRECCION\s*:?\s*(.*)",
        "observaciones": r"OBSERVACIONES\s*:?\s*(.*)",
        "solucion": r"SOLUCION\s*:?\s*(.*)",
    }

    lineas = texto.splitlines()
    resultados = {}

    # Verificar si al menos contiene campos clave característicos
    texto_upper = texto.upper()
    claves_esenciales = ["ATENDIDO", "RECLAMO:", "SOLUCION:", "VENAPP:"]
    coincidencias = sum(1 for c in claves_esenciales if c in texto_upper)

    if coincidencias < 2:
        return None

    # Extraer línea por línea para evitar que un campo vacío capture la línea siguiente
    for linea in texto.splitlines():
        linea_strip = linea.strip()
        for campo, patron in patrones.items():
            if campo not in resultados or not resultados[campo]:
                match = re.match(patron, linea_strip, re.IGNORECASE)
                if match:
                    resultados[campo] = match.group(1).strip()
                    break

    # Rellenar campos faltantes con cadena vacía
    for campo in patrones.keys():
        resultados.setdefault(campo, "")

    return resultados


def formatear_respuesta_car_supervisor(caso: dict) -> str:
    """Genera una vista enriquecida para el Supervisor cuando lee la respuesta de CAR."""
    datos = parsear_formato_car(caso["contenido"])
    
    if datos:
        texto = (
            f"🛠️ <b>SOLUCIÓN DE CUADRILLA #{caso['id']}</b>\n"
            f"📅 <b>Registro:</b> <code>{caso['fecha_creacion']}</code>\n"
            f"👷 <b>Enviado por:</b> {caso['remitente_nombre']}\n"
            f"────────────────────────\n"
            f"📋 <b>VenApp:</b> <code>{datos.get('venapp') or 'N/A'}</code>\n"
            f"🔢 <b>Reclamo:</b> <code>{datos.get('reclamo') or 'N/A'}</code>\n"
            f"🚛 <b>Unidad MPPEE:</b> {datos.get('unidad_mppee') or 'N/A'}\n"
            f"📍 <b>Dirección:</b> {datos.get('direccion') or 'N/A'}\n"
            f"👥 <b>Cuadrilla:</b> Op: {datos.get('operario') or 'N/A'} | Ch: {datos.get('chofer') or 'N/A'}\n"
            f"🏷️ <b>UBT:</b> {datos.get('ubt') or 'N/A'}\n"
            f"🔧 <b>Solución:</b>\n{datos.get('solucion') or 'N/A'}\n"
        )
        if datos.get("observaciones"):
            texto += f"💬 <b>Observaciones:</b> {datos.get('observaciones')}\n"
        return texto
    else:
        # Texto libre si no usaron la plantilla estricta
        return (
            f"🛠️ <b>SOLUCIÓN #{caso['id']}</b>\n"
            f"📅 <b>Fecha:</b> <code>{caso['fecha_creacion']}</code>\n"
            f"👷 <b>Cuadrilla (CAR):</b> {caso['remitente_nombre']}\n"
            f"🏷️ <b>Estado anterior:</b> <i>{caso['estado']}</i>\n"
            f"🔧 <b>Detalle reportado:</b>\n{caso['contenido']}"
        )
