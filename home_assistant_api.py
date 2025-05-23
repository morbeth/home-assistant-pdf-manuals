import requests
import os
import json
import time

class HomeAssistantAPI:
    def __init__(self):
        # In Home Assistant Add-ons wird ein Supervisor-Token automatisch bereitgestellt
        self.token = os.environ.get('SUPERVISOR_TOKEN')
        print(f"Supervisor-Token vorhanden: {self.token is not None}")
        
        # Debug: Teste verschiedene API-Endpunkte, um herauszufinden, welche funktionieren
        self.base_url = self.find_working_api()
        
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        print(f"Verwende API Base URL: {self.base_url}")
    
    def find_working_api(self):
        """Teste verschiedene mögliche API-Endpunkte"""
        test_urls = [
            "http://supervisor/core/api",
            "http://supervisor/api",
            "http://homeassistant:8123/api",
            "http://host.docker.internal:8123/api",
            "http://172.30.32.1:8123/api",  # Typische Supervisor-IP
            "http://192.168.1.57:8123/api"  # Deine spezifische Home Assistant IP
        ]
        
        for base in test_urls:
            # Teste einen einfachen Endpunkt (states funktioniert in den meisten Fällen)
            url = f"{base}/states"
            try:
                headers = {"Authorization": f"Bearer {self.token}"}
                print(f"Teste API-URL: {url}")
                response = requests.get(url, headers=headers, timeout=3)
                if response.status_code == 200:
                    print(f"✅ API-URL funktioniert: {base}")
                    return base
                else:
                    print(f"❌ API-URL nicht erreichbar (Status {response.status_code}): {base}")
            except Exception as e:
                print(f"❌ API-URL nicht erreichbar (Fehler: {str(e)}): {base}")
        
        # Fallback zur ersten URL, wenn keine funktioniert
        print("⚠️ Keine API-URL funktioniert. Verwende Standard-URL.")
        return "http://supervisor/core/api"
    
    def get_devices(self):
        """Holt alle Geräte aus Home Assistant"""
        try:
            # Zuerst prüfen, ob wir die states abrufen können (grundlegende Funktionalität)
            response = requests.get(f"{self.base_url}/states", headers=self.headers)
            response.raise_for_status()
            all_states = response.json()
            print(f"Erfolgreich {len(all_states)} States abgerufen")
            
            # Da keine Registry verfügbar ist, erstelle die Geräteliste direkt aus den States
            print("Erstelle Geräteliste aus States")
            devices = []
            seen_devices = set()  # Um Duplikate zu vermeiden

            # Definiere die interessanten Domains
            device_domains = ['light', 'switch', 'climate', 'media_player', 'camera', 
                              'vacuum', 'cover', 'fan', 'humidifier', 'water_heater']
            
            # Gruppiere zuerst nach Areas, um eine bessere Zuordnung zu erhalten
            areas = {}
            for state in all_states:
                if state['entity_id'].startswith('zone.') or state['entity_id'].startswith('area.'):
                    entity_id = state['entity_id']
                    friendly_name = state['attributes'].get('friendly_name', entity_id.split('.')[1])
                    areas[entity_id] = friendly_name
            
            # Wenn keine Areas gefunden wurden, erstelle Standard-Areas
            if not areas:
                areas = {
                    'area.wohnzimmer': 'Wohnzimmer',
                    'area.kueche': 'Küche',
                    'area.schlafzimmer': 'Schlafzimmer',
                    'area.badezimmer': 'Badezimmer'
                }
            
            # Jetzt die Geräte-Entitäten verarbeiten
            for state in all_states:
                entity_id = state['entity_id']
                domain = entity_id.split('.')[0]
                
                # Nur relevante Geräte-Domains verarbeiten
                if domain in device_domains:
                    friendly_name = state['attributes'].get('friendly_name', entity_id)
                    device_id = state['attributes'].get('device_id', entity_id)
                    
                    # Duplikate vermeiden
                    if device_id in seen_devices:
                        continue
                    seen_devices.add(device_id)
                    
                    # Area bestimmen
                    area = 'Unbekannt'
                    area_id = state['attributes'].get('area_id')
                    if area_id:
                        area = areas.get(f"area.{area_id}", 'Unbekannt')
                    
                    # Für einige Gerätetypen, versuche die Area aus dem Namen zu erraten
                    if area == 'Unbekannt' and ' ' in friendly_name:
                        possible_area = friendly_name.split(' ')[0]
                        if possible_area.lower() in [a.lower() for a in areas.values()]:
                            area = possible_area
                    
                    # Erstelle das Gerät
                    device = {
                        'id': device_id,
                        'name': friendly_name,
                        'manufacturer': state['attributes'].get('manufacturer', 'Unbekannt'),
                        'model': state['attributes'].get('model', 'Unbekannt'),
                        'type': self.get_device_type(entity_id),
                        'location': area
                    }
                    devices.append(device)
        
        print(f"Gefundene Geräte: {len(devices)}")
        return devices
    except Exception as e:
        print(f"Fehler beim Abrufen der Geräte: {e}")
        return []
    
    def get_device_registry(self):
        """Holt das Geräteregister aus Home Assistant"""
        endpoints = [
            "/config/device_registry",
            "/devices",
            "/device_registry"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                print(f"Versuche Device Registry: {url}")
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                print(f"✅ Device Registry erfolgreich abgerufen über {endpoint}")
                return data
            except Exception as e:
                print(f"❌ Endpunkt {endpoint} nicht erfolgreich: {e}")
        
        print("⚠️ Keine funktionierenden Device Registry Endpunkte gefunden")
        return []

    def get_entity_registry(self):
        """Holt das Entity-Register aus Home Assistant"""
        endpoints = [
            "/config/entity_registry",
            "/entities",
            "/entity_registry"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                print(f"Versuche Entity Registry: {url}")
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                print(f"✅ Entity Registry erfolgreich abgerufen über {endpoint}")
                return data
            except Exception as e:
                print(f"❌ Endpunkt {endpoint} nicht erfolgreich: {e}")
        
        print("⚠️ Keine funktionierenden Entity Registry Endpunkte gefunden")
        return []

    def find_device_for_entity(self, entity_id, device_registry, entity_registry):
        """Findet das Gerät für eine bestimmte Entity"""
        try:
            # Suchen Sie die Entity in der Registry
            for entity in entity_registry:
                if entity['entity_id'] == entity_id and 'device_id' in entity:
                    device_id = entity['device_id']
                    # Suchen Sie das Gerät in der Device Registry
                    for device in device_registry:
                        if device['id'] == device_id:
                            return {
                                'id': device['id'],
                                'name': device.get('name_by_user') or device.get('name', 'Unbekanntes Gerät'),
                                'manufacturer': device.get('manufacturer', 'Unbekannt'),
                                'model': device.get('model', 'Unbekannt'),
                                'type': self.get_device_type(entity_id),
                                'location': self.get_device_area(device['area_id']) if 'area_id' in device else 'Unbekannt'
                            }
            # Keine Fehlermeldung ausgeben, wenn keine Zuordnung gefunden wird
            return None
        except Exception as e:
            print(f"Fehler beim Suchen des Geräts für Entity {entity_id}: {e}")
            return None
    
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
            # Weitere Domains können hier hinzugefügt werden
        }
        return type_mapping.get(domain, 'Sonstiges')
    
    def get_device_area(self, area_id):
        """Holt den Raum/Bereich für ein Gerät"""
        if not area_id:
            return 'Unbekannt'
        
        endpoints = [
            "/config/area_registry",
            "/areas",
            "/area_registry"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                areas = response.json()
                
                for area in areas:
                    if area['area_id'] == area_id:
                        return area['name']
                
                return 'Unbekannt'
            except Exception as e:
                continue
        
        return 'Unbekannt'

    def get_areas(self):
        """Holt alle Bereiche/Räume aus Home Assistant"""
        try:
            # Da die Area-Registry nicht verfügbar ist, erstelle eine Liste aus den States
            response = requests.get(f"{self.base_url}/states", headers=self.headers)
            response.raise_for_status()
            all_states = response.json()
            
            # Suche nach Zonen und Bereichen in den States
            areas = []
            seen_areas = set()
            
            # Zuerst explizite Area-Entitäten suchen
            for state in all_states:
                entity_id = state['entity_id']
                if entity_id.startswith('zone.') or entity_id.startswith('area.'):
                    friendly_name = state['attributes'].get('friendly_name', entity_id.split('.')[1])
                    area_id = entity_id
                    
                    if friendly_name not in seen_areas:
                        seen_areas.add(friendly_name)
                        areas.append({
                            'id': area_id,
                            'name': friendly_name
                        })
        
        # Dann Areas aus Geräteeigenschaften extrahieren
        for state in all_states:
            if 'area_id' in state['attributes']:
                area_name = state['attributes'].get('area_name', state['attributes']['area_id'])
                if area_name not in seen_areas:
                    seen_areas.add(area_name)
                    areas.append({
                        'id': state['attributes']['area_id'],
                        'name': area_name
                    })
        
        # Dann versuche, Raumnamen aus den Gerätenamen zu extrahieren
        for state in all_states:
            if 'friendly_name' in state['attributes']:
                name = state['attributes']['friendly_name']
                if ' ' in name:
                    possible_area = name.split(' ')[0]
                    # Typische Raumnamen prüfen
                    if possible_area.lower() in ['wohnzimmer', 'küche', 'schlafzimmer', 'badezimmer', 
                                               'flur', 'büro', 'keller', 'garage', 'garten']:
                        if possible_area not in seen_areas:
                            seen_areas.add(possible_area)
                            areas.append({
                                'id': f"extracted_{possible_area.lower()}",
                                'name': possible_area
                            })
        
        # Wenn immer noch keine Areas gefunden wurden, verwende Standard-Areas
        if not areas:
            areas = [
                {'id': 'default_living_room', 'name': 'Wohnzimmer'},
                {'id': 'default_kitchen', 'name': 'Küche'},
                {'id': 'default_bedroom', 'name': 'Schlafzimmer'},
                {'id': 'default_bathroom', 'name': 'Badezimmer'},
                {'id': 'default_office', 'name': 'Büro'}
            ]
        
        # Sortiere nach Namen
        sorted_areas = sorted(areas, key=lambda x: x['name'])
        print(f"Gefundene Bereiche: {len(sorted_areas)}")
        return sorted_areas
    except Exception as e:
        print(f"Fehler beim Abrufen der Bereiche: {e}")
        # Standard-Bereiche als Fallback
        return [
            {'id': 'default_living_room', 'name': 'Wohnzimmer'},
            {'id': 'default_kitchen', 'name': 'Küche'},
            {'id': 'default_bedroom', 'name': 'Schlafzimmer'},
            {'id': 'default_bathroom', 'name': 'Badezimmer'},
            {'id': 'default_office', 'name': 'Büro'}
        ]