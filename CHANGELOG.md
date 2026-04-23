# Changelog

## [1.0.28] - 2026-04-23

### Neu
- **Automatischer Anleitung-Download**: PDF-Anleitungen für physische Geräte werden automatisch auf manualslib.com gesucht und heruntergeladen
  - "Anleitung suchen"-Button pro Gerät (nur bei Geräten ohne zugewiesene Anleitung)
  - "Alle Anleitungen suchen"-Button für alle Geräte auf einmal
- **Device Registry**: Import aus Home Assistant nutzt jetzt die WebSocket-API und die echte Device Registry statt Entity-States
  - Echter Hersteller und Modellname werden ausgelesen (z.B. „Philips", „IKEA", „Shelly")
  - Echter Raum/Bereich aus der HA Area Registry
  - Virtuelle Dienste und deaktivierte Geräte werden herausgefiltert
- **Automatische Versionsnummer**: Git Pre-Commit Hook zählt die Patch-Version bei jedem Commit automatisch hoch

### Technisch
- Neue Abhängigkeiten: `beautifulsoup4`, `websocket-client`
- Neues Modul `manual_downloader.py` für die PDF-Suche und den Download
- `home_assistant_api.py` vollständig auf WebSocket umgestellt

---

## [1.0.27] - 2026-04-22

### Neu
- **Raumkonfiguration**: Standorte (Räume) können eigenständig verwaltet werden
  - Standorte anlegen, umbenennen (mit optionalem Kaskadieren auf Geräte) und löschen
  - Import von Bereichen direkt aus Home Assistant
  - Automatischer Merge der HA-Bereiche beim Start
- **Standortanzeige**: Geräte-Ansicht nach Standort filterbar und sortierbar
  - Dedizierte Seite pro Standort mit allen zugehörigen Geräten

---

## [1.0.26] - 2026-04-21

### Neu
- Massenauswahl und -löschung von Geräten
- "Alle Geräte löschen"-Funktion

---

## [1.0.25] - 2026-04-20

### Neu
- **Home Assistant Import**: Geräte aus HA automatisch importieren
  - Duplikate werden anhand der Entity-ID erkannt
  - Importierte Geräte werden mit `ha_imported`-Flag markiert
  - Hersteller und Modell werden in der Geräteliste angezeigt

---

## [1.0.24] - 2026-04-19

### Neu
- Navigation zwischen allen Bereichen der App

---

## [1.0.23] - 2026-04-18

### Behoben
- Upload-Fehler bei bestehenden Dateien behoben
- URL-Generierung unter Home Assistant Ingress korrigiert

---

## [1.0.1] - 2026-04-17

### Neu
- Home Assistant API-Anbindung (REST)
- Grundlegende Fehlerbehandlung beim API-Zugriff

---

## [1.0.0] - 2026-04-16

### Erstveröffentlichung
- Web-Interface zum Hochladen und Verwalten von PDF-Anleitungen
- Geräte anlegen, bearbeiten und löschen
- PDF-Anleitungen Geräten zuweisen
- Home Assistant Ingress-Unterstützung
- Unterstützte Architekturen: armhf, armv7, aarch64, amd64, i386
