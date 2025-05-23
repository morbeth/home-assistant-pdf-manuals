import requests
import os
import json

class HomeAssistantAPI:
    def __init__(self):
        # In Home Assistant Add-ons wird ein Supervisor-Token automatisch bereitgestellt
        self.token = os.environ.get('SUPERVISOR_TOKEN')
        self.base_url = "http://supervisor/core/api"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def get_devices(self):
        """Holt alle Geräte aus Home Assistant"""
        try:
            response = requests.get(f"{self.base_url}/states", headers=self.headers)
            response.raise_for_status()
            all_states = response.json()
            
            # Filtern Sie Entitäten, die tatsächlich Geräte sind
            devices = []
            device_registry = self.get_device_registry()
            
            # Entity Registry nur einmal abrufen
            entity_registry = self.get_entity_registry()
            
            for state in all_states:
                entity_id = state['entity_id']
                # Prüfen, ob die Entity zu einem Gerät gehört
                device_info = self.find_device_for_entity(entity_id, device_registry, entity_registry)
                if device_info and device_info not in devices:
                    devices.append(device_info)
            
            return devices
        except Exception as e:
            print(f"Fehler beim Abrufen der Geräte: {e}")
            return []
    
    def get_device_registry(self):
        """Holt das Geräteregister aus Home Assistant"""
        try:
            response = requests.get(f"{self.base_url}/config/device_registry", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Fehler beim Abrufen des Geräteregisters: {e}")
            return []

    def get_entity_registry(self):
        """Holt das Entity-Register aus Home Assistant"""
        try:
            response = requests.get(f"{self.base_url}/config/entity_registry", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Fehler beim Abrufen des Entity-Registers: {e}")
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
        
        try:
            response = requests.get(f"{self.base_url}/config/area_registry", headers=self.headers)
            response.raise_for_status()
            areas = response.json()
            
            for area in areas:
                if area['area_id'] == area_id:
                    return area['name']
            
            return 'Unbekannt'
        except Exception as e:
            print(f"Fehler beim Abrufen des Bereichs: {e}")
            return 'Unbekannt'

    def get_areas(self):
        """Holt alle Bereiche/Räume aus Home Assistant"""
        try:
            response = requests.get(f"{self.base_url}/config/area_registry", headers=self.headers)
            response.raise_for_status()
            areas = response.json()
            
            # Bereite eine Liste der Bereiche vor
            return sorted([{
                'id': area['area_id'],
                'name': area['name']
            } for area in areas], key=lambda x: x['name'])
        except Exception as e:
            print(f"Fehler beim Abrufen der Bereiche: {e}")
            return []