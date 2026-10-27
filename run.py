import os
import sys
from pathlib import Path

# Añadir la carpeta 'mi_proyecto' al path de Python para importar 'mi_app'
base_dir = Path(__file__).resolve().parent
mi_proyecto_dir = base_dir / "mi_proyecto"
if str(mi_proyecto_dir) not in sys.path:
    sys.path.insert(0, str(mi_proyecto_dir))

from dotenv import load_dotenv

# Carga las variables de `.env` (SECRET_KEY, GEMINI_API_KEY, ...) al correr en local.
load_dotenv(base_dir / ".env")

from mi_app import create_app

app = create_app()

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", os.environ.get("APP_PORT", 5000)))
    print(f"Iniciando METTAV en http://127.0.0.1:{puerto} ...")
    # El depurador de Flask permite ejecutar código: solo se escucha en este equipo.
    # Para probar desde otro dispositivo de la red usa HOST=0.0.0.0 y FLASK_DEBUG=0.
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=puerto, debug=debug)
