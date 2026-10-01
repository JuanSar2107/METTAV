from flask import Blueprint, Response, jsonify


docs_bp = Blueprint("docs", __name__)

_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "METTAV API",
        "description": "API de usuarios y gestión de inventario.",
        "version": "1.0.0",
    },
    "servers": [{"url": "/"}],
    "components": {
        "securitySchemes": {
            "sessionCookie": {"type": "apiKey", "in": "cookie", "name": "session"}
        }
    },
    "paths": {
        "/health": {"get": {"summary": "Comprobar estado de la API", "responses": {"200": {"description": "API activa"}}}},
        "/api/usuarios": {
            "post": {"summary": "Registrar usuario", "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["usuario", "contrasena"], "properties": {"usuario": {"type": "string"}, "contrasena": {"type": "string", "format": "password"}}}}}}, "responses": {"201": {"description": "Usuario creado"}, "400": {"description": "Datos inválidos"}, "409": {"description": "Usuario existente"}}}
        },
        "/api/login": {"post": {"summary": "Iniciar sesión", "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["usuario", "contrasena"], "properties": {"usuario": {"type": "string"}, "contrasena": {"type": "string", "format": "password"}}}}}}, "responses": {"200": {"description": "Sesión iniciada"}, "401": {"description": "Credenciales inválidas"}}}},
        "/api/logout": {"post": {"summary": "Cerrar sesión", "responses": {"200": {"description": "Sesión cerrada"}}}},
        "/api/usuarios/me": {
            "get": {"summary": "Consultar usuario actual", "security": [{"sessionCookie": []}], "responses": {"200": {"description": "Usuario actual"}, "401": {"description": "No autenticado"}}},
            "put": {"summary": "Actualizar usuario actual", "security": [{"sessionCookie": []}], "responses": {"200": {"description": "Usuario actualizado"}, "401": {"description": "No autenticado"}}},
            "patch": {"summary": "Actualizar parcialmente el usuario", "security": [{"sessionCookie": []}], "responses": {"200": {"description": "Usuario actualizado"}, "401": {"description": "No autenticado"}}},
            "delete": {"summary": "Eliminar usuario actual", "security": [{"sessionCookie": []}], "responses": {"200": {"description": "Cuenta eliminada"}, "401": {"description": "No autenticado"}}},
        },
        "/api/inventario/": {"post": {"summary": "Crear artículo de inventario", "security": [{"sessionCookie": []}], "responses": {"201": {"description": "Artículo creado"}, "401": {"description": "No autenticado"}, "403": {"description": "Se requiere administrador"}}}},
        "/api/inventario/{id_articulo}": {"delete": {"summary": "Eliminar artículo", "security": [{"sessionCookie": []}], "parameters": [{"name": "id_articulo", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {"200": {"description": "Artículo eliminado"}, "404": {"description": "Artículo no encontrado"}}}},
        "/api/inventario/{id_articulo}/retirar": {"post": {"summary": "Retirar unidades del inventario", "security": [{"sessionCookie": []}], "parameters": [{"name": "id_articulo", "in": "path", "required": True, "schema": {"type": "integer"}}], "responses": {"200": {"description": "Stock actualizado"}, "409": {"description": "Stock insuficiente"}}}},
    },
}


@docs_bp.get("/openapi.json")
def openapi_json():
    return jsonify(_SPEC)


@docs_bp.get("/docs")
def swagger_ui():
    html = """<!doctype html><html><head><title>METTAV API Docs</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"></head>
<body><div id="swagger-ui"></div><script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>window.onload=()=>SwaggerUIBundle({url:'/openapi.json',dom_id:'#swagger-ui',persistAuthorization:true});</script>
</body></html>"""
    return Response(html, mimetype="text/html")
