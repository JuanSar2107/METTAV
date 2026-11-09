"""Copias de seguridad: un .zip con la base de datos, los documentos y las imágenes.

La base se guarda siempre como un archivo SQLite, también si la app usa
PostgreSQL, de modo que la misma copia sirve para restaurar en cualquiera de
las dos. Se usa desde el botón de Reportes y desde respaldar.py.
"""

import os
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

from flask import current_app

from mi_app.validacion import ErrorValidacion

_HORA_COLOMBIA = timezone(timedelta(hours=-5))
_ARCHIVO_BD = "base_de_datos.sqlite3"
PREFIJO = "mettav-respaldo"
PREFIJO_PREVIO = "mettav-antes-de-restaurar"
CONSERVAR_POR_DEFECTO = 14


def _conservar() -> int:
    try:
        return max(1, int(os.environ.get("RESPALDOS_CONSERVAR", CONSERVAR_POR_DEFECTO)))
    except ValueError:
        return CONSERVAR_POR_DEFECTO


def _purgar(carpeta: Path, conservar: int) -> None:
    """Borra las copias automáticas más antiguas; nunca las previas a una restauración."""
    copias = sorted(carpeta.glob(f"{PREFIJO}-*.zip"), key=lambda ruta: ruta.name, reverse=True)
    for vieja in copias[conservar:]:
        vieja.unlink(missing_ok=True)


def crear_respaldo(
    url_bd: str,
    carpeta: Path,
    carpetas_archivos: dict[str, Path],
    prefijo: str = PREFIJO,
    conservar: int | None = None,
) -> Path:
    """Crea la copia en `carpeta` y devuelve su ruta.

    `carpetas_archivos` asocia el nombre dentro del zip con la carpeta real. El
    zip se escribe aparte y se renombra al final: nunca queda una copia a medias.
    """
    from migrar_a_postgres import migrar

    carpeta.mkdir(parents=True, exist_ok=True)
    marca = datetime.now(_HORA_COLOMBIA).strftime("%Y-%m-%d-%H%M%S")
    destino = carpeta / f"{prefijo}-{marca}.zip"
    parcial = carpeta / f".{destino.name}.parcial"

    with tempfile.TemporaryDirectory() as temporal:
        copia_bd = Path(temporal) / _ARCHIVO_BD
        migrar(url_bd, f"sqlite:///{copia_bd.as_posix()}")
        with zipfile.ZipFile(parcial, "w", zipfile.ZIP_DEFLATED) as archivo:
            archivo.write(copia_bd, _ARCHIVO_BD)
            for nombre, origen in carpetas_archivos.items():
                if not origen.is_dir():
                    continue
                for ruta in sorted(origen.rglob("*")):
                    if ruta.is_file():
                        archivo.write(ruta, f"{nombre}/{ruta.relative_to(origen).as_posix()}")
    parcial.replace(destino)
    _purgar(carpeta, _conservar() if conservar is None else conservar)
    return destino


def restaurar_respaldo(zip_origen: Path, url_bd: str, carpetas_archivos: dict[str, Path]) -> dict[str, int]:
    """Reemplaza la base por la de la copia y repone sus archivos.

    Solo extrae lo que corresponde a las carpetas conocidas, sin salirse de ellas.
    """
    from migrar_a_postgres import migrar

    with zipfile.ZipFile(zip_origen) as archivo:
        if _ARCHIVO_BD not in archivo.namelist():
            raise ErrorValidacion("El archivo no es una copia de seguridad de METTAV.")
        with tempfile.TemporaryDirectory() as temporal:
            copia_bd = Path(temporal) / _ARCHIVO_BD
            copia_bd.write_bytes(archivo.read(_ARCHIVO_BD))
            copiadas = migrar(f"sqlite:///{copia_bd.as_posix()}", url_bd, vaciar_destino=True)

        for info in archivo.infolist():
            partes = PurePosixPath(info.filename).parts
            if info.is_dir() or len(partes) < 2 or ".." in partes or "\\" in info.filename:
                continue
            carpeta = carpetas_archivos.get(partes[0])
            if carpeta is None:
                continue
            raiz = carpeta.resolve()
            salida = raiz.joinpath(*partes[1:]).resolve()
            if not salida.is_relative_to(raiz):
                continue
            salida.parent.mkdir(parents=True, exist_ok=True)
            salida.write_bytes(archivo.read(info))
    return copiadas


def carpetas_de_archivos(documentos: Path, imagenes: Path) -> dict[str, Path]:
    return {
        "documentos": documentos,
        "imagenes_perfiles": imagenes / "profiles",
        "imagenes_inventario": imagenes / "inventory",
    }


def crear_respaldo_de_la_app() -> Path:
    """Copia de la app en ejecución, con las carpetas de su configuración."""
    imagenes = Path(current_app.static_folder) / "images"
    return crear_respaldo(
        current_app.config["SQLALCHEMY_DATABASE_URI"],
        Path(current_app.config["RESPALDOS_FOLDER"]),
        carpetas_de_archivos(Path(current_app.config["DOCUMENTOS_FOLDER"]), imagenes),
    )
