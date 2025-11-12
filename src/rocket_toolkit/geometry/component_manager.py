import json
import os
from src.rocket_toolkit import config

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
            self.add_calculated_fin_mass(self.calculated_fin_mass, config.fin_set_cg_position)
        
        if components_loaded > 0:
            print(f"Successfully loaded {components_loaded} components from team data files")
            self.has_loaded_data = True
        else:
            print("No team data files found or no components loaded")
    
    def add_calculated_fin_mass(self, fin_mass, fin_position, num_fins=4):
        self.calculated_fin_mass = fin_mass
        self.components["fins (calculated)"] = {
            "mass": fin_mass * num_fins,  # Total mass of all fins
            "position": fin_position,
            "team": "aero",  # Assuming fins are part of aero team
            "description": f"Calculated mass for {num_fins} fins"
        }
        
        print(f"Using calculated fin mass: {fin_mass * num_fins:.4f} kg (total for {num_fins} fins)")
    
    def create_team_template(self, team_name):
        """
        Create a template JSON file for a team to fill in based on new structure
        """
        # Define specific templates for each team
        if team_name == "aero":
            team_components = {
                "nose cone": {
                    "mass": 3.0,
                    "position": 0.45,
                    "description": "nose cone"
                }
                # Note: Removed fins as they are calculated by fin sizer
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
        
        # Save to file
        file_path = os.path.join(get_team_data_path(), filename)
        with open(file_path, 'w') as f:
            json.dump(team_components, f, indent=4)
        
        print(f"Created template file for {team_name} team at {file_path}")
        return file_path
    
    def create_all_templates(self):
        """Create templates for all teams with new structure"""
        teams = ["aero", "fuselage", "nozzle"] # Updated team names
        for team in teams:
            self.create_team_template(team)
    
    def get_component_data(self):
        """Get the current component data for stability analysis"""
        return self.components
    
    def update_config(self):
        """Update the config variables with current component data"""
        # Reset default config values to zeros to ensure they don't influence results
        # if not present in JSON files
        config.nose_cone_mass = 0
        config.fuselage_mass = 0
        config.nozzle_mass = 0
        config.engine_mass = 0  
        config.propellant_mass = 0
        config.recovery_system_mass = 0
        
        # Calculate fuselage mass (total of all components with 'fuselage' in name)
        fuselage_mass = 0
        fuselage_mass_position_product = 0
        
        for component, data in self.components.items():
            comp_name = component.lower()
            
            # Handle fuselage components
            if "fuselage" in comp_name:
                fuselage_mass += data["mass"]
                fuselage_mass_position_product += data["mass"] * data["position"]
            # Handle other specific components
            elif comp_name == "nose cone" or "nose" in comp_name:
                config.nose_cone_mass = data["mass"]
                config.nose_cone_cg_position = data["position"]
                print(f"Updated config: nose_cone_mass = {data['mass']} kg")
            elif comp_name == "nozzle":
                config.nozzle_mass = data["mass"]
                config.nozzle_cg_position = data["position"]
                print(f"Updated config: nozzle_mass = {data['mass']} kg")
            elif comp_name == "engine":
                config.engine_mass = data["mass"]
                config.engine_cg_position = data["position"]
                print(f"Updated config: engine_mass = {data['mass']} kg")
            elif comp_name == "propellant":
                config.propellant_mass = data["mass"]
                config.propellant_cg_position = data["position"]
                print(f"Updated config: propellant_mass = {data['mass']} kg")
            elif "fin" in comp_name and "calculate" in comp_name:
                # This is the calculated fin mass - display it but don't set a config value
                # as it will be used directly from the fin calculations
                pass
        
        # Update fuselage mass and position if we have data
        if fuselage_mass > 0:
            # Calculate average position weighted by mass
            avg_position = fuselage_mass_position_product / fuselage_mass if fuselage_mass > 0 else 0
            
            config.fuselage_mass = fuselage_mass
            config.fuselage_cg_position = avg_position
            
            print(f"Updated config: fuselage_mass = {fuselage_mass} kg")
        
        # Calculate and update total dry weight
        dry_weight = 0
        for component, data in self.components.items():
            if "propellant" not in component.lower():  # Skip propellant for dry weight
                dry_weight += data["mass"]
        
        # Update dry weight with sum of all components
        config.dry_weight = dry_weight
        print(f"Updated config: dry_weight = {dry_weight} kg (sum of all non-propellant components)")
        
    def print_component_summary(self):
        """Print a summary of all components and their properties"""
        # If we haven't loaded data, try loading it first
        if not self.has_loaded_data or not self.components:
            self.update_from_team_files()
        
        print("\nRocket Component Summary:")
        print(f"{'Component':<20} {'Mass (kg)':<10} {'Position (m)':<15} {'Team':<15}")
        print('-' * 60)
        
        # Track total mass
        total_dry_mass = 0
        propellant_mass = 0
        
        # Sort components for better display - put propellant first, calculated fins last
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
        
        # Calculate total mass
        total_mass = total_dry_mass + propellant_mass
        
        print('-' * 60)
        print(f"{'Dry mass':<20} {total_dry_mass:<10.3f}")
        print(f"{'Propellant':<20} {propellant_mass:<10.3f}")
        print(f"{'Total':<20} {total_mass:<10.3f}")

