import os
from mi_app import create_app

app = create_app()

if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", os.environ.get("APP_PORT", 5000)))
    print(f"Iniciando METTAV en http://127.0.0.1:{puerto} ...")
    app.run(host="0.0.0.0", port=puerto, debug=True)
