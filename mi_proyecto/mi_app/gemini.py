"""Cliente mínimo para la API de Google Gemini.

Usa directamente el endpoint REST `generateContent` con la librería estándar,
así no se agrega ningún SDK a la imagen Docker.

Variables de entorno:
    GEMINI_API_KEY -> clave de Google AI Studio (https://aistudio.google.com/apikey)
    GEMINI_MODEL   -> modelo a usar (por defecto: gemini-3.5-flash)
"""

import json
import os
import urllib.error
import urllib.request

MODELO_POR_DEFECTO = "gemini-3.5-flash"
_URL_API = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
_TIEMPO_MAXIMO = 45


class GeminiError(Exception):
    """Error al consultar Gemini; el mensaje ya es apto para mostrar al usuario."""


def clave_configurada() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def consultar_gemini(instrucciones: str, mensajes: list[dict]) -> str:
    """Envía la conversación a Gemini y devuelve el texto de la respuesta.

    `mensajes` es una lista de {"rol": "usuario" | "asistente", "texto": str}
    en orden cronológico; el último debe ser la pregunta del usuario.
    """
    clave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not clave:
        raise GeminiError("El asistente no está configurado: falta GEMINI_API_KEY.")
    modelo = os.environ.get("GEMINI_MODEL", "").strip() or MODELO_POR_DEFECTO

    cuerpo = {
        "system_instruction": {"parts": [{"text": instrucciones}]},
        "contents": [
            {
                "role": "model" if mensaje["rol"] == "asistente" else "user",
                "parts": [{"text": mensaje["texto"]}],
            }
            for mensaje in mensajes
        ],
        "generationConfig": {"temperature": 0.3},
    }
    peticion = urllib.request.Request(
        _URL_API.format(modelo=modelo),
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": clave},
        method="POST",
    )

    try:
        with urllib.request.urlopen(peticion, timeout=_TIEMPO_MAXIMO) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise GeminiError(_mensaje_error_http(error)) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise GeminiError("No se pudo conectar con Gemini. Revisa la conexión a internet.") from error
    except json.JSONDecodeError as error:
        raise GeminiError("Gemini devolvió una respuesta no válida.") from error

    candidatos = datos.get("candidates") or []
    partes = ((candidatos[0].get("content") or {}).get("parts") or []) if candidatos else []
    texto = "".join(parte.get("text", "") for parte in partes if not parte.get("thought")).strip()
    if not texto:
        raise GeminiError("Gemini no devolvió una respuesta. Intenta reformular la pregunta.")
    return texto


def _mensaje_error_http(error: urllib.error.HTTPError) -> str:
    try:
        detalle = json.loads(error.read().decode("utf-8")).get("error", {}).get("message", "")
    except (ValueError, AttributeError):
        detalle = ""
    if error.code in (400, 401, 403) and "API key" in detalle:
        return "La clave GEMINI_API_KEY no es válida."
    if error.code == 404:
        return "El modelo configurado en GEMINI_MODEL no existe o no está disponible."
    if error.code == 429:
        return "Se alcanzó el límite de uso de Gemini. Espera un momento e inténtalo de nuevo."
    return f"Gemini respondió con un error ({error.code}). {detalle}".strip()
