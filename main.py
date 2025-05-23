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

# Debug-Log für den Startup
print("Starting Flask app...")
print(f"Host environment: IP={os.environ.get('HOST_IP', 'unknown')}")

# Nach der Flask-App-Initialisierung und vor den Routen hinzufügen
@app.before_request
def fix_ingress():
    """Korrigiert die URL für Home Assistant Ingress"""
    # X-Ingress-Path Header von Nginx enthält den Basispfad
    ingress_path = request.headers.get('X-Ingress-Path', '')
    x_forwarded_proto = request.headers.get('X-Forwarded-Proto', '')
    x_forwarded_host = request.headers.get('X-Forwarded-Host', '')

    # Debug-Informationen
    print(f"Request headers: Ingress-Path={ingress_path}, Host={request.host}, "
          f"X-Forwarded-Host={x_forwarded_host}, X-Forwarded-Proto={x_forwarded_proto}")
    print(f"Request: path={request.path}, full_path={request.full_path}")

    # HTTPS-Schema erzwingen, wenn der Forwarded-Proto Header HTTPS anzeigt
    if x_forwarded_proto == 'https':
        request.environ['wsgi.url_scheme'] = 'https'
        print("HTTPS-Schema erzwungen basierend auf X-Forwarded-Proto")

    if ingress_path:
        # WSGI-Umgebung anpassen
        request.environ['SCRIPT_NAME'] = ingress_path
        path_info = request.environ['PATH_INFO']
        if path_info.startswith(ingress_path):
            request.environ['PATH_INFO'] = path_info[len(ingress_path):]

        print(f"Ingress aktiviert: Pfad={ingress_path}, PATH_INFO={request.environ['PATH_INFO']}")

# Nach der fix_ingress-Funktion hinzufügen
def get_base_url():
    """Gibt die Basis-URL für Links zurück, unter Berücksichtigung von Ingress"""
    # X-Ingress-Path prüfen (Home Assistant spezifisch)
    ingress_path = request.headers.get('X-Ingress-Path', '')
    if ingress_path:
        print(f"Verwende Ingress-Basis-URL: {ingress_path}")
        return ingress_path

    # SCRIPT_NAME aus der WSGI-Umgebung prüfen
    script_name = request.environ.get('SCRIPT_NAME', '')
    if script_name:
        print(f"Verwende SCRIPT_NAME-Basis-URL: {script_name}")
        return script_name

    # Wenn wir hinter einem Proxy sind, verwende X-Forwarded-* Header
    x_forwarded_host = request.headers.get('X-Forwarded-Host', '')
    x_forwarded_proto = request.headers.get('X-Forwarded-Proto', '')

    if x_forwarded_host:
        proto = x_forwarded_proto if x_forwarded_proto else 'http'
        base_url = f"{proto}://{x_forwarded_host}"
        print(f"Verwende X-Forwarded-Basis-URL: {base_url}")
        return ""  # Leere Basis-URL, da die vollständige URL von Flask generiert wird

    # Direkte Anfrage (kein Proxy/Ingress)
    print("Keine Proxy/Ingress-Header gefunden. Verwende leere Basis-URL.")
    return ""

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

    # Vermeide doppelte Base-URLs
    if base_url and not original_url.startswith(base_url):
        # Wenn die Basis-URL noch nicht im Original enthalten ist

        # Wenn das original_url mit /static beginnt, stellen wir sicher, dass wir
        # nicht versehentlich einen doppelten Basis-URL-Pfad erzeugen
        if original_url.startswith('/'):
            original_url = original_url[1:]  # Entferne führenden Slash

        # Log für Debugging
        print(f"URL-Generierung: original={original_url}, base_url={base_url}")

        # Stellen Sie sicher, dass die URL korrekt ist (keine doppelten Slashes)
        if base_url.endswith('/') and original_url.startswith('/'):
            original_url = original_url[1:]
        elif not base_url.endswith('/') and not original_url.startswith('/'):
            result = f"{base_url}/{original_url}"
            print(f"URL umgeschrieben (einfach): {original_url} -> {result}")
            return result

        # Verwende urljoin für komplexere Fälle
        result = urljoin(base_url + '/', original_url)
        print(f"URL umgeschrieben (urljoin): {original_url} -> {result}")
        return result

    return original_url

# Ersetze die globale url_for-Funktion
app.jinja_env.globals['url_for'] = custom_url_for

# Hilfsfunktion für statische Dateien im Template
@app.context_processor
def utility_processor():
    def static_url(filename):
        """Generiert URLs für statische Dateien mit einer einzigen Basis-URL"""
        base_url = get_base_url()
        # Einfacher und direkter Ansatz
        if base_url:
            # Stellen Sie sicher, dass die URL korrekt formatiert ist
            if base_url.endswith('/'):
                url = f"{base_url}static/{filename}"
            else:
                url = f"{base_url}/static/{filename}"
        else:
            url = f"/static/{filename}"

        print(f"Static URL für {filename}: {url}")
        return url
    return dict(static_url=static_url)

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

# Stelle sicher, dass der static-Ordner existiert
if not os.path.isdir('static'):
    os.makedirs('static', exist_ok=True)
    print("Static-Verzeichnis erstellt")

# Stelle sicher, dass die CSS-Datei existiert
css_path = os.path.join('static', 'styles.css')
if not os.path.isfile(css_path):
    with open(css_path, 'w') as f:
        f.write("""
/* Basis-Stil */
body {
    font-family: Arial, sans-serif;
    line-height: 1.6;
    margin: 0;
    padding: 0;
    background-color: #f4f4f4;
    color: #333;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 1rem;
}

h1, h2, h3 {
    color: #2c3e50;
}

/* Navigation */
.nav {
    display: flex;
    background-color: #34495e;
    padding: 0.5rem 1rem;
    margin-bottom: 1.5rem;
    border-radius: 4px;
}

.nav a {
    color: white;
    text-decoration: none;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    transition: background-color 0.3s;
}

.nav a:hover {
    background-color: #2c3e50;
}

.nav a.active {
    background-color: #2980b9;
}

/* Meldungen */
.messages {
    margin-bottom: 1.5rem;
}

.message {
    background-color: #3498db;
    color: white;
    padding: 0.8rem 1rem;
    border-radius: 4px;
    margin-bottom: 0.5rem;
}

/* Tabellen */
.data-table {
    width: 100%;
    border-collapse: collapse;
    background-color: white;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
    border-radius: 4px;
    overflow: hidden;
}

.data-table th, .data-table td {
    padding: 0.8rem;
    border-bottom: 1px solid #e0e0e0;
    text-align: left;
}

.data-table th {
    background-color: #2980b9;
    color: white;
}

.data-table tr:hover {
    background-color: #f9f9f9;
}

.data-table .empty {
    color: #999;
    font-style: italic;
}

.data-table .actions {
    display: flex;
    gap: 0.5rem;
}

/* Buttons & Aktionen */
.action-btn {
    display: inline-block;
    padding: 0.3rem 0.7rem;
    border-radius: 4px;
    text-decoration: none;
    font-size: 0.9rem;
    transition: background-color 0.3s;
    color: white;
}

.action-btn.view {
    background-color: #2980b9;
}

.action-btn.edit {
    background-color: #f39c12;
}

.action-btn.delete {
    background-color: #e74c3c;
}

.action-btn:hover {
    opacity: 0.9;
}

/* Dashboard */
.dashboard {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1.5rem;
}

@media (min-width: 768px) {
    .dashboard {
        grid-template-columns: repeat(2, 1fr);
    }
}

.stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
    gap: 1rem;
    grid-column: 1 / -1;
}

.stat-box {
    background-color: white;
    padding: 1rem;
    border-radius: 4px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
    text-align: center;
}

.stat-box h3 {
    margin: 0 0 0.5rem 0;
    font-size: 1rem;
    color: #7f8c8d;
}

.stat-box .count {
    font-size: 2rem;
    font-weight: bold;
    color: #2980b9;
}

.recent {
    background-color: white;
    padding: 1rem;
    border-radius: 4px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
}

.recent h2 {
    margin-top: 0;
    border-bottom: 1px solid #eee;
    padding-bottom: 0.5rem;
    font-size: 1.2rem;
}

.list {
    list-style: none;
    padding: 0;
    margin: 0;
}

.list li {
    padding: 0.8rem 0;
    border-bottom: 1px solid #eee;
    display: flex;
    flex-direction: column;
}

.list li:last-child {
    border-bottom: none;
}

.list .name {
    font-weight: bold;
    margin-bottom: 0.3rem;
}

.list .info {
    color: #7f8c8d;
    font-size: 0.9rem;
    margin-bottom: 0.3rem;
}

.list .action {
    color: #2980b9;
    text-decoration: none;
    font-size: 0.9rem;
    margin-top: 0.3rem;
}

.list .empty {
    color: #999;
    font-style: italic;
    text-align: center;
    padding: 1.5rem 0;
}

/* Formulare */
.form {
    background-color: white;
    padding: 1.5rem;
    border-radius: 4px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
}

.form-group {
    margin-bottom: 1rem;
}

.form-group label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: bold;
}

.form-group input,
.form-group select,
.form-group textarea {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 1rem;
}

.form-actions {
    margin-top: 1.5rem;
}

.button {
    padding: 0.7rem 1.5rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
    transition: background-color 0.3s;
}

.button.primary {
    background-color: #2980b9;
    color: white;
}

.button.secondary {
    background-color: #95a5a6;
    color: white;
}

.button:hover {
    opacity: 0.9;
}

/* Content */
.content {
    background-color: white;
    padding: 1.5rem;
    border-radius: 4px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
}
        """)
    print("Standard CSS-Datei erstellt")

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

# Direkter Zugriff auf statische Dateien
@app.route('/static/<path:filename>')
def serve_static(filename):
    """Spezielle Route für statische Dateien mit korrektem MIME-Typ"""
    print(f"Direkter Zugriff auf statische Datei: {filename}")

    try:
        response = send_from_directory('static', filename)

        # Setze den MIME-Typ explizit für CSS-Dateien
        if filename.endswith('.css'):
            response.headers['Content-Type'] = 'text/css'
        elif filename.endswith('.js'):
            response.headers['Content-Type'] = 'application/javascript'

        return response
    except Exception as e:
        print(f"Fehler beim Zugriff auf statische Datei {filename}: {e}")
        return f"Datei {filename} nicht gefunden", 404

# Statusendpunkt für Healthchecks
@app.route('/healthcheck')
def healthcheck():
    return "OK", 200

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
    # Beide Ports unterstützen (5000 für Healthcheck, 8099 für regulären Betrieb)
    # In Produktion würde man hier einen WSGI-Server wie Gunicorn verwenden
    port = int(os.environ.get('PORT', 8099))
    print(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)