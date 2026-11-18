import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import (
    DB_PATH,
    ESTADO_PENDIENTE_CAT,
    ESTADO_LEIDO_CAT,
    ESTADO_RESPUESTA_CAR,
    ESTADO_LEIDO_SUPERVISOR
)


@contextmanager
def get_db_connection():
    """Context manager para manejar conexiones seguras a SQLite en entornos multihilo."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Inicializa las tablas de la base de datos si no existen."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Tabla de Usuarios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                rol TEXT DEFAULT NULL,
                municipio TEXT DEFAULT 'Maracaibo',
                fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabla de Casos / Reportes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS casos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                remitente_id INTEGER NOT NULL,
                remitente_nombre TEXT,
                contenido TEXT NOT NULL,
                estado TEXT NOT NULL,
                foto_id TEXT DEFAULT NULL,
                municipio TEXT DEFAULT 'Maracaibo',
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                fecha_leido DATETIME DEFAULT NULL,
                FOREIGN KEY (remitente_id) REFERENCES usuarios (user_id)
            )
        """)

        # Migración automática si la columna foto_id o municipio no existían
        cursor.execute("PRAGMA table_info(casos)")
        columnas_casos = [col["name"] for col in cursor.fetchall()]
        if "foto_id" not in columnas_casos:
            cursor.execute("ALTER TABLE casos ADD COLUMN foto_id TEXT DEFAULT NULL")
        if "municipio" not in columnas_casos:
            cursor.execute("ALTER TABLE casos ADD COLUMN municipio TEXT DEFAULT 'Maracaibo'")

        cursor.execute("PRAGMA table_info(usuarios)")
        columnas_usuarios = [col["name"] for col in cursor.fetchall()]
        if "municipio" not in columnas_usuarios:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN municipio TEXT DEFAULT 'Maracaibo'")


def registrar_usuario_si_no_existe(user_id: int, username: Optional[str], first_name: Optional[str]):
    """Registra al usuario nuevo sin rol si no existe en la base de datos."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, rol FROM usuarios WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO usuarios (user_id, username, first_name, rol, fecha_registro, fecha_actualizacion)
                VALUES (?, ?, ?, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (user_id, username, first_name))
        else:
            # Mantener actualizados username y first_name
            cursor.execute("""
                UPDATE usuarios 
                SET username = ?, first_name = ?
                WHERE user_id = ?
            """, (username, first_name, user_id))


def asignar_rol(user_id: int, nuevo_rol: str, municipio: str = "Maracaibo", username: Optional[str] = None, first_name: Optional[str] = None) -> bool:
    """Asigna o actualiza el rol y municipio de un usuario."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM usuarios WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE usuarios 
                SET rol = ?, municipio = ?, username = coalesce(?, username), first_name = coalesce(?, first_name), fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (nuevo_rol, municipio, username, first_name, user_id))
        else:
            cursor.execute("""
                INSERT INTO usuarios (user_id, username, first_name, rol, municipio, fecha_registro, fecha_actualizacion)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (user_id, username, first_name, nuevo_rol, municipio))
        return True


def obtener_usuario(user_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene el registro completo de un usuario."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def obtener_rol(user_id: int) -> Optional[str]:
    """Retorna el rol del usuario o None si no tiene rol o no existe."""
    user = obtener_usuario(user_id)
    return user.get("rol") if user else None


def obtener_municipio_usuario(user_id: int) -> str:
    """Retorna el municipio del usuario o 'Maracaibo' por defecto."""
    user = obtener_usuario(user_id)
    return user.get("municipio") or "Maracaibo" if user else "Maracaibo"


def obtener_usuarios_por_rol(rol: str, municipio: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retorna todos los usuarios que tienen un rol específico, opcionalmente filtrados por municipio."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if municipio:
            cursor.execute("""
                SELECT * FROM usuarios 
                WHERE rol = ? AND (municipio = ? OR municipio = 'Todos')
            """, (rol, municipio))
        else:
            cursor.execute("SELECT * FROM usuarios WHERE rol = ?", (rol,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def crear_caso(tipo: str, remitente_id: int, remitente_nombre: str, contenido: str, estado: str, foto_id: Optional[str] = None, municipio: str = "Maracaibo") -> int:
    """Crea un nuevo caso en la base de datos con su municipio y retorna su ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO casos (tipo, remitente_id, remitente_nombre, contenido, estado, foto_id, municipio, fecha_creacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (tipo, remitente_id, remitente_nombre, contenido, estado, foto_id, municipio))
        return cursor.lastrowid


def obtener_caso_por_id(caso_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene un caso específico por su ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM casos WHERE id = ?", (caso_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def obtener_ultimos_casos_por_tipo(tipo: str, limite: int = 5, municipio: Optional[str] = None) -> List[Dict[str, Any]]:
    """Obtiene los últimos N casos de un tipo específico (leídos o no), opcionalmente filtrados por municipio."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if municipio:
            cursor.execute("""
                SELECT * FROM casos 
                WHERE tipo = ? AND municipio = ?
                ORDER BY id DESC 
                LIMIT ?
            """, (tipo, municipio, limite))
        else:
            cursor.execute("""
                SELECT * FROM casos 
                WHERE tipo = ? 
                ORDER BY id DESC 
                LIMIT ?
            """, (tipo, limite))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def buscar_casos_por_texto(termino: str, limite: int = 5) -> List[Dict[str, Any]]:
    """Busca casos por coincidencia en el texto (ej. número de VenApp, reclamo, dirección)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        patron = f"%{termino}%"
        cursor.execute("""
            SELECT * FROM casos 
            WHERE contenido LIKE ? 
            ORDER BY id DESC 
            LIMIT ?
        """, (patron, limite))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def obtener_casos_por_estado(estado: str, municipio: Optional[str] = None) -> List[Dict[str, Any]]:
    """Obtiene los casos filtrados por su estado y opcionalmente por municipio."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if municipio:
            cursor.execute("""
                SELECT * FROM casos 
                WHERE estado = ? AND municipio = ?
                ORDER BY id ASC
            """, (estado, municipio))
        else:
            cursor.execute("""
                SELECT * FROM casos 
                WHERE estado = ? 
                ORDER BY id ASC
            """, (estado,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def marcar_casos_como_leidos(ids_casos: List[int], nuevo_estado: str):
    """Actualiza una lista de casos a un nuevo estado y registra la fecha de lectura."""
    if not ids_casos:
        return
    with get_db_connection() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in ids_casos)
        cursor.execute(f"""
            UPDATE casos 
            SET estado = ?, fecha_leido = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
        """, [nuevo_estado] + ids_casos)
