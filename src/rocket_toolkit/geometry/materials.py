import json
import os
from rocket_toolkit.config import load_config

class MaterialsDatabase:
    def __init__(self, cfg=None):
        if cfg is None:
            cfg = load_config()
        print("Loading materials from shared config")
        self.materials_db = cfg.get("materials", {})
        
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