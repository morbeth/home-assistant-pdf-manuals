# PDF-Anleitungen Add-on

## Funktionen
- Hochladen und Verwalten von PDF-Anleitungen für Ihre Geräte
- Übersichtliche Weboberfläche
- Anzeigen der PDF-Dateien direkt im Browser
- Informationen über Seitenanzahl und Dateigröße
- Einfaches Löschen nicht mehr benötigter Anleitungen

## Installation
1. Fügen Sie das Add-on zu Home Assistant hinzu
2. Starten Sie das Add-on
3. Öffnen Sie die Weboberfläche über Port 8099

## Verwendung
1. Öffnen Sie die Weboberfläche des Add-ons
2. Nutzen Sie den "Hochladen" Button, um neue PDF-Anleitungen hinzuzufügen
3. Klicken Sie auf "Anzeigen", um eine Anleitung zu öffnen
4. Verwenden Sie "Löschen", um nicht mehr benötigte Anleitungen zu entfernen

## Technische Details
- Die PDF-Dateien werden in `/data/manuals` gespeichert
- Maximale Dateigröße: 16MB
- Unterstützte Formate: PDF

## Fehlersuche
### PDF kann nicht hochgeladen werden
- Überprüfen Sie, ob die Datei tatsächlich im PDF-Format vorliegt
- Stellen Sie sicher, dass die Datei nicht größer als 16MB ist
- Prüfen Sie die Zugriffsrechte des Add-ons

### PDF wird nicht angezeigt
- Überprüfen Sie, ob Ihr Browser PDF-Dateien anzeigen kann
- Stellen Sie sicher, dass die Datei nicht beschädigt ist