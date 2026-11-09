"""Medidas de seguridad compartidas por toda la aplicación.

- Clave secreta: nunca usa un valor por defecto conocido.
- Autenticación con JWT en cookies HttpOnly:
    * token de acceso (JWT, ~15 min) que identifica al usuario en cada petición;
    * token de refresco (JWT, rotativo) cuyo `jti` vigente se guarda en la BD, por
      lo que el servidor puede revocar la sesión (logout, cambio de contraseña),
      cerrar por inactividad / duración máxima y detectar tokens robados y
      reutilizados (se revoca toda la sesión);
    * "sello" de la contraseña dentro de ambos tokens: cambiarla invalida los demás.
- CSRF: comprueba el origen y exige la cabecera X-CSRF-Token en las peticiones que
  modifican datos con sesión iniciada.
- Cabeceras de seguridad (CSP, anti-clickjacking, nosniff, HSTS).
- Límite de intentos (en la BD, sobrevive a reinicios y varios procesos).
- Política de contraseñas y bitácora de accesos.
"""

import hashlib
import hmac
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import jwt
from flask import Flask, current_app, g, jsonify, request
from sqlalchemy import delete, insert, select
from werkzeug.middleware.proxy_fix import ProxyFix

from mi_app.extensions import db

# Valores de ejemplo que aparecieron en el repositorio: si alguien los deja
# configurados, se tratan como si no hubiera clave.
_CLAVES_INSEGURAS = {
    "mettav-dev-key-2026",
    "cambia-esta-clave-en-produccion",
    "genera-aqui-una-clave-larga-y-aleatoria",
}
_CONTRASENAS_DE_EJEMPLO = {"cambia-esta-clave"}
_METODOS_QUE_MODIFICAN = {"POST", "PUT", "PATCH", "DELETE"}

MIN_LARGO_CONTRASENA = 12
MAX_LARGO_CONTRASENA = 256
# Contraseñas típicas (se comparan solo las letras, sin números ni símbolos).
_CONTRASENAS_COMUNES = {
    "password", "contrasena", "contrasenia", "clave", "claveclave", "admin", "administrador",
    "administrator", "mettav", "mettavgroup", "qwerty", "qwertyuiop", "abcdefgh", "abcdefghijkl",
    "bienvenido", "bienvenida", "welcome", "letmein", "iloveyou", "cambiaestaclave",
    "inventario", "zonafranca", "colombia", "football", "monkey", "dragon",
}

COOKIE_ACCESO = "mettav_access"
COOKIE_REFRESCO = "mettav_refresh"
COOKIE_CSRF = "mettav_csrf"
_EMISOR = "mettav"
# Si dos peticiones llegan a la vez con el mismo refresco, la segunda lleva el
# token que la primera ya rotó: se tolera unos segundos.
_GRACIA_ROTACION = 20

_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob: https://images.unsplash.com",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


def resolver_clave_secreta(carpeta_instancia: Path) -> str:
    """Usa SECRET_KEY si es segura; si no, una clave aleatoria guardada en instance/.

    En Docker, instance/ es un volumen persistente, así que la clave generada
    sobrevive a los redespliegues y las sesiones no se cierran en cada uno.
    """
    clave = (os.environ.get("SECRET_KEY") or "").strip()
    if clave and clave not in _CLAVES_INSEGURAS:
        return clave

    archivo = carpeta_instancia / "secret_key"
    if archivo.exists():
        guardada = archivo.read_text(encoding="utf-8").strip()
        if guardada:
            return guardada
    nueva = secrets.token_hex(32)
    archivo.write_text(nueva, encoding="utf-8")
    try:
        archivo.chmod(0o600)
    except OSError:
        pass
    return nueva


# ---------------------------------------------------------------- contraseñas

def validar_contrasena(contrasena, usuario: str | None = None) -> str | None:
    """Devuelve el motivo por el que la contraseña no sirve, o None si es aceptable."""
    if not isinstance(contrasena, str) or not MIN_LARGO_CONTRASENA <= len(contrasena) <= MAX_LARGO_CONTRASENA:
        return f"La contraseña debe tener entre {MIN_LARGO_CONTRASENA} y {MAX_LARGO_CONTRASENA} caracteres."
    if contrasena.isdigit() or contrasena.isalpha():
        return "La contraseña debe combinar letras y números o símbolos."
    if len(set(contrasena)) <= 3:
        return "La contraseña es demasiado repetitiva."
    if contrasena.lower() in _CONTRASENAS_DE_EJEMPLO or re.sub(r"[^a-z]", "", contrasena.lower()) in _CONTRASENAS_COMUNES:
        return "Esa contraseña es demasiado común; elige otra."
    nombre = (usuario or "").strip().lower()
    if len(nombre) >= 3 and nombre in contrasena.lower():
        return "La contraseña no puede contener el nombre de usuario."
    return None


# ------------------------------------------------------------------ limitador

class LimitadorIntentos:
    """Cuenta eventos por clave en una ventana de tiempo, guardados en la BD.

    Al estar en la base de datos, el bloqueo sobrevive a los reinicios y vale
    aunque haya varios procesos o réplicas.
    """

    @staticmethod
    def _tabla():
        from mi_app.models import EventoLimite

        return EventoLimite.__table__

    def espera(self, clave: str, maximo: int, ventana: float) -> int:
        """Segundos que faltan para poder intentarlo de nuevo (0 si se puede)."""
        tabla = self._tabla()
        ahora = time.time()
        with db.engine.connect() as conexion:
            momentos = conexion.execute(
                select(tabla.c.momento)
                .where(tabla.c.clave == clave[:200], tabla.c.momento > ahora - ventana)
                .order_by(tabla.c.momento)
            ).scalars().all()
        if len(momentos) < maximo:
            return 0
        return max(1, int(momentos[len(momentos) - maximo] + ventana - ahora) + 1)

    def registrar(self, clave: str) -> None:
        tabla = self._tabla()
        ahora = time.time()
        with db.engine.begin() as conexion:
            conexion.execute(insert(tabla).values(clave=clave[:200], momento=ahora))
            # Limpieza: lo de hace más de un día ya no cuenta para ninguna ventana.
            if secrets.randbelow(50) == 0:
                conexion.execute(delete(tabla).where(tabla.c.momento < ahora - 86400))

    def limpiar(self, clave: str) -> None:
        tabla = self._tabla()
        with db.engine.begin() as conexion:
            conexion.execute(delete(tabla).where(tabla.c.clave == clave[:200]))


def limitador() -> LimitadorIntentos:
    return current_app.extensions["mettav_limitador"]


def ip_cliente() -> str:
    return request.remote_addr or "desconocida"


def respuesta_limite(segundos: int, mensaje: str):
    minutos = -(-segundos // 60)
    respuesta = jsonify(error=f"{mensaje} Inténtalo de nuevo en {minutos} minuto(s).")
    respuesta.status_code = 429
    respuesta.headers["Retry-After"] = str(segundos)
    return respuesta


# ------------------------------------------------------------------- bitácora

def registrar_acceso(evento: str, exito: bool, usuario: str | None = None,
                     id_usuario: int | None = None, detalle: str | None = None) -> None:
    """Anota un evento de acceso. Un fallo al escribir nunca debe tumbar el login."""
    from mi_app.models import RegistroAcceso

    try:
        with db.engine.begin() as conexion:
            conexion.execute(insert(RegistroAcceso.__table__).values(
                momento=datetime.now(timezone.utc).replace(tzinfo=None),
                evento=evento,
                exito=exito,
                usuario=(usuario or None) and usuario[:80],
                id_usuario=id_usuario,
                ip=ip_cliente()[:64],
                agente=(request.headers.get("User-Agent") or "")[:200] or None,
                detalle=(detalle or None) and detalle[:200],
            ))
    except Exception:  # noqa: BLE001
        current_app.logger.exception("No se pudo registrar el evento de acceso '%s'.", evento)


# ------------------------------------------------------------------------ JWT

def _clave_jwt() -> bytes:
    """Clave de firma derivada de SECRET_KEY (siempre de 32 bytes)."""
    return hashlib.sha256(b"mettav-jwt-v1|" + current_app.secret_key.encode("utf-8")).digest()


def _sello(contrasena_hash: str) -> str:
    """Huella de la contraseña actual guardada en los tokens (no revela el hash)."""
    return hmac.new(
        current_app.secret_key.encode("utf-8"), contrasena_hash.encode("utf-8"), hashlib.sha256
    ).hexdigest()[:32]


def _csrf(familia: str) -> str:
    return hmac.new(_clave_jwt(), b"csrf|" + familia.encode("ascii"), hashlib.sha256).hexdigest()[:32]


def _codificar(carga: dict, ttl: int) -> str:
    ahora = int(time.time())
    return jwt.encode(
        {**carga, "iss": _EMISOR, "iat": ahora, "exp": ahora + max(1, ttl)},
        _clave_jwt(),
        algorithm="HS256",
    )


def _decodificar(token: str, tipo: str, *, verificar_exp: bool = True) -> dict | None:
    try:
        carga = jwt.decode(
            token,
            _clave_jwt(),
            algorithms=["HS256"],  # nunca "none" ni algoritmos asimétricos
            issuer=_EMISOR,
            leeway=5,
            options={"require": ["exp", "iat", "sub", "sid", "jti", "typ"], "verify_exp": verificar_exp},
        )
    except jwt.PyJWTError:
        return None
    if carga.get("typ") != tipo or not isinstance(carga.get("sid"), str):
        return None
    try:
        int(carga["sub"])
    except (TypeError, ValueError):
        return None
    return carga


def _emitir_cookies(usuario, fila, *, con_refresco: bool = True) -> None:
    """Prepara las cookies de acceso (y refresco) para añadirlas a la respuesta."""
    sello = _sello(usuario.contrasena_hash)
    restante = max(1, fila.expira - int(time.time()))
    base = {"sub": str(usuario.id_usuario), "sid": fila.familia, "pwd": sello}
    acceso = _codificar({**base, "typ": "access", "jti": secrets.token_hex(8)},
                        current_app.config["JWT_ACCESO_SEGUNDOS"])
    cookies = {COOKIE_ACCESO: (acceso, current_app.config["JWT_ACCESO_SEGUNDOS"])}
    if con_refresco:
        refresco = _codificar({**base, "typ": "refresh", "jti": fila.jti_actual}, restante)
        cookies[COOKIE_REFRESCO] = (refresco, restante)
    cookies[COOKIE_CSRF] = (_csrf(fila.familia), restante)
    g._mettav_cookies = cookies
    g._mettav_borrar = False


def _marcar_borrado() -> None:
    g._mettav_cookies = None
    g._mettav_borrar = True


def _aplicar_cookies(respuesta) -> None:
    seguro = bool(current_app.config.get("COOKIE_SECURE")) or request.is_secure
    if getattr(g, "_mettav_borrar", False):
        for nombre in (COOKIE_ACCESO, COOKIE_REFRESCO, COOKIE_CSRF):
            respuesta.delete_cookie(nombre, path="/", secure=seguro, samesite="Lax",
                                    httponly=nombre != COOKIE_CSRF)
        return
    for nombre, (valor, duracion) in (getattr(g, "_mettav_cookies", None) or {}).items():
        respuesta.set_cookie(
            nombre, valor, max_age=duracion, path="/", secure=seguro, samesite="Lax",
            # El token CSRF lo lee el JavaScript de la página para enviarlo en la cabecera.
            httponly=nombre != COOKIE_CSRF,
        )


def _fila_activa(familia: str, ahora: int):
    from mi_app.models import SesionToken

    fila = SesionToken.query.filter_by(familia=familia, revocada=False).first()
    if fila is None or ahora > fila.inicio + current_app.config["JWT_SESION_MAX_SEGUNDOS"]:
        return None
    return fila


def _revocar_familia(familia: str) -> None:
    from mi_app.models import SesionToken

    SesionToken.query.filter_by(familia=familia).update({"revocada": True})
    db.session.commit()


def _resolver_usuario():
    from mi_app.models import Usuario

    ahora = int(time.time())
    token = request.cookies.get(COOKIE_ACCESO)
    if token:
        carga = _decodificar(token, "access")
        if carga is not None:
            fila = _fila_activa(carga["sid"], ahora)
            usuario = db.session.get(Usuario, int(carga["sub"]))
            if (
                fila is not None
                and usuario is not None
                and fila.id_usuario == usuario.id_usuario
                and hmac.compare_digest(str(carga.get("pwd", "")), _sello(usuario.contrasena_hash))
            ):
                g._mettav_sid = fila.familia
                return usuario
            # Firma válida pero la sesión ya no existe o cambió la contraseña.
            _marcar_borrado()
            return None
    refresco = request.cookies.get(COOKIE_REFRESCO)
    if refresco:
        return _renovar(refresco, ahora)
    return None


def _renovar(token: str, ahora: int):
    """Cambia un refresco válido por un acceso nuevo, rotando el refresco."""
    from mi_app.models import Usuario

    carga = _decodificar(token, "refresh")
    if carga is None:
        _marcar_borrado()
        return None
    fila = _fila_activa(carga["sid"], ahora)
    usuario = db.session.get(Usuario, int(carga["sub"])) if fila is not None else None
    if (
        fila is None
        or usuario is None
        or fila.id_usuario != usuario.id_usuario
        or ahora > fila.expira
        or not hmac.compare_digest(str(carga.get("pwd", "")), _sello(usuario.contrasena_hash))
    ):
        _marcar_borrado()
        return None

    config = current_app.config
    if carga["jti"] == fila.jti_actual:
        fila.jti_anterior = fila.jti_actual
        fila.jti_actual = secrets.token_hex(16)
        fila.rotada_en = ahora
        fila.ultimo_uso = ahora
        fila.expira = min(ahora + config["JWT_INACTIVIDAD_SEGUNDOS"], fila.inicio + config["JWT_SESION_MAX_SEGUNDOS"])
        db.session.commit()
        _emitir_cookies(usuario, fila)
    elif carga["jti"] == fila.jti_anterior and ahora - fila.rotada_en <= _GRACIA_ROTACION:
        _emitir_cookies(usuario, fila, con_refresco=False)
    else:
        # Un refresco ya usado reapareció: alguien copió el token. Se cierra toda la sesión.
        fila.revocada = True
        db.session.commit()
        registrar_acceso("token_reutilizado", False, usuario=usuario.usuario, id_usuario=usuario.id_usuario,
                         detalle="Se reutilizó un token de refresco; sesión revocada.")
        _marcar_borrado()
        return None
    g._mettav_sid = fila.familia
    return usuario


def usuario_actual():
    """Devuelve el usuario de la sesión, o None si no hay sesión válida.

    Valida el JWT de acceso; si caducó, intenta renovarlo con el de refresco.
    """
    if "_mettav_auth" not in g:
        g._mettav_auth = _resolver_usuario()
    return g._mettav_auth


def iniciar_sesion_usuario(usuario) -> None:
    """Abre una sesión nueva y prepara las cookies con sus JWT."""
    from mi_app.models import SesionToken

    _revocar_sesion_de_la_peticion()
    ahora = int(time.time())
    config = current_app.config
    # Limpieza: sesiones revocadas o vencidas hace más de un día.
    SesionToken.query.filter(SesionToken.expira < ahora - 86400).delete()
    fila = SesionToken(
        familia=secrets.token_hex(16),
        id_usuario=usuario.id_usuario,
        jti_actual=secrets.token_hex(16),
        rotada_en=0,
        inicio=ahora,
        expira=ahora + min(config["JWT_INACTIVIDAD_SEGUNDOS"], config["JWT_SESION_MAX_SEGUNDOS"]),
        ultimo_uso=ahora,
        ip=ip_cliente()[:64],
        agente=(request.headers.get("User-Agent") or "")[:200] or None,
    )
    db.session.add(fila)
    db.session.commit()
    _emitir_cookies(usuario, fila)
    g._mettav_auth = usuario
    g._mettav_sid = fila.familia
    registrar_acceso("login", True, usuario=usuario.usuario, id_usuario=usuario.id_usuario)


def _carga_de_la_peticion() -> dict | None:
    """Carga de los tokens de la petición con la firma verificada (aunque hayan caducado)."""
    for nombre, tipo in ((COOKIE_REFRESCO, "refresh"), (COOKIE_ACCESO, "access")):
        token = request.cookies.get(nombre)
        if token:
            carga = _decodificar(token, tipo, verificar_exp=False)
            if carga is not None:
                return carga
    return None


def _revocar_sesion_de_la_peticion() -> dict | None:
    carga = _carga_de_la_peticion()
    if carga is not None:
        _revocar_familia(carga["sid"])
    return carga


def cerrar_sesion_actual() -> None:
    """Cierra la sesión en el servidor (revoca el refresco) y borra las cookies."""
    carga = _revocar_sesion_de_la_peticion()
    if carga is not None:
        registrar_acceso("logout", True, id_usuario=int(carga["sub"]))
    g._mettav_auth = None
    _marcar_borrado()


def revocar_sesiones_de(id_usuario: int, excepto: str | None = None) -> None:
    """Revoca todas las sesiones del usuario (menos la familia indicada)."""
    from mi_app.models import SesionToken

    consulta = SesionToken.query.filter_by(id_usuario=id_usuario, revocada=False)
    if excepto is not None:
        consulta = consulta.filter(SesionToken.familia != excepto)
    consulta.update({"revocada": True})
    db.session.commit()


def renovar_sello(usuario) -> None:
    """Tras cambiar la contraseña: la sesión actual sigue, las demás se cierran."""
    from mi_app.models import SesionToken

    familia = getattr(g, "_mettav_sid", None)
    fila = SesionToken.query.filter_by(familia=familia).first() if familia else None
    if fila is not None:
        fila.jti_actual = secrets.token_hex(16)
        fila.jti_anterior = None
        db.session.commit()
        _emitir_cookies(usuario, fila)
    revocar_sesiones_de(usuario.id_usuario, excepto=familia)


# ------------------------------------------------------------------------ CSRF

def _origen_permitido() -> bool:
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        return False
    origen = request.headers.get("Origin") or request.headers.get("Referer")
    if origen is None:
        # Sin cabecera de origen (clientes que no son navegadores): la cookie
        # SameSite=Lax ya impide que un navegador la envíe desde otro sitio, y
        # además se exige el token CSRF más abajo.
        return True
    return urlparse(origen).netloc == request.host


def _token_csrf_valido() -> bool:
    """Con sesión iniciada, las peticiones que modifican datos deben traer X-CSRF-Token."""
    if request.endpoint == "usuarios.iniciar_sesion":
        return True  # sin sesión previa; protegido por la comprobación de origen
    if not (request.cookies.get(COOKIE_ACCESO) or request.cookies.get(COOKIE_REFRESCO)):
        return True
    if usuario_actual() is None:
        return True  # la ruta responderá 401
    enviado = request.headers.get("X-CSRF-Token", "").encode("utf-8")
    return hmac.compare_digest(enviado, _csrf(g._mettav_sid).encode("ascii"))


def configurar_seguridad(app: Flask) -> None:
    app.config.setdefault("COOKIE_SECURE", os.environ.get("COOKIE_SECURE") == "1")
    app.config.setdefault("JWT_ACCESO_SEGUNDOS", _entorno_entero("JWT_ACCESO_MINUTOS", 15) * 60)
    app.config.setdefault("JWT_INACTIVIDAD_SEGUNDOS", _entorno_entero("JWT_INACTIVIDAD_MINUTOS", 30) * 60)
    app.config.setdefault("JWT_SESION_MAX_SEGUNDOS", _entorno_entero("JWT_SESION_MAX_HORAS", 12) * 3600)
    app.extensions["mettav_limitador"] = LimitadorIntentos()

    # Detrás del proxy de Coolify: confía en X-Forwarded-For/Proto/Host para
    # conocer la IP real del cliente y si la conexión es HTTPS. TRUST_PROXY_HOPS es
    # el número de proxies de confianza delante de la app (por defecto 1).
    confiar_en_proxy = os.environ.get("TRUST_PROXY") == "1"
    if confiar_en_proxy:
        saltos = _entorno_entero("TRUST_PROXY_HOPS", 1)
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=saltos, x_proto=1, x_host=1)

    @app.before_request
    def _proteger_csrf():
        if not confiar_en_proxy and request.headers.get("X-Forwarded-For") and not app.config.get("_aviso_proxy"):
            app.config["_aviso_proxy"] = True
            app.logger.warning(
                "Llegan cabeceras X-Forwarded-For pero TRUST_PROXY no está activo: el límite de intentos "
                "verá la IP del proxy. Define TRUST_PROXY=1 si la app está detrás de un proxy."
            )
        if request.method in _METODOS_QUE_MODIFICAN:
            if not _origen_permitido():
                return jsonify(error="Petición rechazada: origen no permitido."), 403
            if not _token_csrf_valido():
                return jsonify(error="Petición rechazada: falta el token CSRF."), 403
        return None

    @app.after_request
    def _cabeceras_seguridad(respuesta):
        _aplicar_cookies(respuesta)
        cabeceras = respuesta.headers
        cabeceras.setdefault("Content-Security-Policy", _CSP)
        cabeceras.setdefault("X-Content-Type-Options", "nosniff")
        cabeceras.setdefault("X-Frame-Options", "DENY")
        cabeceras.setdefault("Referrer-Policy", "same-origin")
        cabeceras.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.is_secure or app.config["COOKIE_SECURE"]:
            cabeceras.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.path.startswith("/api/") or request.path == "/dashboard":
            cabeceras.setdefault("Cache-Control", "no-store")
        return respuesta


def _entorno_entero(nombre: str, defecto: int) -> int:
    try:
        return max(1, int(os.environ.get(nombre) or defecto))
    except ValueError:
        return defecto
