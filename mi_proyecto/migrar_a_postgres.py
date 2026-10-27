"""Copia todos los datos de la base SQLite de METTAV a PostgreSQL.

Uso (desde la carpeta mi_proyecto, o en la Terminal del contenedor de Coolify):

    python migrar_a_postgres.py --destino "postgresql://usuario:clave@servidor:5432/mettav"

También se puede pasar la URL en la variable DESTINO_URL en lugar de --destino.

- El origen por defecto es instance/mi_proyecto.sqlite3 (cámbialo con --origen).
- Crea las tablas en el destino si no existen y conserva los mismos IDs.
- Si el destino ya tiene datos se detiene; con --vaciar-destino los borra antes.
- No modifica la base SQLite de origen.
"""

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import Integer, create_engine, func, inspect, select, text

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mi_app.database import normalizar_url, opciones_motor  # noqa: E402
from mi_app.extensions import db  # noqa: E402
import mi_app.models  # noqa: E402,F401  (registra las tablas en db.metadata)

_ORIGEN_POR_DEFECTO = Path(__file__).resolve().parent / "instance" / "mi_proyecto.sqlite3"


def migrar(url_origen: str, url_destino: str, vaciar_destino: bool = False) -> dict[str, int]:
    """Copia cada tabla del modelo de origen a destino y devuelve las filas copiadas."""
    origen = create_engine(url_origen)
    destino = create_engine(url_destino, **opciones_motor(url_destino))
    tablas = db.metadata.sorted_tables

    db.metadata.create_all(destino)
    tablas_origen = set(inspect(origen).get_table_names())
    copiadas = {}

    with origen.connect() as lectura, destino.begin() as escritura:
        ocupadas = [
            tabla.name for tabla in tablas
            if escritura.execute(select(func.count()).select_from(tabla)).scalar()
        ]
        if ocupadas and not vaciar_destino:
            raise RuntimeError(
                "El destino ya tiene datos en: " + ", ".join(ocupadas)
                + ". Usa --vaciar-destino para reemplazarlos."
            )
        for tabla in reversed(tablas):
            escritura.execute(tabla.delete())

        for tabla in tablas:
            if tabla.name not in tablas_origen:
                copiadas[tabla.name] = 0
                continue
            # Solo las columnas que existen en el origen (una base vieja puede no tenerlas todas).
            columnas_origen = {c["name"] for c in inspect(origen).get_columns(tabla.name)}
            columnas = [c for c in tabla.columns if c.name in columnas_origen]
            filas = [dict(fila) for fila in lectura.execute(select(*columnas)).mappings()]
            if filas:
                escritura.execute(tabla.insert(), filas)
            copiadas[tabla.name] = len(filas)

        if destino.dialect.name == "postgresql":
            # Las secuencias deben continuar después del último ID copiado.
            for tabla in tablas:
                for columna in tabla.primary_key.columns:
                    if isinstance(columna.type, Integer):
                        escritura.execute(text(
                            f"SELECT setval(pg_get_serial_sequence('{tabla.name}', '{columna.name}'), "
                            f"COALESCE(MAX({columna.name}), 1), MAX({columna.name}) IS NOT NULL) "
                            f"FROM {tabla.name}"
                        ))

    origen.dispose()
    destino.dispose()
    return copiadas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--origen", default=str(_ORIGEN_POR_DEFECTO), help="Archivo SQLite de origen")
    parser.add_argument("--destino", default=os.environ.get("DESTINO_URL", ""), help="URL de PostgreSQL")
    parser.add_argument("--vaciar-destino", action="store_true", help="Borra los datos del destino antes de copiar")
    argumentos = parser.parse_args()

    ruta_origen = Path(argumentos.origen)
    if not ruta_origen.is_file():
        print(f"No existe la base de origen: {ruta_origen}")
        return 1
    if not argumentos.destino:
        print("Indica la base de destino con --destino o la variable DESTINO_URL.")
        return 1

    try:
        copiadas = migrar(f"sqlite:///{ruta_origen.as_posix()}", normalizar_url(argumentos.destino),
                          argumentos.vaciar_destino)
    except RuntimeError as error:
        print(f"No se copió nada. {error}")
        return 1

    print("Migración completada. Filas copiadas:")
    for tabla, cantidad in copiadas.items():
        print(f"  {tabla}: {cantidad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
