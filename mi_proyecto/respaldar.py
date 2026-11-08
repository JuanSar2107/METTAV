"""Crea o restaura copias de seguridad de METTAV.

Desde la carpeta mi_proyecto (o la Terminal del contenedor en Coolify):

    python respaldar.py                         crea una copia ahora
    python respaldar.py --cada-horas 24         crea una copia cada 24 horas
    python respaldar.py --restaurar copia.zip --confirmar

Restaurar REEMPLAZA todos los datos actuales: antes guarda una copia de cómo
estaba todo. Hazlo con la aplicación detenida. Las copias quedan en
instance/respaldos (se conservan las 14 últimas; cámbialo con RESPALDOS_CONSERVAR).
"""

import argparse
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from mi_app.database import url_base_de_datos  # noqa: E402
from mi_app.respaldos import PREFIJO_PREVIO, carpetas_de_archivos, crear_respaldo, restaurar_respaldo  # noqa: E402

_INSTANCIA = RAIZ / "instance"
_CARPETAS = carpetas_de_archivos(_INSTANCIA / "documentos", RAIZ / "mi_app" / "static" / "images")
_RESPALDOS = _INSTANCIA / "respaldos"


def _crear(url: str) -> None:
    print(f"Copia creada: {crear_respaldo(url, _RESPALDOS, _CARPETAS)}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cada-horas", type=float, help="Repite la copia cada tantas horas")
    parser.add_argument("--restaurar", help="Archivo .zip de la copia que se va a restaurar")
    parser.add_argument("--confirmar", action="store_true", help="Confirma que se reemplazarán los datos actuales")
    argumentos = parser.parse_args()
    url = url_base_de_datos(_INSTANCIA / "mi_proyecto.sqlite3")

    if argumentos.restaurar:
        archivo = Path(argumentos.restaurar)
        if not archivo.is_file():
            print(f"No existe el archivo: {archivo}")
            return 1
        if not argumentos.confirmar:
            print("Esto reemplaza TODOS los datos actuales. Repite el comando con --confirmar.")
            return 1
        previa = crear_respaldo(url, _RESPALDOS, _CARPETAS, prefijo=PREFIJO_PREVIO)
        print(f"Estado anterior guardado en: {previa}")
        try:
            copiadas = restaurar_respaldo(archivo, url, _CARPETAS)
        except ValueError as error:
            print(f"No se restauró nada. {error}")
            return 1
        print(f"Restauración completada: {sum(copiadas.values())} filas en {len(copiadas)} tablas.")
        return 0

    if not argumentos.cada_horas:
        _crear(url)
        return 0
    if argumentos.cada_horas <= 0:
        print("--cada-horas debe ser mayor que cero.")
        return 1
    while True:
        try:
            _crear(url)
        except Exception as error:  # un fallo puntual no debe detener las copias siguientes
            print(f"No se pudo crear la copia: {error}", flush=True)
        time.sleep(argumentos.cada_horas * 3600)


if __name__ == "__main__":
    sys.exit(main())
