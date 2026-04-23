import requests
from bs4 import BeautifulSoup
import os
import re
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
}

MANUALSLIB_BASE = 'https://www.manualslib.com'


def _make_query(device_name, manufacturer, model):
    """Erstellt die beste Suchanfrage für ein Gerät."""
    if manufacturer and manufacturer != 'Unbekannt' and model and model != 'Unbekannt':
        return f"{manufacturer} {model}"
    elif manufacturer and manufacturer != 'Unbekannt':
        return f"{manufacturer} {device_name}"
    else:
        return device_name


def search_manualslib(query):
    """Sucht ein Handbuch auf manualslib.com. Gibt die erste Treffer-URL zurück oder None."""
    search_url = f"{MANUALSLIB_BASE}/search.php?q={requests.utils.quote(query)}"
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"ManualsLib-Suche fehlgeschlagen: {e}")
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Treffer in Suchergebnissen finden
    for tag in soup.find_all('a', href=re.compile(r'/manual-\d+/')):
        href = tag.get('href', '')
        if href and not href.endswith('/manual-search/'):
            return MANUALSLIB_BASE + href if not href.startswith('http') else href

    print(f"ManualsLib: Keine Treffer für '{query}'")
    return None


def get_pdf_url(manual_page_url):
    """Ermittelt die direkte PDF-URL von einer ManualsLib-Handbuchseite."""
    try:
        resp = requests.get(manual_page_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"ManualsLib-Manualseite nicht abrufbar: {e}")
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Variante 1: iframe mit pdf.manualslib.com
    iframe = soup.find('iframe', src=re.compile(r'pdf\.manualslib\.com', re.I))
    if iframe:
        return iframe['src']

    # Variante 2: Direkter PDF-Download-Link
    for a in soup.find_all('a', href=True):
        href = a['href']
        if re.search(r'\.pdf(\?|$)', href, re.I):
            return href if href.startswith('http') else MANUALSLIB_BASE + href

    # Variante 3: URL-Schema ableiten
    # z.B. /manual-12345/brand-model.html -> pdf.manualslib.com/manual-12345/brand-model.pdf
    match = re.search(r'/manual-(\d+)/(.+?)(?:\.html)?$', manual_page_url)
    if match:
        pdf_url = f"https://pdf.manualslib.com/manual-{match.group(1)}/{match.group(2)}.pdf"
        print(f"PDF-URL abgeleitet: {pdf_url}")
        return pdf_url

    return None


def download_pdf(url, dest_path):
    """Lädt eine PDF-Datei herunter. Gibt True bei Erfolg zurück."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True, allow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get('content-type', '')
        if 'pdf' not in content_type.lower() and not url.lower().split('?')[0].endswith('.pdf'):
            print(f"Kein PDF empfangen: Content-Type={content_type}, URL={url}")
            return False

        with open(dest_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        # Mindestgröße prüfen (< 5 KB = wahrscheinlich Fehlerseite)
        if os.path.getsize(dest_path) < 5120:
            os.remove(dest_path)
            print(f"Heruntergeladene Datei zu klein, verworfen")
            return False

        return True
    except Exception as e:
        print(f"PDF-Download fehlgeschlagen: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False


def find_and_download_manual(device_name, manufacturer, model, dest_folder):
    """
    Sucht und lädt eine Anleitung für ein Gerät herunter.
    Gibt (filename, error_message) zurück. Bei Erfolg ist error_message None.
    """
    query = _make_query(device_name, manufacturer, model)
    print(f"Suche Anleitung für: '{query}'")

    manual_page_url = search_manualslib(query)
    if not manual_page_url:
        return None, f"Keine Anleitung für '{query}' auf ManualsLib gefunden"

    pdf_url = get_pdf_url(manual_page_url)
    if not pdf_url:
        return None, "PDF-Link auf der Handbuchseite nicht gefunden"

    # Sicheren Dateinamen erstellen
    safe_name = re.sub(r'[^\w\-]', '_', query.lower())
    safe_name = re.sub(r'_+', '_', safe_name).strip('_')
    filename = f"{safe_name}.pdf"
    dest_path = os.path.join(dest_folder, filename)

    # Falls bereits vorhanden, direkt zurückgeben
    if os.path.exists(dest_path):
        print(f"Datei bereits vorhanden: {filename}")
        return filename, None

    if download_pdf(pdf_url, dest_path):
        print(f"Anleitung heruntergeladen: {filename}")
        return filename, None

    return None, "PDF-Download fehlgeschlagen"
