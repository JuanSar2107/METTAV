from mi_app import create_app
import os

app = create_app()

if __name__ == '__main__':
    app.run(
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
    )
