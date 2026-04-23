"""
Automatische Anleitung-Suche und -Download.

Strategie (in dieser Reihenfolge):
  1. manualslib.com  – größte Handbuch-Datenbank
  2. DuckDuckGo Lite – sucht nach direkten PDF-Links im Web
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

MANUALSLIB = 'https://www.manualslib.com'


# -----------------------------------------------------------------------
# Öffentliche API
# -----------------------------------------------------------------------

def find_and_download_manual(device_name, manufacturer, model, dest_folder):
    """
    Sucht und lädt eine Anleitung für ein Gerät herunter.

    Gibt (filename, error_message) zurück.
    Bei Erfolg ist error_message None.
    """
    query = _build_query(device_name, manufacturer, model)
    if not query:
        return None, "Kein Suchbegriff verfügbar (Name, Hersteller und Modell unbekannt)"

    print("Suche Anleitung für: '{}'".format(query))

    # Bereits heruntergeladene Datei?
    filename = _safe_filename(query)
    dest_path = os.path.join(dest_folder, filename)
    if os.path.exists(dest_path):
        print("Datei bereits vorhanden: {}".format(filename))
        return filename, None

    # Strategie 1: manualslib.com
    pdf_url = _search_manualslib(query)

    # Strategie 2: DuckDuckGo → direkter PDF-Link
    if not pdf_url:
        pdf_url = _search_duckduckgo_pdf(query)

    if not pdf_url:
        return None, "Keine Anleitung für '{}' gefunden".format(query)

    # PDF herunterladen
    if _download_pdf(pdf_url, dest_path):
        return filename, None

    return None, "Download von '{}' fehlgeschlagen".format(pdf_url)


# -----------------------------------------------------------------------
# Strategie 1: manualslib.com
# -----------------------------------------------------------------------

def _search_manualslib(query):
    """Sucht auf manualslib.com und gibt eine direkte PDF-URL zurück."""
    search_url = "{}/search.php?q={}".format(
        MANUALSLIB, requests.utils.quote(query)
    )
    try:
        resp = SESSION.get(search_url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print("manualslib.com Suche fehlgeschlagen: {}".format(e))
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Ersten Treffer finden: Link mit /manual-XXXX/ Muster
    manual_path = None
    for a in soup.find_all('a', href=True):
        href = a['href']
        if re.match(r'^/manual-\d+/', href):
            manual_path = href
            break

    if not manual_path:
        print("manualslib.com: Keine Treffer für '{}'".format(query))
        return None

    manual_url = MANUALSLIB + manual_path
    print("manualslib.com Treffer: {}".format(manual_url))

    # PDF-URL von der Manual-Seite ermitteln
    return _extract_pdf_url_manualslib(manual_url)


def _extract_pdf_url_manualslib(manual_page_url):
    """Extrahiert die direkte PDF-URL von einer manualslib.com Seite."""
    try:
        resp = SESSION.get(manual_page_url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print("manualslib.com Seite nicht abrufbar: {}".format(e))
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Variante 1: iframe mit pdf.manualslib.com
    for iframe in soup.find_all('iframe', src=True):
        if 'manualslib' in iframe['src']:
            return iframe['src']

    # Variante 2: Direkter Download-Link (.pdf)
    for a in soup.find_all('a', href=True):
        href = a['href']
        if re.search(r'\.pdf(\?|$)', href, re.I):
            return href if href.startswith('http') else MANUALSLIB + href

    # Variante 3: URL-Schema ableiten
    # /manual-12345/brand-model.html → pdf.manualslib.com/manual-12345/brand-model.pdf
    m = re.search(r'(/manual-\d+/[^?#]+?)(?:\.html)?$', manual_page_url)
    if m:
        pdf_url = "https://pdf.manualslib.com{}.pdf".format(m.group(1))
        print("manualslib.com PDF abgeleitet: {}".format(pdf_url))
        return pdf_url

    return None


# -----------------------------------------------------------------------
# Strategie 2: DuckDuckGo Lite → PDF-Link
# -----------------------------------------------------------------------

def _search_duckduckgo_pdf(query):
    """
    Sucht auf DuckDuckGo Lite nach einem direkten PDF-Link zur Anleitung.
    Gibt die erste gefundene PDF-URL zurück oder None.
    """
    search_query = "{} Bedienungsanleitung OR manual filetype:pdf".format(query)
    ddg_url = "https://lite.duckduckgo.com/lite/"

    try:
        resp = SESSION.get(ddg_url, params={'q': search_query}, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print("DuckDuckGo-Suche fehlgeschlagen: {}".format(e))
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')

    # DuckDuckGo Lite gibt Ergebnisse als <a class="result-link"> zurück
    for a in soup.find_all('a', href=True):
        href = a['href']
        # Direkte PDF-Links bevorzugen
        if re.search(r'\.pdf(\?|$)', href, re.I) and href.startswith('http'):
            print("DuckDuckGo PDF-Link: {}".format(href))
            return href

    # Zweiter Durchlauf: manualslib-Links aus DDG-Ergebnissen
    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'manualslib.com/manual-' in href:
            return _extract_pdf_url_manualslib(href)

    print("DuckDuckGo: Kein PDF-Link für '{}'".format(query))
    return None


# -----------------------------------------------------------------------
# Download
# -----------------------------------------------------------------------

def _download_pdf(url, dest_path):
    """Lädt eine PDF-Datei herunter. Gibt True bei Erfolg zurück."""
    try:
        resp = SESSION.get(url, timeout=60, stream=True, allow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get('content-type', '').lower()
        is_pdf_url   = re.search(r'\.pdf(\?|$)', url, re.I)
        if 'pdf' not in content_type and not is_pdf_url:
            print("Kein PDF: Content-Type='{}', URL={}".format(content_type, url))
            return False

        with open(dest_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        size = os.path.getsize(dest_path)
        if size < 5120:  # < 5 KB → Fehlerseite statt PDF
            os.remove(dest_path)
            print("Download zu klein ({} Bytes), verworfen".format(size))
            return False

        print("PDF heruntergeladen: {} ({} KB)".format(dest_path, size // 1024))
        return True

    except Exception as e:
        print("PDF-Download fehlgeschlagen: {}".format(e))
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False


# -----------------------------------------------------------------------
# Hilfsfunktionen
# -----------------------------------------------------------------------

def _build_query(device_name, manufacturer, model):
    """Erstellt die bestmögliche Suchanfrage."""
    manufacturer = (manufacturer or '').strip()
    model        = (model or '').strip()
    device_name  = (device_name or '').strip()

    # Unbekannte Werte ignorieren
    if manufacturer.lower() in ('unbekannt', 'unknown', ''):
        manufacturer = ''
    if model.lower() in ('unbekannt', 'unknown', ''):
        model = ''

    if manufacturer and model:
        return "{} {}".format(manufacturer, model)
    elif manufacturer:
        return "{} {}".format(manufacturer, device_name).strip()
    elif model:
        return model
    elif device_name:
        return device_name
    return ''


def _safe_filename(query):
    """Erstellt einen sicheren Dateinamen aus dem Suchbegriff."""
    name = re.sub(r'[^\w\-]', '_', query.lower())
    name = re.sub(r'_+', '_', name).strip('_')
    return name[:80] + '.pdf'
