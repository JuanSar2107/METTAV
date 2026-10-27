"""Elección de la base de datos.

Por defecto se usa SQLite (instance/mi_proyecto.sqlite3). Si se define la
variable DATABASE_URL se usa esa base, por ejemplo PostgreSQL:

    DATABASE_URL=postgresql://usuario:clave@servidor:5432/mettav
"""

import os
from pathlib import Path


def normalizar_url(url: str) -> str:
    """Adapta las URL de PostgreSQL para usar el driver psycopg 3.

    Coolify, Heroku y otros entregan `postgres://` o `postgresql://`, que
    SQLAlchemy asociaría a psycopg2; aquí se usa psycopg (versión 3).
    """
    url = url.strip()
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


def url_base_de_datos(ruta_sqlite: Path) -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return normalizar_url(url)
    return f"sqlite:///{ruta_sqlite}"


def opciones_motor(url: str) -> dict:
    if url.startswith("sqlite"):
        return {}
    # Descarta conexiones que el servidor cerró (reinicios, inactividad).
    return {"pool_pre_ping": True, "pool_recycle": 1800}
