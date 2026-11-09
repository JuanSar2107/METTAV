"""Códigos de un solo uso (TOTP, RFC 6238) para la verificación en dos pasos.

Compatible con Google Authenticator, Microsoft Authenticator, Authy, etc.
Solo usa la biblioteca estándar.
"""

import base64
import hashlib
import hmac
import os
import struct
import time
from urllib.parse import quote

PASO_SEGUNDOS = 30
DIGITOS = 6


def generar_secreto() -> str:
    return base64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")


def _codigo(secreto: str, paso: int) -> str:
    relleno = "=" * (-len(secreto) % 8)
    clave = base64.b32decode(secreto.upper() + relleno)
    resumen = hmac.new(clave, struct.pack(">Q", paso), hashlib.sha1).digest()
    desplazamiento = resumen[-1] & 0x0F
    valor = struct.unpack(">I", resumen[desplazamiento:desplazamiento + 4])[0] & 0x7FFFFFFF
    return str(valor % 10**DIGITOS).zfill(DIGITOS)


def verificar(secreto: str, codigo, ultimo_paso: int | None = None, ahora: float | None = None) -> int | None:
    """Devuelve el paso del código si es válido (±1 paso de tolerancia) y no se usó antes.

    Quien llama debe guardar el paso devuelto como `ultimo_paso` para que el mismo
    código no sirva dos veces. Devuelve None si el código es inválido o repetido.
    """
    if not isinstance(codigo, str):
        return None
    codigo = codigo.replace(" ", "")
    if len(codigo) != DIGITOS or not codigo.isdigit():
        return None
    actual = int((time.time() if ahora is None else ahora) // PASO_SEGUNDOS)
    for paso in (actual, actual - 1, actual + 1):
        if ultimo_paso is not None and paso <= ultimo_paso:
            continue
        if hmac.compare_digest(_codigo(secreto, paso), codigo):
            return paso
    return None


def uri_aprovisionamiento(secreto: str, usuario: str, emisor: str = "METTAV") -> str:
    etiqueta = quote(f"{emisor}:{usuario}")
    return f"otpauth://totp/{etiqueta}?secret={secreto}&issuer={quote(emisor)}&digits={DIGITOS}&period={PASO_SEGUNDOS}"
