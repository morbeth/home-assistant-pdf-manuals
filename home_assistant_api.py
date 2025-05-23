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
            
            # Filtern Sie Entitäten, die tatsächlich Geräte sind
            devices = []
            device_registry = self.get_device_registry()
            
            # Entity Registry nur einmal abrufen
            entity_registry = self.get_entity_registry()
            
            # Versuche ein einfaches Geräte-Array zu erstellen, wenn keine Registry verfügbar ist
            if not device_registry and not entity_registry:
                print("Keine Registry verfügbar, erstelle einfache Geräteliste aus States")
                devices_by_domain = {}
                for state in all_states:
                    entity_id = state['entity_id']
                    domain = entity_id.split('.')[0]
                    if domain in ['light', 'switch', 'climate', 'media_player', 'camera', 'vacuum']:
                        friendly_name = state['attributes'].get('friendly_name', entity_id)
                        device_key = f"{domain}_{friendly_name}"
                        if device_key not in devices_by_domain:
                            devices_by_domain[device_key] = {
                                'id': entity_id,
                                'name': friendly_name,
                                'manufacturer': state['attributes'].get('manufacturer', 'Unbekannt'),
                                'model': state['attributes'].get('model', 'Unbekannt'),
                                'type': self.get_device_type(entity_id),
                                'location': state['attributes'].get('area', 'Unbekannt')
                            }
                
                return list(devices_by_domain.values())
            
            # Normale Verarbeitung, wenn Registry verfügbar ist
            for state in all_states:
                entity_id = state['entity_id']
                # Prüfen, ob die Entity zu einem Gerät gehört
                device_info = self.find_device_for_entity(entity_id, device_registry, entity_registry)
                if device_info and device_info not in devices:
                    devices.append(device_info)
            
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
        endpoints = [
            "/config/area_registry",
            "/areas",
            "/area_registry"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                print(f"Versuche Areas: {url}")
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                areas = response.json()
                
                result = sorted([{
                    'id': area['area_id'],
                    'name': area['name']
                } for area in areas], key=lambda x: x['name'])
                
                print(f"✅ Areas erfolgreich abgerufen über {endpoint}: {len(result)} Bereiche gefunden")
                return result
            except Exception as e:
                print(f"❌ Endpunkt {endpoint} für Areas nicht erfolgreich: {e}")
        
        print("⚠️ Keine Areas gefunden, verwende Standard-Bereiche")
        # Standard-Bereiche als Fallback
        return [
            {'id': 'default_living_room', 'name': 'Wohnzimmer'},
            {'id': 'default_kitchen', 'name': 'Küche'},
            {'id': 'default_bedroom', 'name': 'Schlafzimmer'},
            {'id': 'default_bathroom', 'name': 'Badezimmer'},
            {'id': 'default_office', 'name': 'Büro'}
        ]