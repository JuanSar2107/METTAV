"""Cliente mínimo para la API de Google Gemini.

Usa directamente el endpoint REST `generateContent` con la librería estándar,
así no se agrega ningún SDK a la imagen Docker.

Variables de entorno:
    GEMINI_API_KEY -> clave de Google AI Studio (https://aistudio.google.com/apikey)
    GEMINI_MODEL   -> modelo a usar (por defecto: gemini-3.5-flash)
    GEMINI_TIMEOUT -> segundos máximos de espera por una respuesta (por defecto: 60)
    GEMINI_MODELOS_RESPALDO -> modelos a probar, en orden, si el principal está saturado
                     (separados por comas; por defecto ninguno)
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request

from mi_app.validacion import ErrorValidacion

_log = logging.getLogger(__name__)

MODELO_POR_DEFECTO = "gemini-3.5-flash"
_URL_API = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
_TIEMPO_POR_DEFECTO = 60
# Respuestas de Google que indican saturación pasajera: vale la pena reintentar.
_CODIGOS_TEMPORALES = {500, 502, 503, 504}
_ESPERAS_REINTENTO = (1.5, 4.0)


class _Saturado(Exception):
    """El modelo respondió que está saturado o no disponible por ahora."""

    def __init__(self, codigo: int):
        super().__init__(codigo)
        self.codigo = codigo


def _modelos() -> list[str]:
    principal = os.environ.get("GEMINI_MODEL", "").strip() or MODELO_POR_DEFECTO
    respaldo = [m.strip() for m in (os.environ.get("GEMINI_MODELOS_RESPALDO") or "").split(",") if m.strip()]
    return list(dict.fromkeys([principal, *respaldo]))


def _tiempo_maximo() -> int:
    try:
        return min(max(int(os.environ.get("GEMINI_TIMEOUT") or _TIEMPO_POR_DEFECTO), 10), 240)
    except ValueError:
        return _TIEMPO_POR_DEFECTO


class GeminiError(ErrorValidacion):
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
    datos_json = json.dumps(cuerpo).encode("utf-8")

    # Si Google responde que el modelo está saturado (503 y similares), se reintenta un par
    # de veces y luego se prueba con los modelos de respaldo, si hay.
    for modelo in _modelos():
        for intento, espera in enumerate((0.0, *_ESPERAS_REINTENTO)):
            if espera:
                time.sleep(espera)
            try:
                return _consultar_modelo(modelo, clave, datos_json)
            except _Saturado as saturado:
                _log.warning("Gemini (%s) respondió %s en el intento %s.", modelo, saturado.codigo, intento + 1)
    raise GeminiError("Gemini está saturado en este momento. Inténtalo de nuevo en unos minutos.")


def _consultar_modelo(modelo: str, clave: str, datos_json: bytes) -> str:
    peticion = urllib.request.Request(
        _URL_API.format(modelo=modelo),
        data=datos_json,
        headers={"Content-Type": "application/json", "x-goog-api-key": clave},
        method="POST",
    )

    try:
        with urllib.request.urlopen(peticion, timeout=_tiempo_maximo()) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code in _CODIGOS_TEMPORALES:
            raise _Saturado(error.code) from error
        raise GeminiError(_mensaje_error_http(error)) from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        # Se distingue "tardó demasiado" de "no hay conexión", y el motivo exacto va al log.
        motivo = getattr(error, "reason", error)
        if isinstance(motivo, TimeoutError) or isinstance(error, TimeoutError):
            _log.warning("Gemini no respondió en %s s (modelo %s).", _tiempo_maximo(), modelo)
            raise GeminiError(
                "Gemini tardó demasiado en responder. Inténtalo de nuevo en un momento."
            ) from error
        _log.warning("No se pudo conectar con Gemini (modelo %s): %r", modelo, motivo)
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
    # El detalle de Google puede incluir datos del proyecto: solo va al log.
    _log.warning("Gemini respondió %s: %s", error.code, detalle)
    return f"Gemini respondió con un error ({error.code}). Inténtalo más tarde."
