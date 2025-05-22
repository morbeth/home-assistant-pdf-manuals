#!/bin/bash

# Debug-Ausgabe aktivieren
set -x

# Stelle sicher, dass alle benötigten Verzeichnisse existieren
mkdir -p /data/manuals /data/devices /app/templates /app/static /run/nginx

# Berechtigungen setzen
chmod 777 -R /data /app/templates /app/static /run

# Alte Nginx-PID entfernen
rm -f /run/nginx/nginx.pid

# Starte Flask
echo "Starte Flask..."
python3 -u /app/main.py &
FLASK_PID=$!

echo "Warte auf Flask-Start..."
sleep 3

# Prüfe, ob Flask lokal erreichbar ist
curl -s http://127.0.0.1:5000/ || {
  echo "FEHLER: Flask ist nicht erreichbar! Logs:"
  ps aux
  exit 1
}

# Starte Nginx
echo "Starte Nginx..."
nginx -t

if [ $? -ne 0 ]; then
    echo "FEHLER: Nginx-Konfiguration ungültig!"
    exit 1
fi

nginx
sleep 2

# Prüfe, ob Nginx läuft
curl -s http://localhost:8099/ || {
  echo "FEHLER: Nginx ist nicht erreichbar! Logs:"
  cat /var/log/nginx/error.log
  exit 1
}

echo "Anwendung erfolgreich gestartet auf Port 8099"

# Halte Container am Laufen
tail -f /dev/null