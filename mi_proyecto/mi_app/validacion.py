"""Errores de validación y comprobaciones de datos enviados por el usuario."""

_MENSAJE_GENERICO = "Los datos enviados no son válidos."


class ErrorValidacion(ValueError):
    """Error cuyo mensaje lo escribimos nosotros y se puede mostrar al usuario."""

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


def mensaje_seguro(error: Exception) -> str:
    """Devuelve el texto apto para el usuario.

    Un ValueError lanzado por una librería puede traer detalles internos, así
    que solo se muestran los mensajes propios.
    """
    if isinstance(error, ErrorValidacion):
        return error.mensaje
    return _MENSAJE_GENERICO


def correo_valido(correo: str) -> bool:
    """Exige la forma usuario@dominio.ext, sin regex para evitar retrocesos costosos."""
    if correo.count("@") != 1 or any(caracter.isspace() for caracter in correo):
        return False
    usuario, dominio = correo.split("@")
    # El punto no puede ser ni el primer ni el último carácter del dominio.
    return bool(usuario) and "." in dominio[1:-1]
