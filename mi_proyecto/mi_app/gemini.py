"""Cliente mínimo para la API de Google Gemini.

Usa directamente el endpoint REST `generateContent` con la librería estándar,
así no se agrega ningún SDK a la imagen Docker.

Variables de entorno:
    GEMINI_API_KEY -> clave de Google AI Studio (https://aistudio.google.com/apikey)
    GEMINI_MODEL   -> modelo a usar (por defecto: gemini-3.5-flash)
    GEMINI_TIMEOUT -> segundos máximos de espera por una respuesta (por defecto: 15; si se pasa, se prueba el siguiente modelo)
    GEMINI_MODELOS_RESPALDO -> modelos a probar, en orden, si el principal está saturado
                     (separados por comas; por defecto: gemini-3.5-flash-lite, gemini-3-flash;
                     si ninguno existe, se usa uno de los que Google ofrezca para la clave).
                     Escribe "ninguno" para no usar respaldo.
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
_URL_STREAM = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:streamGenerateContent?alt=sse"
MODELOS_RESPALDO_POR_DEFECTO = ("gemini-3.5-flash-lite", "gemini-3-flash")
_TIEMPO_POR_DEFECTO = 15
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
    texto = os.environ.get("GEMINI_MODELOS_RESPALDO")
    if texto is None or not texto.strip():
        respaldo = list(MODELOS_RESPALDO_POR_DEFECTO)
    elif texto.strip().lower() == "ninguno":
        respaldo = []
    else:
        respaldo = [m.strip() for m in texto.split(",") if m.strip()]
    return list(dict.fromkeys([principal, *respaldo]))


# Modelos que Google dijo que no existen (404) y lista de modelos disponibles para la
# clave, consultada a Google una vez por hora como máximo. Así, si Google retira un
# modelo, el asistente sigue funcionando con otro sin tener que tocar la configuración.
_no_existen: set[str] = set()
_disponibles_cache: dict = {"hasta": 0.0, "modelos": []}
_URL_MODELOS = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000"
_EXCLUIR = ("image", "tts", "audio", "live", "embedding", "robotics", "computer-use")


def _version(nombre: str) -> float:
    try:
        return float(nombre.split("-")[1])
    except (IndexError, ValueError):
        return 0.0


def _modelos_disponibles(clave: str) -> list[str]:
    """Modelos "flash" de texto que la clave puede usar, del más conveniente al menos."""
    if time.time() < _disponibles_cache["hasta"]:
        return _disponibles_cache["modelos"]
    modelos = []
    try:
        peticion = urllib.request.Request(_URL_MODELOS, headers={"x-goog-api-key": clave})
        with urllib.request.urlopen(peticion, timeout=_tiempo_maximo()) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
        for modelo in datos.get("models") or []:
            nombre = str(modelo.get("name", "")).removeprefix("models/")
            if (
                nombre.startswith("gemini-") and "flash" in nombre
                and "generateContent" in (modelo.get("supportedGenerationMethods") or [])
                and not any(palabra in nombre for palabra in _EXCLUIR)
            ):
                modelos.append(nombre)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, AttributeError) as error:
        _log.warning("No se pudo consultar la lista de modelos de Gemini: %r", error)
    # Primero los estables, luego los "lite", y de la versión más nueva a la más vieja.
    modelos.sort(key=lambda n: ("preview" in n or "exp" in n, "lite" in n, -_version(n), n))
    _disponibles_cache.update(hasta=time.time() + 3600, modelos=modelos)
    if modelos:
        _log.info("Modelos de Gemini disponibles: %s", ", ".join(modelos))
    return modelos


def _tiempo_maximo() -> int:
    try:
        return min(max(int(os.environ.get("GEMINI_TIMEOUT") or _TIEMPO_POR_DEFECTO), 5), 240)
    except ValueError:
        return _TIEMPO_POR_DEFECTO


class _ModeloNoUsable(Exception):
    """El modelo no existe (404) o agotó su cuota (429): conviene probar otro."""

    def __init__(self, codigo: int, mensaje: str):
        super().__init__(codigo)
        self.codigo = codigo
        self.mensaje = mensaje


class _Lento(Exception):
    """El modelo no respondió a tiempo."""


def _cuerpo_para(modelo: str, cuerpo: dict) -> bytes:
    """Pide poco "razonamiento" interno: las preguntas del inventario son simples y así
    las respuestas llegan en pocos segundos en vez de medio minuto."""
    config = {"temperature": 0.3, "maxOutputTokens": 2048}
    if modelo.startswith("gemini-2.5"):
        config["thinkingConfig"] = {"thinkingBudget": 0}
    elif modelo.startswith("gemini-"):
        config["thinkingConfig"] = {"thinkingLevel": "low"}
    return json.dumps({**cuerpo, "generationConfig": config}).encode("utf-8")


class GeminiError(ErrorValidacion):
    """Error al consultar Gemini; el mensaje ya es apto para mostrar al usuario."""


def clave_configurada() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def _cuerpo_base(instrucciones: str, mensajes: list[dict]) -> dict:
    return {
        "system_instruction": {"parts": [{"text": instrucciones}]},
        "contents": [
            {
                "role": "model" if mensaje["rol"] == "asistente" else "user",
                "parts": [{"text": mensaje["texto"]}],
            }
            for mensaje in mensajes
        ],
    }


def _clave() -> str:
    clave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not clave:
        raise GeminiError("El asistente no está configurado: falta GEMINI_API_KEY.")
    return clave


def _con_respaldo(intentar, clave: str):
    """Llama a `intentar(modelo)` con el modelo principal y, si falla, con los de respaldo.

    Si Google responde que el modelo está saturado (503 y similares), se reintenta un par
    de veces y luego se prueba el siguiente. Si un modelo no existe (404), llegó a su límite
    de uso (429) o tarda demasiado, se pasa directo al siguiente.
    """
    ultimo_error = None
    modelos = [m for m in _modelos() if m not in _no_existen]
    buscados = False
    if not modelos:
        modelos, buscados = list(_modelos_disponibles(clave)), True
    indice = 0
    while True:
        if indice >= len(modelos):
            if buscados or not _no_existen:
                break
            # Algún modelo ya no existe: antes de rendirse se prueban los que Google
            # ofrece para esta clave.
            buscados = True
            modelos += [m for m in _modelos_disponibles(clave) if m not in modelos and m not in _no_existen]
            if indice >= len(modelos):
                break
        modelo = modelos[indice]
        indice += 1
        for intento, espera in enumerate((0.0, *_ESPERAS_REINTENTO)):
            if espera:
                time.sleep(espera)
            try:
                return intentar(modelo)
            except _Saturado as saturado:
                _log.warning("Gemini (%s) respondió %s en el intento %s.", modelo, saturado.codigo, intento + 1)
            except _Lento:
                _log.warning("Gemini (%s) no respondió en %s s; se prueba el siguiente.", modelo, _tiempo_maximo())
                ultimo_error = ultimo_error or "Gemini tardó demasiado en responder. Inténtalo de nuevo en un momento."
                break
            except _ModeloNoUsable as error:
                if error.codigo == 404:
                    _no_existen.add(modelo)
                _log.warning("Gemini (%s) no se pudo usar (%s); se prueba el siguiente.", modelo, error.codigo)
                ultimo_error = ultimo_error or error.mensaje
                break
    if ultimo_error:
        raise GeminiError(ultimo_error)
    raise GeminiError("Gemini está saturado en este momento. Inténtalo de nuevo en unos minutos.")


def consultar_gemini(instrucciones: str, mensajes: list[dict]) -> str:
    """Envía la conversación a Gemini y devuelve el texto completo de la respuesta.

    `mensajes` es una lista de {"rol": "usuario" | "asistente", "texto": str}
    en orden cronológico; el último debe ser la pregunta del usuario.
    """
    clave = _clave()
    cuerpo = _cuerpo_base(instrucciones, mensajes)
    return _con_respaldo(lambda modelo: _consultar_modelo(modelo, clave, _cuerpo_para(modelo, cuerpo)), clave)


def consultar_gemini_por_partes(instrucciones: str, mensajes: list[dict]):
    """Igual que `consultar_gemini`, pero devuelve un iterador con la respuesta a trozos,
    a medida que Gemini la escribe (como en ChatGPT).

    Se espera al primer trozo antes de devolver el iterador: así los errores de conexión,
    saturación o modelo inexistente se lanzan aquí como GeminiError y se prueban los modelos
    de respaldo, antes de empezar a mostrar la respuesta.
    """
    clave = _clave()
    cuerpo = _cuerpo_base(instrucciones, mensajes)

    def intentar(modelo):
        respuesta = _abrir(_URL_STREAM.format(modelo=modelo), clave, _cuerpo_para(modelo, cuerpo), modelo)
        trozos = _leer_eventos(respuesta)
        try:
            primero = next(trozos)
        except StopIteration:
            respuesta.close()
            raise GeminiError("Gemini no devolvió una respuesta. Intenta reformular la pregunta.") from None
        except (TimeoutError, OSError) as error:
            respuesta.close()
            raise _Lento() from error
        return _continuar(primero, trozos, respuesta)

    return _con_respaldo(intentar, clave)


def _continuar(primero: str, trozos, respuesta):
    try:
        yield primero
        yield from trozos
    except (TimeoutError, OSError, ValueError) as error:
        _log.warning("Se cortó la respuesta de Gemini: %r", error)
        yield "\n\n(La respuesta se cortó. Inténtalo de nuevo.)"
    finally:
        respuesta.close()


def _leer_eventos(respuesta):
    """Lee los eventos `data: {...}` que envía Gemini y devuelve solo el texto visible."""
    for linea in respuesta:
        linea = linea.decode("utf-8").strip()
        if not linea.startswith("data:"):
            continue
        datos = json.loads(linea[5:])
        candidatos = datos.get("candidates") or []
        partes = ((candidatos[0].get("content") or {}).get("parts") or []) if candidatos else []
        texto = "".join(parte.get("text", "") for parte in partes if not parte.get("thought"))
        if texto:
            yield texto


def _abrir(url: str, clave: str, datos_json: bytes, modelo: str):
    peticion = urllib.request.Request(
        url,
        data=datos_json,
        headers={"Content-Type": "application/json", "x-goog-api-key": clave},
        method="POST",
    )
    try:
        return urllib.request.urlopen(peticion, timeout=_tiempo_maximo())
    except urllib.error.HTTPError as error:
        if error.code in _CODIGOS_TEMPORALES:
            raise _Saturado(error.code) from error
        if error.code in (404, 429):
            raise _ModeloNoUsable(error.code, _mensaje_error_http(error)) from error
        raise GeminiError(_mensaje_error_http(error)) from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        # Se distingue "tardó demasiado" de "no hay conexión", y el motivo exacto va al log.
        motivo = getattr(error, "reason", error)
        if isinstance(motivo, TimeoutError) or isinstance(error, TimeoutError):
            raise _Lento() from error
        _log.warning("No se pudo conectar con Gemini (modelo %s): %r", modelo, motivo)
        raise GeminiError("No se pudo conectar con Gemini. Revisa la conexión a internet.") from error


def _consultar_modelo(modelo: str, clave: str, datos_json: bytes) -> str:
    try:
        with _abrir(_URL_API.format(modelo=modelo), clave, datos_json, modelo) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except TimeoutError as error:
        raise _Lento() from error
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
