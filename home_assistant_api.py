import os
import json
import requests

# WebSocket optional – erst nach Docker-Rebuild verfügbar
try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False
    print("WARNUNG: websocket-client nicht installiert. Nutze REST-Fallback.")

SUPERVISOR_WS   = "ws://supervisor/core/websocket"
SUPERVISOR_REST = "http://supervisor/core/api"


class HomeAssistantAPI:
    def __init__(self):
        self.token = os.environ.get('SUPERVISOR_TOKEN', '')
        self.headers = {
            "Authorization": "Bearer {}".format(self.token),
            "Content-Type": "application/json",
        }
        print("Supervisor-Token vorhanden: {}".format(bool(self.token)))
        print("WebSocket-Client verfügbar: {}".format(HAS_WEBSOCKET))

    # ------------------------------------------------------------------
    # WebSocket-Hilfsmethode
    # ------------------------------------------------------------------

    def _ws_query(self, *messages):
        """Sendet mehrere Nachrichten über eine WebSocket-Verbindung."""
        ws = websocket.create_connection(SUPERVISOR_WS, timeout=15)
        try:
            msg = json.loads(ws.recv())
            if msg.get('type') != 'auth_required':
                raise RuntimeError("Unerwartete Nachricht: {}".format(msg))

            ws.send(json.dumps({"type": "auth", "access_token": self.token}))
            msg = json.loads(ws.recv())
            if msg.get('type') != 'auth_ok':
                raise RuntimeError("Auth fehlgeschlagen: {}".format(msg))

            results = []
            for i, payload in enumerate(messages, start=1):
                payload['id'] = i
                ws.send(json.dumps(payload))
                resp = json.loads(ws.recv())
                if not resp.get('success', False):
                    raise RuntimeError("WS-Fehler bei {}: {}".format(payload.get('type'), resp))
                results.append(resp.get('result', []))
            return results
        finally:
            ws.close()

    # ------------------------------------------------------------------
    # Öffentliche Methoden
    # ------------------------------------------------------------------

    def get_devices(self):
        """Physische Geräte aus der HA Device Registry laden."""
        if HAS_WEBSOCKET:
            return self._get_devices_via_websocket()
        else:
            print("Nutze REST-Fallback (physische Geräte mit Hersteller/Modell aus Attributen)")
            return self._get_devices_via_rest()

    def get_areas(self):
        """Bereiche/Räume aus HA laden."""
        if HAS_WEBSOCKET:
            try:
                areas_raw, = self._ws_query({"type": "config/area_registry/list"})
                areas = [{'id': a['area_id'], 'name': a['name']} for a in areas_raw]
                return sorted(areas, key=lambda x: x['name'])
            except Exception as e:
                print("WebSocket-Bereiche fehlgeschlagen: {}".format(e))

        # REST-Fallback: Bereiche aus Entity-Attributen raten
        return self._get_areas_via_rest()

    # ------------------------------------------------------------------
    # WebSocket-Implementierung
    # ------------------------------------------------------------------

    def _get_devices_via_websocket(self):
        try:
            devices_raw, areas_raw, entities_raw = self._ws_query(
                {"type": "config/device_registry/list"},
                {"type": "config/area_registry/list"},
                {"type": "config/entity_registry/list"},
            )
        except Exception as e:
            print("WebSocket Device Registry fehlgeschlagen: {}".format(e))
            return self._get_devices_via_rest()

        area_map   = {a['area_id']: a['name'] for a in areas_raw}
        domain_map = {}
        for entity in entities_raw:
            dev_id = entity.get('device_id')
            if dev_id and dev_id not in domain_map:
                eid = entity.get('entity_id', '')
                domain_map[dev_id] = eid.split('.')[0] if '.' in eid else ''

        devices = []
        for raw in devices_raw:
            if raw.get('entry_type') == 'service':
                continue
            if raw.get('disabled_by') is not None:
                continue

            dev_id       = raw.get('id', '')
            name         = (raw.get('name_by_user') or raw.get('name') or 'Unbekanntes Gerät').strip()
            manufacturer = raw.get('manufacturer') or 'Unbekannt'
            model        = raw.get('model') or 'Unbekannt'
            area_id      = raw.get('area_id')
            location     = area_map.get(area_id, 'Unbekannt') if area_id else 'Unbekannt'
            domain       = domain_map.get(dev_id, '')

            devices.append({
                'id':           dev_id,
                'name':         name,
                'manufacturer': manufacturer,
                'model':        model,
                'type':         self._device_type(domain, manufacturer, model),
                'location':     location,
            })

        print("Physische Geräte (WebSocket): {}".format(len(devices)))
        return devices

    # ------------------------------------------------------------------
    # REST-Fallback
    # ------------------------------------------------------------------

    def _get_devices_via_rest(self):
        """
        Fallback: Entitäten abrufen und nur solche behalten, die
        tatsächlich manufacturer/model-Attribute haben (= echte Hardware).
        Pro Hersteller+Modell wird nur ein Gerät angelegt.
        """
        try:
            resp = requests.get("{}/states".format(SUPERVISOR_REST),
                                headers=self.headers, timeout=15)
            resp.raise_for_status()
            states = resp.json()
        except Exception as e:
            print("REST-States fehlgeschlagen: {}".format(e))
            return []

        seen = set()
        devices = []

        for state in states:
            attrs        = state.get('attributes', {})
            manufacturer = attrs.get('manufacturer', '').strip()
            model        = attrs.get('model', '').strip()

            # Nur Entitäten mit echten Hersteller- und Modellinformationen
            if not manufacturer or not model:
                continue

            key = (manufacturer.lower(), model.lower())
            if key in seen:
                continue
            seen.add(key)

            entity_id = state['entity_id']
            domain    = entity_id.split('.')[0]
            name      = attrs.get('friendly_name', entity_id)

            # Bereich aus friendly_name erraten (erster Teil)
            location = 'Unbekannt'
            if ' ' in name:
                first = name.split(' ')[0]
                if len(first) > 2 and first not in ['Der', 'Die', 'Das', 'Ein', 'Eine']:
                    location = first

            devices.append({
                'id':           entity_id,
                'name':         "{} {}".format(manufacturer, model),
                'manufacturer': manufacturer,
                'model':        model,
                'type':         self._device_type(domain, manufacturer, model),
                'location':     location,
            })

        print("Physische Geräte (REST-Fallback, mit Hersteller+Modell): {}".format(len(devices)))
        return devices

    def _get_areas_via_rest(self):
        try:
            resp = requests.get("{}/states".format(SUPERVISOR_REST),
                                headers=self.headers, timeout=15)
            resp.raise_for_status()
            states = resp.json()
        except Exception as e:
            print("REST-States für Bereiche fehlgeschlagen: {}".format(e))
            return []

        areas = set()
        for state in states:
            name = state.get('attributes', {}).get('friendly_name', '')
            if ' ' in name:
                first = name.split(' ')[0]
                if len(first) > 2 and first not in ['Der', 'Die', 'Das', 'Ein', 'Eine']:
                    areas.add(first)

        result = [{'id': 'rest_{}'.format(a.lower()), 'name': a} for a in sorted(areas)]
        return result

    # ------------------------------------------------------------------
    # Intern
    # ------------------------------------------------------------------

    @staticmethod
    def _device_type(domain, manufacturer, model):
        domain_map = {
            'light':               'Beleuchtung',
            'switch':              'Schalter',
            'climate':             'Klima / Heizung',
            'media_player':        'Medienplayer',
            'camera':              'Kamera',
            'vacuum':              'Staubsauger',
            'cover':               'Rollladen / Jalousie',
            'fan':                 'Lüfter',
            'lock':                'Schloss',
            'sensor':              'Sensor',
            'binary_sensor':       'Sensor',
            'alarm_control_panel': 'Alarm',
        }
        if domain in domain_map:
            return domain_map[domain]

        combined = (manufacturer + ' ' + model).lower()
        if any(k in combined for k in ['bulb', 'light', 'lamp', 'led', 'leuchte']):
            return 'Beleuchtung'
        if any(k in combined for k in ['plug', 'socket', 'steckdose', 'switch']):
            return 'Schalter'
        if any(k in combined for k in ['thermostat', 'heater', 'heizung', 'climate']):
            return 'Klima / Heizung'
        if any(k in combined for k in ['camera', 'cam', 'kamera']):
            return 'Kamera'
        if any(k in combined for k in ['sensor', 'motion', 'door', 'window', 'tür', 'fenster']):
            return 'Sensor'
        return 'Sonstiges'
