# syntax=docker/dockerfile:1

# Imagen base: Python 3.12 sobre Debian slim (ligera y estable)
FROM python:3.12-slim

# Mejores prácticas: no generar .pyc y salida de logs sin buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) Instalar dependencias primero (aprovecha la caché de capas de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 2) Copiar el código de la aplicación
COPY . .

# 3) Usuario sin privilegios (mejora la seguridad en producción)
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/instance /app/mi_app/static/images \
    && chown -R appuser:appuser /app
USER appuser

# Puerto que expone la aplicación
EXPOSE 5000

# Servidor de producción: Gunicorn
# 1 worker con hilos: lo recomendado para SQLite (evita bloqueos de escritura)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "app:app"]