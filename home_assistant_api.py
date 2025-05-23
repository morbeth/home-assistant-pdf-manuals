import requests
import os
import json
import time

class HomeAssistantAPI:
    def __init__(self):
        # In Home Assistant Add-ons wird ein Supervisor-Token automatisch bereitgestellt
        self.token = os.environ.get('SUPERVISOR_TOKEN')
        print("Supervisor-Token vorhanden: {}".format(self.token is not None))
        
        # Basis-URL festlegen
        self.base_url = "http://supervisor/core/api"
        self.headers = {
            "Authorization": "Bearer {}".format(self.token) if self.token else "",
            "Content-Type": "application/json"
        }
    
    def get_devices(self):
        """Holt alle Geräte aus Home Assistant"""
        try:
            # Zuerst prüfen, ob wir die states abrufen können
            response = requests.get("{}/states".format(self.base_url), headers=self.headers)
            response.raise_for_status()
            all_states = response.json()
            print("Erfolgreich {} States abgerufen".format(len(all_states)))
            
            # Da keine Registry verfügbar ist, erstelle die Geräteliste direkt aus den States
            print("Erstelle Geräteliste aus States")
            devices = []
            seen_devices = set()  # Um Duplikate zu vermeiden
            extracted_areas = set()  # Sammeln aller Standorte für spätere Verwendung

            # Definiere die interessanten Domains
            device_domains = ['light', 'switch', 'climate', 'media_player', 'camera', 
                             'vacuum', 'cover', 'fan']
            
            # Jetzt die Geräte-Entitäten verarbeiten
            for state in all_states:
                entity_id = state['entity_id']
                domain = entity_id.split('.')[0]
                
                # Nur relevante Geräte-Domains verarbeiten
                if domain in device_domains:
                    # Attribute aus dem State extrahieren
                    attrs = state.get('attributes', {})
                    friendly_name = attrs.get('friendly_name', entity_id)
                    device_id = entity_id  # Verwende entity_id als device_id, da keine Registry
                    
                    # Duplikate vermeiden
                    if device_id in seen_devices:
                        continue
                    seen_devices.add(device_id)
                    
                    # Area aus friendly_name extrahieren (z.B. "Wohnzimmer Licht")
                    area = 'Unbekannt'
                    if ' ' in friendly_name:
                        possible_area = friendly_name.split(' ')[0]
                        # Umfassendere Liste von möglichen Standorten
                        if len(possible_area) > 2 and possible_area not in ['Der', 'Die', 'Das', 'Ein', 'Eine']:
                            area = possible_area
                            # Füge den extrahierten Bereich zur Liste hinzu
                            extracted_areas.add(area)
                
                # Erstelle das Gerät
                device = {
                    'id': device_id,
                    'name': friendly_name,
                    'manufacturer': attrs.get('manufacturer', 'Unbekannt'),
                    'model': attrs.get('model', 'Unbekannt'),
                    'type': self.get_device_type(entity_id),
                    'location': area
                }
                devices.append(device)
        
        # Speichere die extrahierten Bereiche für die spätere Verwendung
        self.extracted_areas = extracted_areas
        
        print("Gefundene Geräte: {}".format(len(devices)))
        print("Extrahierte Bereiche: {}".format(len(extracted_areas)))
        return devices
    except Exception as e:
        print("Fehler beim Abrufen der Geräte: {}".format(e))
        return []
    
    def get_device_type(self, entity_id):
        """Bestimmt den Typ des Geräts anhand der Entity-ID"""
        domain = entity_id.split('.')[0]
        type_mapping = {
            'light': 'Beleuchtung',
            'switch': 'Schalter',
            'sensor': 'Sensor',
            'binary_sensor': 'Binärer Sensor',
            'climate': 'Klima',
            'media_player': 'Medienplayer',
            'camera': 'Kamera',
            'vacuum': 'Staubsauger'
        }
        return type_mapping.get(domain, 'Sonstiges')
    
    def get_areas(self):
        """Holt alle Bereiche/Räume aus Home Assistant oder gibt Standard-Bereiche zurück"""
        try:
            # Standard-Bereiche definieren
            standard_areas = [
                {'id': 'default_living_room', 'name': 'Wohnzimmer'},
                {'id': 'default_kitchen', 'name': 'Küche'},
                {'id': 'default_bedroom', 'name': 'Schlafzimmer'},
                {'id': 'default_bathroom', 'name': 'Badezimmer'},
                {'id': 'default_office', 'name': 'Büro'},
                {'id': 'default_hallway', 'name': 'Flur'},
                {'id': 'default_other', 'name': 'Sonstiger Ort'}
            ]
            
            # Füge extrahierte Bereiche hinzu, wenn wir sie bereits haben
            if hasattr(self, 'extracted_areas') and self.extracted_areas:
                for area_name in self.extracted_areas:
                    # Prüfen, ob der Bereich bereits in der Standardliste ist
                    if not any(area['name'] == area_name for area in standard_areas):
                        area_id = "extracted_{}".format(area_name.lower().replace(' ', '_'))
                        standard_areas.append({
                            'id': area_id,
                            'name': area_name
                        })
            else:
                # Versuchen, Bereiche aus States zu extrahieren, falls noch nicht geschehen
                try:
                    response = requests.get("{}/states".format(self.base_url), headers=self.headers)
                    if response.status_code == 200:
                        all_states = response.json()
                        
                        # Extrahiere einzigartige Bereiche aus Gerätenamen
                        extracted_areas = set()
                        for state in all_states:
                            attrs = state.get('attributes', {})
                            if 'friendly_name' in attrs:
                                name = attrs['friendly_name']
                                if ' ' in name:
                                    possible_area = name.split(' ')[0]
                                    if len(possible_area) > 2 and possible_area not in ['Der', 'Die', 'Das', 'Ein', 'Eine']:
                                        extracted_areas.add(possible_area)
                    
                    # Speichere für zukünftige Verwendung
                    self.extracted_areas = extracted_areas
                    
                    # Füge extrahierte Bereiche zur Standardliste hinzu
                    for area_name in extracted_areas:
                        # Prüfen, ob der Bereich bereits in der Standardliste ist
                        if not any(area['name'] == area_name for area in standard_areas):
                            area_id = "extracted_{}".format(area_name.lower().replace(' ', '_'))
                            standard_areas.append({
                                'id': area_id,
                                'name': area_name
                            })
                except Exception as e:
                    print("Fehler beim Extrahieren der Bereiche aus States: {}".format(e))
                    # Bei Fehler einfach Standard-Bereiche verwenden
                    pass
            
            return sorted(standard_areas, key=lambda x: x['name'])
        except Exception as e:
            print("Fehler beim Abrufen der Bereiche: {}".format(e))
            # Standard-Bereiche als Fallback
            return [
                {'id': 'default_living_room', 'name': 'Wohnzimmer'},
                {'id': 'default_kitchen', 'name': 'Küche'},
                {'id': 'default_bedroom', 'name': 'Schlafzimmer'},
                {'id': 'default_bathroom', 'name': 'Badezimmer'},
                {'id': 'default_office', 'name': 'Büro'},
                {'id': 'default_other', 'name': 'Sonstiger Ort'}
            ]