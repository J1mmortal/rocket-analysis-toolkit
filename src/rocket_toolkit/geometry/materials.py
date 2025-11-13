import json
import os

class MaterialsDatabase:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
            config_path = os.path.abspath(config_path)
        print("Loading materials from:", config_path)
        with open(config_path, "r") as f:
            config = json.load(f)
        self.materials_db = config.get("materials", {})
        print("Loaded materials:", self.materials_db)
        
        
    def get_material_properties(self, material_name):
        if material_name in self.materials_db:
            return self.materials_db[material_name]
        return None
        
    def get_available_materials(self):
        return list(self.materials_db.keys())
    
    def get_materials_by_max_temp(self, min_temp=None, max_temp=None):
        filtered_materials = []
        for name, props in self.materials_db.items():
            service_temp = props["max_service_temp"]
            if min_temp and service_temp < min_temp:
                continue
            if max_temp and service_temp > max_temp:
                continue
            filtered_materials.append(name)
        return filtered_materials
    
    def get_lightest_materials(self, max_density=None, count=None):
        materials_by_density = sorted(
            self.materials_db.items(),
            key=lambda x: x[1]["density"]
        )
        if max_density:
            materials_by_density = [
                (name, props) for name, props in materials_by_density
                if props["density"] <= max_density
            ]
        if count:
            materials_by_density = materials_by_density[:count]
        return [name for name, props in materials_by_density]