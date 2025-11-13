import numpy as np
import pandas as pd
import os
import json
from src.rocket_toolkit.geometry.materials import MaterialsDatabase
from src.rocket_toolkit import config
import time

def get_team_data_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    up_one = os.path.dirname(current_dir)
    up_two = os.path.dirname(up_one)
    project_root = os.path.dirname(up_two)
    team_data_path = os.path.join(project_root, "Team_data")
    return team_data_path

class RocketFin:
    def __init__(self, material_name=None):
        self.delta_v = 1400  # m/s required
        self.isp = 235  # sec
        self.m_payload = 1.3  # kg
        self.g0 = 9.81  # m/s^2
        self.max_q = 82800.0  # Pascals
        if hasattr(config, 'max_q'):
            config.max_q = self.max_q
        self.dt = 0.2  # sec of maneuver to get rotational velocity
        self.min_rad = 1  # rad/s
        self.max_rad = 5  # rad/s
        self.tol = 1e-7
        self.max_iter = 100
        self.radius_fuselage = 0.25  # m
        self.radial_fin_length = 0.05  # m
        self.wall_thickness = 4  # mm
        self.aoa = 0.4  # degrees - increased from 0.1 for better convergence
        self.aoa_rad = np.radians(self.aoa)
        self.fin_angle = 40  # degrees
        self.fin_angle_rad = np.radians(self.fin_angle)
        self.finconflict_value = 0.69
        self.num_fins = 4
        self.m1 = 2  # kg
        self.m1_marge = 0.2
        self.m2 = 4  # kg
        self.m2_marge = 0.2
        self.m3 = 3  # kg
        self.m3_marge = 0.2
        self.ambient_temp = 288.15  # K
        self.velocity = None  # m/s
        self.altitude = None  # m
        self.fin_area = None
        self.fin_height = None
        self.fin_width = None
        self.fin_mass = None
        self.materials_db = MaterialsDatabase()
        self.material_dimensions = {}
        if material_name is None:
            material_name = "Aluminum 6061-T6"  # Default fallback
        self.set_material(material_name)
        self.all_materials_data = None
        self._masses_cache = None
        self._component_data_cache = None
        self._component_data_timestamp = 0
        self._geom_ratio = np.tan(self.fin_angle_rad)
        self._cl = 2 * np.pi * self.aoa_rad
    
    def set_material(self, material_name):
        if not material_name:
            return False
    
        material = self.materials_db.get_material_properties(material_name)
        if not material:
            print(f"Warning: Material '{material_name}' not found in database. Using default properties.")
            self.material_name = material_name
            return False
    
        self.material_name = material_name
        self.thermal_conductivity = material["thermal_conductivity"]
        self.density = material["density"]
        self.specific_heat = material["specific_heat"]
        self.max_service_temp = material["max_service_temp"]
        self.yield_strength = material["yield_strength"]
        self.thermal_expansion = material["thermal_expansion"]
        self.emissivity = material["emissivity"]
    
        # Optionally handle material-specific dimensions if you are still using them
        if hasattr(self, "material_dimensions") and material_name in self.material_dimensions:
            dims = self.material_dimensions[material_name]
            self.fin_area = dims["area"]
            self.fin_height = dims["height"]
            self.fin_width = dims["width"]
            self.fin_mass = dims["mass"]
            self.radial_fin_length = dims["radial_length"]
    
        return True

    
    def get_available_materials(self):
        return self.materials_db.get_available_materials()
    
    def load_component_data(self):
        current_time = time.time()
        
        if (self._component_data_cache is not None and 
            current_time - self._component_data_timestamp < 1.0):
            return self._component_data_cache
        
        components = {}
        total_mass = 0
        team_data_path = get_team_data_path()
        file_paths = [
            os.path.join(team_data_path, "aero_group.json"),
            os.path.join(team_data_path, "fuselage_group.json"),
            os.path.join(team_data_path, "nozzle_group.json")
        ]
        
        for file_path in file_paths:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        team_data = json.load(f)
                    
                    for component_name, component_data in team_data.items():
                        if "mass" in component_data:
                            mass = component_data["mass"]
                            components[component_name] = {
                                "mass": mass,
                                "team": os.path.basename(file_path).split('_')[0]
                            }
                            total_mass += mass
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")
        
        self._component_data_cache = (components, total_mass)
        self._component_data_timestamp = current_time
        
        return components, total_mass
    
    def masses(self):
        if self._masses_cache is not None:
            return self._masses_cache
        
        components, total_mass = self.load_component_data()
        
        if components and total_mass > 0:
            total_mass += self.m_payload
            
            dry_mass = 0
            propellant_mass = 0
            for name, data in components.items():
                if "propellant" in name.lower():
                    propellant_mass += data["mass"]
                else:
                    dry_mass += data["mass"]
            
            self._masses_cache = dry_mass + self.m_payload + propellant_mass
            return self._masses_cache
        
        fuel_frac = (np.exp(self.delta_v / (self.isp * self.g0)) - 1) * 100
        m_empty_min = self.m1 * (1 - self.m1_marge) + self.m2 * (1 - self.m2_marge) + self.m3 * (1 - self.m3_marge) + self.m_payload
        m_empty_max = self.m1 * (1 + self.m1_marge) + self.m2 * (1 + self.m2_marge) + self.m3 * (1 + self.m3_marge) + self.m_payload
        
        self._masses_cache = (m_empty_min + m_empty_max) / 2
        return self._masses_cache
    
    def calculate_fin_mass(self, height_mm=None, width_mm=None, material=None):
        if height_mm is None:
            height_mm = self.fin_height
        if width_mm is None:
            width_mm = self.fin_width
            
        if height_mm is None or width_mm is None:
            return None
            
        height_m = height_mm * 0.001
        width_m = width_mm * 0.001
        thickness_m = self.wall_thickness * 0.001
        
        volume = 0.5 * width_m * height_m * thickness_m
        
        if material:
            material_props = self.materials_db.get_material_properties(material)
            density = material_props["density"]
        else:
            density = self.density
        
        return volume * density
    
    def calculate_fin_mmoi(self, height_mm=None, width_mm=None, mass=None):
        if height_mm is None:
            height_mm = self.fin_height
        if width_mm is None:
            width_mm = self.fin_width
        if height_mm is None or width_mm is None:
            return 0
        if mass is None:
            mass = self.calculate_fin_mass(height_mm, width_mm)
        if mass is None:
            return 0
            
        height_m = height_mm * 0.001
        width_m = width_mm * 0.001
        
        cm_distance_from_center = self.radius_fuselage + width_m/3
        I_cm = (mass/18) * (width_m**2 + height_m**2)
        I_fin = I_cm + mass * cm_distance_from_center**2
        
        return I_fin
    
    def calculate_fin_dimensions(self, verbose=False):
        start_time = time.time()
        
        if self.material_name in self.material_dimensions:
            cached_dims = self.material_dimensions[self.material_name]
            self.fin_area = cached_dims["area"]
            self.fin_height = cached_dims["height"]
            self.fin_width = cached_dims["width"]
            self.fin_mass = cached_dims["mass"]
            self.radial_fin_length = cached_dims["radial_length"]
            
            if verbose:
                print(f"Using cached dimensions for {self.material_name}")
                print(f"Fin area: {self.fin_area:.6f} m^2")
                print(f"Fin height: {self.fin_height:.2f} mm")
                print(f"Fin width: {self.fin_width:.2f} mm")
                print(f"Total mass of {self.num_fins} fins: {self.fin_mass * self.num_fins:.4f} kg")
                print(f"Using dynamic pressure (max_q): {self.max_q:.1f} Pa")
                print(f"Calculation time: {time.time() - start_time:.4f} seconds (cached)")
            
            return self.fin_area, self.fin_height, self.fin_width, self.fin_mass
        
        m_empty = self.masses()
        
        if verbose:
            components, total_mass = self.load_component_data()
            if components and total_mass > 0:
                dry_mass = 0
                propellant_mass = 0
                for name, data in components.items():
                    if "propellant" in name.lower():
                        propellant_mass += data["mass"]
                    else:
                        dry_mass += data["mass"]
                
                print(f"Using team component data for mass calculation: {dry_mass + self.m_payload + propellant_mass:.3f} kg")
                print(f"  Dry mass: {dry_mass + self.m_payload:.3f} kg")
                print(f"  Propellant: {propellant_mass:.3f} kg")
            else:
                print(f"No team data found. Using legacy mass calculation: {m_empty:.3f} kg")
            print(f"Using dynamic pressure (max_q) for calculations: {self.max_q:.1f} Pa")
        
        self.fin_height = None
        self.fin_width = None
        current_radial_fin_length = self.radial_fin_length
        
        I_body = 0.5 * m_empty * self.radius_fuselage**2
        
        for i in range(self.max_iter):
            r_fin = self.radius_fuselage + current_radial_fin_length
            
            if self.fin_height is not None and self.fin_width is not None:
                fin_mass = self.calculate_fin_mass()
                I_single_fin = self.calculate_fin_mmoi()
                I_fins = self.num_fins * I_single_fin
                I_total = I_body + I_fins
            else:
                I_total = I_body
            
            angular_accelerations = np.array([self.min_rad, self.max_rad])
            forces = (I_total * angular_accelerations) / (r_fin * self.dt)
            min_F, max_F = forces
            
            if verbose and i % 5 == 0:
                print(f"Iteration {i+1}: Min and max Force: {min_F:.3f} N, {max_F:.3f} N")
            
            avg_F = (min_F + max_F) * 0.5
            A = avg_F / (self.max_q * self._cl) 
            
            H = np.sqrt((2 * A) / self._geom_ratio) * 1000
            W = H * self._geom_ratio  # mm
            new_radial_fin_length = W * 0.0005
            
            if self.fin_height is not None:
                height_diff = abs(H - self.fin_height)
                width_diff = abs(W - self.fin_width)
                
                if verbose and i % 10 == 0:
                    print(f"  Height diff: {height_diff:.5f} mm, Width diff: {width_diff:.5f} mm")
                
                if height_diff < self.tol and width_diff < self.tol:
                    if verbose:
                        print(f"Converged after {i+1} iterations")
                    break
            
            self.fin_height = H
            self.fin_width = W
            current_radial_fin_length = new_radial_fin_length
        else:
            if verbose:
                print("Warning: Iteration did not converge after maximum iterations.")
        
        self.fin_mass = self.calculate_fin_mass()
        self.radial_fin_length = current_radial_fin_length
        self.fin_area = A
        self.material_dimensions[self.material_name] = {
            "area": self.fin_area,
            "height": self.fin_height,
            "width": self.fin_width,
            "mass": self.fin_mass,
            "radial_length": self.radial_fin_length
        }
        
        if verbose:
            print(f"\nFinal fin area: {self.fin_area:.6f} m^2")
            print(f"Final fin height: {self.fin_height:.2f} mm")
            print(f"Final fin width: {self.fin_width:.2f} mm")
            print(f"Total mass of {self.num_fins} fins: {self.fin_mass * self.num_fins:.4f} kg")
            print(f"Pressure due to maneuver: {avg_F/self.fin_area:.3f} Pa")
            
            # Calculate final MMOI components for output
            I_single_fin = self.calculate_fin_mmoi()
            I_fins = self.num_fins * I_single_fin
            I_total = I_body + I_fins
            
            print(f"\nMMOI of body: {I_body:.6f} kg·m^2")
            print(f"MMOI of all fins: {I_fins:.6f} kg·m^2")
            print(f"Fins contribute {I_fins/I_total*100:.2f}% of total MMOI")
            print(f"Calculation time: {time.time() - start_time:.4f} seconds")
        
        return self.fin_area, self.fin_height, self.fin_width, self.fin_mass
    
    def calculate_all_material_dimensions(self, verbose=False):
        start_time = time.time()
        current_material = self.material_name
        
        materials = self.get_available_materials()
        if verbose:
            print(f"Calculating fin dimensions for {len(materials)} materials...")
        
        results = []
        
        _ = self.masses()
        
        for i, material in enumerate(materials):
            material_start = time.time()
            if verbose:
                print(f"\nCalculating for {material} ({i+1}/{len(materials)}):")
            
            self.set_material(material)
            area, height, width, mass = self.calculate_fin_dimensions(verbose=False)  # Suppress individual verbose output
            material_props = self.materials_db.get_material_properties(material)

            results.append({
                "Material": material,
                "Area (m²)": area,
                "Height (mm)": height,
                "Width (mm)": width,
                "Mass per fin (kg)": mass,
                "Total mass (kg)": mass * self.num_fins,
                "Density (kg/m³)": material_props["density"],
                "Thermal Conductivity (W/m·K)": material_props["thermal_conductivity"],
                "Max Service Temp (K)": material_props["max_service_temp"]
            })
            
            if verbose:
                print(f"  Completed in {time.time() - material_start:.3f}s")
        
        self.set_material(current_material)
        self.all_materials_data = pd.DataFrame(results)
        
        if verbose:
            print(f"\nAll materials calculated in {time.time() - start_time:.3f} seconds")
            print("\nSummary of fin dimensions for all materials:")
            print(self.all_materials_data[["Material", "Height (mm)", "Width (mm)", "Total mass (kg)"]])
        return self.all_materials_data
    
    def get_material_specific_dimensions(self, material_name):
        if material_name not in self.material_dimensions:
            current_material = self.material_name
            self.set_material(material_name)
            self.calculate_fin_dimensions(verbose=False)
            self.set_material(current_material)
        return self.material_dimensions[material_name]
    
    def get_all_material_dimensions(self):
        if self.all_materials_data is None:
            self.calculate_all_material_dimensions()
        return self.all_materials_data
    
    def clear_caches(self):
        self._masses_cache = None
        self._component_data_cache = None
        self.material_dimensions.clear()
        self.all_materials_data = None

def main():
    start_time = time.time()
    fin = RocketFin()

    print("Available materials:")
    for material in fin.get_available_materials():
        print(f"- {material}")

    components, total_mass = fin.load_component_data()
    if components:
        print("\nTeam component data found:")
        print(f"Total component mass: {total_mass:.3f} kg")
        print("Components:")
        
        teams = {}
        for name, data in components.items():
            team = data.get('team', 'unknown')
            if team not in teams:
                teams[team] = []
            teams[team].append((name, data['mass']))
        
        for team, comps in teams.items():
            print(f"\n{team.capitalize()} team components:")
            for name, mass in comps:
                print(f"- {name}: {mass} kg")
    else:
        print("\nNo team component data found. Using legacy mass calculations.")

    print(f"\nComponent data loading time: {time.time() - start_time:.3f} seconds")
    
    calc_start = time.time()
    fin.calculate_all_material_dimensions(verbose=True)
    print(f"All materials calculation time: {time.time() - calc_start:.3f} seconds")
    
    fin.velocity = 1273.011  # m/s
    fin.altitude = 20770.795  # m

    titanium_dims = fin.get_material_specific_dimensions("Titanium Ti-6Al-4V")
    print(f"\nTitanium dimensions: {titanium_dims['height']:.2f}mm x {titanium_dims['width']:.2f}mm")
    
    print(f"Total execution time: {time.time() - start_time:.3f} seconds")

if __name__ == "__main__":
    main()