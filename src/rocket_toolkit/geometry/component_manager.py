import json
import os

config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

def get_team_data_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    up_one = os.path.dirname(current_dir)
    up_two = os.path.dirname(up_one)
    project_root = os.path.dirname(up_two)
    team_data_path = os.path.join(project_root, "Team_data")
    return team_data_path

class ComponentData:
    def __init__(self):
        self.components = {}
        self.has_loaded_data = False 
        self.calculated_fin_mass = None 
        
        team_data_dir = get_team_data_path()
        os.makedirs(team_data_dir, exist_ok=True)
    
    def update_from_team_files(self):
        calculated_fin_mass = self.calculated_fin_mass
        self.components = {}
        self.calculated_fin_mass = calculated_fin_mass
        
        file_to_team_map = {
            "aero_group.json": "aero",
            "fuselage_group.json": "fuselage",
            "nozzle_group.json": "nozzle"
        }
        
        components_loaded = 0 # just for print
        
        for filename, team in file_to_team_map.items():
            file_path = os.path.join(get_team_data_path(), filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        team_data = json.load(f)
                    
                    for component_name, component_data in team_data.items():
                        if "mass" in component_data and component_data["mass"] <= 0:
                            continue
                        
                        if component_name.lower() == "fins" or component_name.lower() == "fin":
                            continue
                        
                        self.components[component_name] = component_data.copy()
                        self.components[component_name]["team"] = team
                        
                        components_loaded += 1
                    
                    print(f"Loaded component data from {filename}")
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")
        
        if self.calculated_fin_mass is not None:
            self.add_calculated_fin_mass(self.calculated_fin_mass, config["mass_properties"]["fin_set_cg_position"])
        
        if components_loaded > 0:
            print(f"Successfully loaded {components_loaded} components from team data files")
            self.has_loaded_data = True
        else:
            print("No team data files found or no components loaded")
    
    def add_calculated_fin_mass(self, fin_mass, fin_position, num_fins=4):
        self.calculated_fin_mass = fin_mass
        self.components["fins (calculated)"] = {
            "mass": fin_mass * num_fins,
            "position": fin_position,
            "team": "aero",
            "description": f"Calculated mass for {num_fins} fins"
        }
        
        print(f"Using calculated fin mass: {fin_mass * num_fins:.4f} kg (total for {num_fins} fins)")
    
    def create_team_template(self, team_name):
        if team_name == "aero":
            team_components = {
                "nose cone": {
                    "mass": 3.0,
                    "position": 0.45,
                    "description": "nose cone"
                }
            }
            filename = "aero_group.json"
        elif team_name == "fuselage":
            team_components = {
                "fuselage_oxi": {
                    "mass": 182.0,
                    "position": 2.4,
                    "description": "oxidant fuselage"
                },
                "fuselage_fuel": {
                    "mass": 20.0,
                    "position": 1.2,
                    "description": "fuel fuselage"
                },
                "propellant": {
                    "mass": 307.5,
                    "position": 1.9,
                    "description": "propellant from fuel and oxidator together"
                }
            }
            filename = "fuselage_group.json"
        elif team_name == "nozzle":
            team_components = {
                "nozzle": {
                    "mass": 0.0,
                    "position": 2.7,
                    "description": "nozzle structure"
                },
                "engine": {
                    "mass": 4.0,
                    "position": 2.35,
                    "description": "engine with thrust characteristics"
                }
            }
            filename = "nozzle_group.json"
        else:
            print(f"Unknown team: {team_name}")
            return None
        
        file_path = os.path.join(get_team_data_path(), filename)
        with open(file_path, 'w') as f:
            json.dump(team_components, f, indent=4)
        
        print(f"Created template file for {team_name} team at {file_path}")
        return file_path
    
    def create_all_templates(self):
        teams = ["aero", "fuselage", "nozzle"]
        for team in teams:
            self.create_team_template(team)
    
    def get_component_data(self):
        return self.components
    
    def update_config(self, config):
        cfg_components = config.get("components", {})
        if not isinstance(cfg_components, dict):
            cfg_components = {}
    
        dry_mass = 0.0
        propellant_mass = 0.0
        for name, data in self.components.items():
            mass = data.get("mass", 0.0)
            position = data.get("position", 0.0)
            team = data.get("team", "N/A")
            description = data.get("description", "")
            if mass <= 0:
                continue
            if name.lower() in ("fins", "fin"):
                continue
            cfg_components[name] = {
                "mass": mass,
                "position": position,
                "team": team,
                "description": description,
            }
    
        existing_components = config.get("components", {})
        for name, data in existing_components.items():
            if name not in cfg_components:
                cfg_components[name] = data
        for name, data in cfg_components.items():
            mass = data.get("mass", 0.0)
            if mass <= 0:
                continue
            if "propellant" in name.lower():
                propellant_mass += mass
            else:
                dry_mass += mass
    
        config["components"] = cfg_components
        config["dry_mass"] = dry_mass
        config["propellant_mass"] = propellant_mass
        config["wet_mass"] = dry_mass + propellant_mass
        print(
            f"Updated config from team data: "
            f"dry_mass = {dry_mass:.3f} kg, "
            f"propellant_mass = {propellant_mass:.3f} kg, "
            f"wet_mass = {dry_mass + propellant_mass:.3f} kg"
        )

        
    def print_component_summary(self):
        if not self.has_loaded_data or not self.components:
            print("\nNo component data loaded. Please use 'Load team data from files' first.")
            return
        
        print("\nRocket Component Summary:")
        print(f"{'Component':<20} {'Mass (kg)':<10} {'Position (m)':<15} {'Team':<15}")
        print('-' * 60)
        
        total_dry_mass = 0
        propellant_mass = 0
        
        def sort_key(item):
            name = item[0].lower()
            if "propellant" in name:
                return (0, name)
            elif "calculate" in name and "fin" in name:
                return (2, name)
            else:
                return (1, name)
        
        sorted_components = sorted(self.components.items(), key=sort_key)
        
        for name, data in sorted_components:
            if "propellant" in name.lower():
                propellant_mass += data['mass']
            else:
                total_dry_mass += data['mass']
            
            print(f"{name:<20} {data['mass']:<10.3f} {data['position']:<15.3f} {data.get('team', 'N/A'):<15}")
        
        total_mass = total_dry_mass + propellant_mass
        
        print('-' * 60)
        print(f"{'Dry mass':<20} {total_dry_mass:<10.3f}")
        print(f"{'Propellant':<20} {propellant_mass:<10.3f}")
        print(f"{'Total':<20} {total_mass:<10.3f}")

