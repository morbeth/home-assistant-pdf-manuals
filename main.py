from flask import Flask, request, render_template, redirect, url_for, flash, send_from_directory
import os
import json
import time
import datetime
import PyPDF2
from werkzeug.utils import secure_filename
from home_assistant_api import HomeAssistantAPI  # Importieren Sie die HomeAssistantAPI-Klasse
from urllib.parse import urljoin

app = Flask(__name__,
            static_folder='static',  # Ordner mit statischen Dateien
            static_url_path='/static')  # URL-Pfad für statische Dateien
app.secret_key = os.urandom(24)

# Nach der Flask-App-Initialisierung und vor den Routen hinzufügen
@app.before_request
def fix_ingress():
    """Korrigiert die URL für Home Assistant Ingress"""
    # X-Ingress-Path Header von Nginx enthält den Basispfad
    ingress_path = request.headers.get('X-Ingress-Path', '')
    if ingress_path:
        # WSGI-Umgebung anpassen
        request.environ['SCRIPT_NAME'] = ingress_path
        path_info = request.environ['PATH_INFO']
        if path_info.startswith(ingress_path):
            request.environ['PATH_INFO'] = path_info[len(ingress_path):]
        
        # Debug-Informationen ausgeben
        print(f"Ingress aktiviert: Pfad={ingress_path}, PATH_INFO={request.environ['PATH_INFO']}")

# Nach der fix_ingress-Funktion hinzufügen
def get_base_url():
    """Gibt die Basis-URL für Links zurück, unter Berücksichtigung von Ingress"""
    script_name = request.environ.get('SCRIPT_NAME', '')
    if script_name:
        # Wenn ein Ingress-Pfad existiert, verwende ihn
        print(f"Verwende Basis-URL: {script_name}")
        return script_name
    
    # Wenn kein Ingress-Pfad existiert, versuche den Host mit Port zu konstruieren
    host = request.host
    if not ':' in host and app.config.get('SERVER_PORT'):
        # Wenn der Host keinen Port enthält, füge ihn hinzu
        host = f"{host}:{app.config.get('SERVER_PORT')}"
    
    # Verwende das gleiche Schema (http/https) wie die Anfrage
    scheme = request.scheme
    base_url = f"{scheme}://{host}"
    print(f"Konstruierte Basis-URL: {base_url}")
    return ""  # Gib einen leeren String zurück, da die URL durch Flask mit Hostnamen erstellt wird

# Die Funktion für alle Templates verfügbar machen
@app.context_processor
def inject_base_url():
    """Fügt die Basis-URL in alle Templates ein"""
    return dict(base_url=get_base_url())

# Überschreibe die url_for-Funktion für korrekte URLs
def custom_url_for(endpoint, **values):
    """Fügt die Basis-URL zu den generierten URLs hinzu"""
    original_url = url_for(endpoint, **values)
    base_url = get_base_url()
    
    if base_url and not original_url.startswith(base_url):
        # Wenn die Basis-URL noch nicht im Original enthalten ist
        if original_url.startswith('/'):
            # Entferne den führenden Slash, um Doppel-Slashes zu vermeiden
            original_url = original_url[1:]
        result = urljoin(base_url + '/', original_url)
        return result
    
    return original_url

# Ersetze die globale url_for-Funktion
app.jinja_env.globals['url_for'] = custom_url_for

# Jinja2 Filter für Datumsformatierung hinzufügen
@app.template_filter('strftime')
def _jinja2_filter_datetime(timestamp, fmt=None):
    date = datetime.datetime.fromtimestamp(timestamp)
    if fmt:
        return date.strftime(fmt)
    return date.strftime('%d.%m.%Y %H:%M')

# Slice Filter für Listen hinzufügen
@app.template_filter('slice')
def _slice(iterable, start, end=None, step=None):
    if end is None:
        end = len(iterable)
    return iterable[start:end:step]

# Pfade für die Datenspeicherung
UPLOAD_FOLDER = '/data/manuals'
DEVICES_FILE = '/data/devices/devices.json'
MANUAL_MAPPING_FILE = '/data/devices/manual_mapping.json'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(DEVICES_FILE), exist_ok=True)

# Home Assistant API initialisieren
ha_api = HomeAssistantAPI()

# Hilfsfunktion zum Laden der Geräte
def load_devices():
    if os.path.exists(DEVICES_FILE):
        with open(DEVICES_FILE, 'r') as f:
            return json.load(f)
    return []

# Hilfsfunktion zum Speichern der Geräte
def save_devices(devices):
    with open(DEVICES_FILE, 'w') as f:
        json.dump(devices, f, indent=4)

# Hilfsfunktion zum Laden der manuellen Mappings
def load_manual_mapping():
    if os.path.exists(MANUAL_MAPPING_FILE):
        with open(MANUAL_MAPPING_FILE, 'r') as f:
            return json.load(f)
    return {}

# Hilfsfunktion zum Speichern der manuellen Mappings
def save_manual_mapping(mapping):
    with open(MANUAL_MAPPING_FILE, 'w') as f:
        json.dump(mapping, f, indent=4)

# Hilfsfunktion zum Abrufen von PDF-Informationen
def get_pdf_info(filepath):
    try:
        with open(filepath, 'rb') as f:
            pdf = PyPDF2.PdfReader(f)
            num_pages = len(pdf.pages)
            return num_pages
    except Exception as e:
        print(f"Fehler beim Lesen der PDF-Datei: {e}")
        return 0

# Hilfsfunktion zum Laden der Anleitungen
def load_manuals():
    manuals = []
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.lower().endswith('.pdf'):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            filesize = os.path.getsize(filepath)
            pages = get_pdf_info(filepath)
            timestamp = os.path.getctime(filepath)
            manuals.append({
                'name': filename,
                'size': filesize,
                'pages': pages,
                'timestamp': timestamp
            })
    return sorted(manuals, key=lambda x: x['timestamp'])

@app.route('/')
def index():
    devices = load_devices()
    manuals = load_manuals()
    manual_mapping = load_manual_mapping()
    return render_template('index.html', devices=devices, manuals=manuals, manual_mapping=manual_mapping)

@app.route('/manuals')
def list_manuals():
    manuals = load_manuals()
    return render_template('manuals.html', manuals=manuals)

@app.route('/devices')
def list_devices():
    devices = load_devices()
    return render_template('devices.html', devices=devices)

@app.route('/upload', methods=['GET', 'POST'])
def upload_manual():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Keine Datei ausgewählt')
            return redirect(custom_url_for('upload_manual'))
        
        file = request.files['file']
        if file.filename == '':
            flash('Keine Datei ausgewählt')
            return redirect(custom_url_for('upload_manual'))
        
        if file and file.filename.lower().endswith('.pdf'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            
            # Überprüfen, ob die Datei bereits existiert
            if os.path.exists(filepath):
                flash(f'Die Datei {filename} existiert bereits')
                return redirect(custom_url_for('upload_manual'))
            
            file.save(filepath)
            flash('Anleitung erfolgreich hochgeladen')
            return redirect(custom_url_for('list_manuals'))
        else:
            flash('Nur PDF-Dateien sind erlaubt')
            return redirect(custom_url_for('upload_manual'))
    
    return render_template('upload_manual.html')

@app.route('/view_manual/<filename>')
def view_manual(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/delete_manual/<filename>')
def delete_manual(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        # Überprüfen, ob die Anleitung einem Gerät zugeordnet ist
        devices = load_devices()
        for device in devices:
            if device.get('manual') == filename:
                device['manual'] = None
        save_devices(devices)
        
        # Löschen der Datei
        os.remove(filepath)
        flash(f'Anleitung {filename} wurde gelöscht')
    else:
        flash(f'Anleitung {filename} wurde nicht gefunden')
    
    return redirect(custom_url_for('list_manuals'))

@app.route('/add_device', methods=['GET', 'POST'])
def add_device():
    if request.method == 'POST':
        name = request.form.get('name')
        device_type = request.form.get('type')
        location = request.form.get('location')
        manual = request.form.get('manual')
        
        if not name or not device_type or not location:
            flash('Bitte füllen Sie alle Pflichtfelder aus')
            return redirect(custom_url_for('add_device'))

        # Neues Gerät erstellen
        new_device = {
            'name': name,
            'type': device_type,
            'location': location,
            'manual': manual if manual else None
        }

        # Gerät zur Liste hinzufügen
        devices = load_devices()
        devices.append(new_device)
        save_devices(devices)

        flash('Gerät erfolgreich hinzugefügt')
        return redirect(custom_url_for('list_devices'))

    # Anleitungen für die Auswahl laden
    manuals = [manual['name'] for manual in load_manuals()]

    # Bereiche aus Home Assistant laden
    areas = ha_api.get_areas()

    return render_template('add_device.html', manuals=manuals, areas=areas)

@app.route('/edit_device/<int:device_id>', methods=['GET', 'POST'])
def edit_device(device_id):
    devices = load_devices()

    if device_id < 0 or device_id >= len(devices):
        flash('Gerät nicht gefunden')
        return redirect(custom_url_for('list_devices'))

    if request.method == 'POST':
        name = request.form.get('name')
        device_type = request.form.get('type')
        location = request.form.get('location')
        manual = request.form.get('manual')

        if not name or not device_type or not location:
            flash('Bitte füllen Sie alle Pflichtfelder aus')
            return redirect(custom_url_for('edit_device', device_id=device_id))

        # Gerät aktualisieren
        devices[device_id]['name'] = name
        devices[device_id]['type'] = device_type
        devices[device_id]['location'] = location
        devices[device_id]['manual'] = manual if manual else None

        save_devices(devices)
        flash('Gerät erfolgreich aktualisiert')
        return redirect(custom_url_for('list_devices'))

    # Anleitungen für die Auswahl laden
    manuals = [manual['name'] for manual in load_manuals()]

    # Bereiche aus Home Assistant laden
    areas = ha_api.get_areas()

    return render_template('edit_device.html', device=devices[device_id], device_id=device_id, manuals=manuals, areas=areas)

@app.route('/delete_device/<int:device_id>')
def delete_device(device_id):
    devices = load_devices()

    if device_id < 0 or device_id >= len(devices):
        flash('Gerät nicht gefunden')
    else:
        devices.pop(device_id)
        save_devices(devices)
        flash('Gerät erfolgreich gelöscht')

    return redirect(custom_url_for('list_devices'))

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/import_ha_devices')
def import_ha_devices():
    """Importiert Geräte aus Home Assistant"""
    try:
        # Aktuelle Geräte laden
        current_devices = load_devices()
        
        # Vorhandene Geräte-IDs abrufen, um Duplikate zu vermeiden
        existing_ids = {device.get('id') for device in current_devices if 'id' in device}
        
        # Geräte aus Home Assistant abrufen
        ha_devices = ha_api.get_devices()
        imported_count = 0
        
        for device in ha_devices:
            if device['id'] not in existing_ids:
                # Erstellen Sie ein neues Gerät im Format Ihrer Anwendung
                new_device = {
                    'id': device['id'],
                    'name': device['name'],
                    'type': device['type'],
                    'location': device['location'],
                    'manual': None,  # Keine Anleitung zugewiesen
                    'manufacturer': device['manufacturer'],
                    'model': device['model'],
                    'ha_imported': True  # Markieren als aus HA importiert
                }
                current_devices.append(new_device)
                imported_count += 1
        
        # Speichern der aktualisierten Geräteliste
        save_devices(current_devices)
        
        flash(f'{imported_count} Geräte aus Home Assistant importiert.')
        return redirect(custom_url_for('list_devices'))
    
    except Exception as e:
        flash(f'Fehler beim Importieren der Geräte: {str(e)}')
        return redirect(custom_url_for('list_devices'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8099, debug=True)