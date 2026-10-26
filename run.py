import os
import sys
from pathlib import Path

# Añadir la carpeta 'mi_proyecto' al path de Python para importar 'mi_app'
base_dir = Path(__file__).resolve().parent
mi_proyecto_dir = base_dir / "mi_proyecto"
if str(mi_proyecto_dir) not in sys.path:
    sys.path.insert(0, str(mi_proyecto_dir))

from mi_app import create_app

app = create_app()

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", os.environ.get("APP_PORT", 5000)))
    print(f"Iniciando METTAV en http://127.0.0.1:{puerto} ...")
    app.run(host="0.0.0.0", port=puerto, debug=True)
