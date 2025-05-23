#!/bin/bash

# Verzeichnisse erstellen
mkdir -p /data/manuals /data/devices /app/templates /app/static /run/nginx
chmod 777 -R /data /app/templates /app/static /run
rm -f /run/nginx/nginx.pid

echo "Starte Flask..."
# Starte Flask im Hintergrund
python3 -u /app/main.py &
FLASK_PID=$!

echo "Warte auf Flask-Start..."
# Warte auf den Start von Flask (mit Timeout)
for i in {1..30}; do
  # Versuche auf beiden Ports (8099 und 5000)
  if curl -s http://127.0.0.1:8099/healthcheck > /dev/null || curl -s http://127.0.0.1:5000/healthcheck > /dev/null; then
    echo "Anwendung erfolgreich gestartet"
    # Halte das Skript am Laufen
    wait $FLASK_PID
    exit 0
  fi
  sleep 1
done

echo "FEHLER: Flask ist nicht erreichbar! Logs:"
ps aux
exit 1