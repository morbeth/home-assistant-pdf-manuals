import os
import json
import websocket  # websocket-client

SUPERVISOR_WS = "ws://supervisor/core/websocket"


class HomeAssistantAPI:
    def __init__(self):
        self.token = os.environ.get('SUPERVISOR_TOKEN', '')
        print("Supervisor-Token vorhanden: {}".format(bool(self.token)))

    # ------------------------------------------------------------------
    # Interne WebSocket-Hilfsmethode
    # ------------------------------------------------------------------

    def _ws_query(self, *messages):
        """
        Öffnet eine WebSocket-Verbindung, authentifiziert sich und sendet
        eine oder mehrere Nachrichten. Gibt eine Liste der Ergebnisse zurück.
        """
        ws = websocket.create_connection(SUPERVISOR_WS, timeout=15)
        try:
            # Auth-Handshake
            msg = json.loads(ws.recv())
            if msg.get('type') != 'auth_required':
                raise RuntimeError("Unerwartete Nachricht: {}".format(msg))

            ws.send(json.dumps({"type": "auth", "access_token": self.token}))
            msg = json.loads(ws.recv())
            if msg.get('type') != 'auth_ok':
                raise RuntimeError("Authentifizierung fehlgeschlagen: {}".format(msg))

            results = []
            for i, payload in enumerate(messages, start=1):
                payload['id'] = i
                ws.send(json.dumps(payload))
                resp = json.loads(ws.recv())
                if not resp.get('success', False):
                    raise RuntimeError("WS-Fehler: {}".format(resp))
                results.append(resp.get('result', []))

            return results
        finally:
            ws.close()

    # ------------------------------------------------------------------
    # Öffentliche Methoden
    # ------------------------------------------------------------------

    def get_devices(self):
        """
        Liefert physische Geräte aus der HA Device Registry.
        Virtuelle Dienste (entry_type='service') und deaktivierte Geräte
        werden herausgefiltert.
        """
        try:
            devices_raw, areas_raw, entities_raw = self._ws_query(
                {"type": "config/device_registry/list"},
                {"type": "config/area_registry/list"},
                {"type": "config/entity_registry/list"},
            )
        except Exception as e:
            print("Fehler beim Abrufen der Device Registry: {}".format(e))
            return []

        # Area-ID → Name Mapping
        area_map = {a['area_id']: a['name'] for a in areas_raw}

        # Device-ID → primäre Entity-Domain (für Gerätetyp)
        domain_map = {}
        for entity in entities_raw:
            dev_id = entity.get('device_id')
            if dev_id and dev_id not in domain_map:
                entity_id = entity.get('entity_id', '')
                domain_map[dev_id] = entity_id.split('.')[0] if '.' in entity_id else ''

        devices = []
        for raw in devices_raw:
            # Virtuelle Dienste und deaktivierte Geräte überspringen
            if raw.get('entry_type') == 'service':
                continue
            if raw.get('disabled_by') is not None:
                continue

            dev_id = raw.get('id', '')
            name = (raw.get('name_by_user') or raw.get('name') or 'Unbekanntes Gerät').strip()
            manufacturer = raw.get('manufacturer') or 'Unbekannt'
            model = raw.get('model') or 'Unbekannt'
            area_id = raw.get('area_id')
            location = area_map.get(area_id, 'Unbekannt') if area_id else 'Unbekannt'
            domain = domain_map.get(dev_id, '')

            devices.append({
                'id': dev_id,
                'name': name,
                'manufacturer': manufacturer,
                'model': model,
                'type': self._device_type(domain, manufacturer, model),
                'location': location,
            })

        print("Physische Geräte aus Device Registry: {}".format(len(devices)))
        return devices

    def get_areas(self):
        """Liefert alle Bereiche/Räume aus der HA Area Registry."""
        try:
            areas_raw, = self._ws_query({"type": "config/area_registry/list"})
            areas = [{'id': a['area_id'], 'name': a['name']} for a in areas_raw]
            return sorted(areas, key=lambda x: x['name'])
        except Exception as e:
            print("Fehler beim Abrufen der Areas: {}".format(e))
            return []

    # ------------------------------------------------------------------
    # Intern
    # ------------------------------------------------------------------

    @staticmethod
    def _device_type(domain, manufacturer, model):
        """Bestimmt den Gerätetyp aus Domain, Hersteller oder Modell."""
        domain_map = {
            'light':        'Beleuchtung',
            'switch':       'Schalter',
            'climate':      'Klima / Heizung',
            'media_player': 'Medienplayer',
            'camera':       'Kamera',
            'vacuum':       'Staubsauger',
            'cover':        'Rollladen / Jalousie',
            'fan':          'Lüfter',
            'lock':         'Schloss',
            'sensor':       'Sensor',
            'binary_sensor': 'Sensor',
            'alarm_control_panel': 'Alarm',
        }
        if domain in domain_map:
            return domain_map[domain]

        # Heuristik über Modell-/Herstellername
        combined = (manufacturer + ' ' + model).lower()
        if any(k in combined for k in ['bulb', 'light', 'lamp', 'led']):
            return 'Beleuchtung'
        if any(k in combined for k in ['plug', 'socket', 'steckdose']):
            return 'Schalter'
        if any(k in combined for k in ['thermostat', 'heater', 'climate']):
            return 'Klima / Heizung'
        if any(k in combined for k in ['camera', 'cam', 'kamera']):
            return 'Kamera'
        if any(k in combined for k in ['sensor', 'motion', 'door', 'window']):
            return 'Sensor'

        return 'Sonstiges'
