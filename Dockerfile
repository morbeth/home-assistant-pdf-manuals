FROM python:3.9-alpine

# System-Pakete installieren
RUN apk add --no-cache \
    poppler-utils \
    nginx \
    bash \
    curl \
    wget

# Python-Pakete installieren
RUN pip3 install --no-cache-dir \
    flask==2.0.1 \
    werkzeug==2.0.1 \
    PyPDF2==2.11.1 \
    requests

# Arbeitsverzeichnis erstellen
WORKDIR /app

# Erstelle Verzeichnisse
RUN mkdir -p /data/manuals \
    /data/devices \
    /run/nginx \
    /app/static \
    /app/templates && \
    chmod -R 777 /data /app /run/nginx

# Kopiere Dateien
COPY nginx.conf /etc/nginx/nginx.conf
COPY main.py /app/
COPY home_assistant_api.py /app/
COPY run.sh /app/
COPY templates/ /app/templates/
COPY static/ /app/static/

# Berechtigungen setzen
RUN chmod +x /app/run.sh && \
    chmod 644 /etc/nginx/nginx.conf

# Debug aktivieren
ENV FLASK_ENV=development
ENV FLASK_DEBUG=1
ENV PYTHONUNBUFFERED=1

# Port
EXPOSE 8099

# Starten
CMD ["/app/run.sh"]