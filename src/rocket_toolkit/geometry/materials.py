class MaterialsDatabase:
    def __init__(self): #values from granta edupack
        self.materials_db = {
            "Aluminum 6061-T6": {
                "thermal_conductivity": 167,  # W/(mK)
                "density": 2700,  # kg/m^3
                "specific_heat": 896,  # J/(kgK)
                "max_service_temp": 473,  # K
                "yield_strength": 270,  # MPa
                "thermal_expansion": 23.6e-6,  # 1/K
                "emissivity": 0.1  # Dimensionless
            },
            "Alumina": {
                "thermal_conductivity": 33,  # W/(mK)
                "density": 3750,  # kg/m^3
                "specific_heat": 690,  # J/(kgK)
                "max_service_temp": 1488,  # K
                "yield_strength": 270,  # MPa
                "thermal_expansion": 6e-6,  # 1/K
                "emissivity": 0.2  # Dimensionless
            },
            "Titanium Ti-6Al-4V": {
                "thermal_conductivity": 25,  # W/(mK)
                "density": 3930,  # kg/m^3
                "specific_heat": 610,  # J/(kgK)
                "max_service_temp": 505,  # K
                "yield_strength": 1050,  # MPa
                "thermal_expansion": 6.6e-6,  # 1/K
                "emissivity": 0.63  # Dimensionless
            },
            "Stainless Steel 304": {
                "thermal_conductivity": 15.5,  # W/(mK)
                "density": 7950,  # kg/m^3
                "specific_heat": 500,  # J/(kgK)
                "max_service_temp": 850,  # K
                "yield_strength": 264,  # MPa
                "thermal_expansion": 17.3e-6,  # 1/K
                "emissivity": 0.44  # Dimensionless
            },
            "Inconel 718": {
                "thermal_conductivity": 12.1,  # W/(mK)
                "density": 8230,  # kg/m^3
                "specific_heat": 448,  # J/(kgK)
                "max_service_temp": 632,  # K
                "yield_strength": 770,  # MPa
                "thermal_expansion": 13.0e-6,  # 1/K
                "emissivity": 0.28  # Dimensionless
            },
            "Beryllium": {
                "thermal_conductivity": 208,  # W/(mK)
                "density": 1850,  # kg/m^3
                "specific_heat": 1880,  # J/(kgK)
                "max_service_temp": 680,  # K
                "yield_strength": 247,  # MPa
                "thermal_expansion": 11.4e-6,  # 1/K
                "emissivity": 0.2  # Dimensionless
            },
            "Carbon carbon matrix composite": {
                "thermal_conductivity": 40,  # W/(mK)
                "density": 1700,  # kg/m^3
                "specific_heat": 756,  # J/(kgK)
                "max_service_temp": 2338,  # K
                "yield_strength": 500,  # MPa
                "thermal_expansion": 4e-6,  # 1/K
                "emissivity": 0.9  # Dimensionless
            }
        }
        
    def get_material_properties(self, material_name):
        if material_name in self.materials_db:
            return self.materials_db[material_name]
        return None
        
    def get_available_materials(self):
        return list(self.materials_db.keys())
    
    def get_materials_by_max_temp(self, min_temp=None, max_temp=None):
        """Get materials filtered by service temperature range"""
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
        """Get materials sorted by density (lightest first)"""
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