"""Tests de la descarga del manual de usuario."""

from io import BytesIO

import pytest
from pypdf import PdfReader


def test_manual_requiere_sesion(client):
    respuesta = client.get("/manual-de-usuario")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/")


@pytest.mark.parametrize("campos", [{"es_admin": True}, {"es_auxiliar": True}, {}])
def test_cualquier_perfil_descarga_el_manual(client, creador_usuarios, iniciar_sesion, campos):
    creador_usuarios("persona", **campos)
    iniciar_sesion("persona")
    html = client.get("/dashboard").get_data(as_text=True)
    assert 'id="manual-button"' in html and 'href="/manual-de-usuario"' in html

    respuesta = client.get("/manual-de-usuario")
    assert respuesta.status_code == 200
    assert respuesta.mimetype == "application/pdf"
    assert 'filename=Manual-de-usuario-METTAV.pdf' in respuesta.headers["Content-Disposition"]
    assert "attachment" in respuesta.headers["Content-Disposition"]


def test_manual_cubre_las_funciones_actuales(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("persona")
    iniciar_sesion("persona")
    lector = PdfReader(BytesIO(client.get("/manual-de-usuario").data))
    texto = "\n".join(pagina.extract_text() for pagina in lector.pages)
    for tema in ("Ingresar existencias", "Salida integrada", "Remisión de salida", "Editar un artículo",
                 "Auxiliar", "Conciliación con Sizfra", "Descargar PDF", "código que sigue", "Problemas frecuentes"):
        assert tema in texto, tema
