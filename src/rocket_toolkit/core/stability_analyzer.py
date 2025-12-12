import numpy as np
import os
import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.path import Path
from src.rocket_toolkit.geometry.component_manager import ComponentData

config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

class RocketStability:
    def __init__(self):
        # Load component data from teams if available
        self.component_manager = ComponentData()
        #self.component_manager.update_from_team_files()
        self.components = self.component_manager.get_component_data()
        self.length = config["rocket"]["length"]
        self.diameter = config["rocket"]["diameter"]
        self.radius = self.diameter / 2
        self.nose_cone_length = config["rocket"]["nose_cone_length"]
        self.nose_cone_shape = config["rocket"]["nose_cone_shape"]
        self.fin_height = None
        self.fin_width = None
        self.fin_sweep = None
        self.fin_position = None
        self.num_fins = None
        self.mach = None
        self.alpha = 2.0  
        self.aoa_rad = np.radians(self.alpha) 
        if self.components:
            self.component_masses = {}
            for component_name, component_data in self.components.items():
                if component_name in ["propellant", "nose_cone", "fuselage", "nozzle", "engine", "recovery"]:
                    self.component_masses[component_name] = {
                        "mass": component_data["mass"],
                        "position": component_data.get("position", 
                                                     getattr(config, f"{component_name}_cg_position", 
                                                            getattr(config, f"{component_name}_position", 0)))
                    }
            
            if "fins" not in self.component_masses:
                self.component_masses["fins"] = {
                    "mass": None,
                    "position": config["mass_properties"]["fin_set_cg_position"]
                }
                
            if "propellant" in self.component_masses:
                self.component_masses["propellant"]["current_mass"] = self.component_masses["propellant"]["mass"]
        else:
            self.component_masses = {
                "nose_cone": {
                    "mass": config["mass_properties"]["nose_cone_mass"],
                    "position": config["mass_properties"]["nose_cone_cg_position"]
                },
                "fuselage": {
                    "mass": config["mass_properties"]["fuselage_mass"],
                    "position": config["mass_properties"]["fuselage_cg_position"]
                },
                "fins": {
                    "mass": None, 
                    "position": config["mass_properties"]["fin_set_cg_position"]
                },
                "nozzle": {
                    "mass": config["mass_properties"]["nozzle_mass"],
                    "position": config["mass_properties"]["nozzle_cg_position"]
                },
                "engine": {
                    "mass": config["mass_properties"]["engine_mass"],
                    "position": config["mass_properties"]["engine_cg_position"]
                },
                "propellant": {
                    "mass": config["mass_properties"]["propellant_mass"],
                    "position": config["mass_properties"]["propellant_cg_position"],
                    "current_mass": config["mass_properties"]["propellant_mass"]
                },
                "recovery": {
                    "mass": config["mass_properties"]["recovery_system_mass"],
                    "position": config["mass_properties"]["recovery_system_cg_position"]
                }
            }
        
        self.center_of_mass = None
        self.center_of_pressure = None
        self.stability_margin = None
        self.stability_calibers = None
        
    def set_fin_properties(self, rocket_fin):
        self.fin_height = rocket_fin.fin_height / 1000 if rocket_fin.fin_height else 0.05
        self.fin_width = rocket_fin.fin_width / 1000 if rocket_fin.fin_width else 0.1
        self.num_fins = rocket_fin.num_fins if hasattr(rocket_fin, 'num_fins') else 4
        if hasattr(rocket_fin, 'fin_mass') and rocket_fin.fin_mass:
            fin_mass = rocket_fin.fin_mass * self.num_fins
        else:
            fin_mass = 0.2 
            
        if "fins" in self.component_masses:
            self.component_masses["fins"]["mass"] = fin_mass
        self.fin_sweep = self.fin_width * 0.6
        self.fin_position = self.length - self.fin_width
    
    def set_flight_conditions(self, mach, alpha=None):
        self.mach = mach
        if alpha is not None:
            self.alpha = alpha
            self.aoa_rad = np.radians(self.alpha)
    
    def set_propellant_mass(self, current_propellant_mass):
        if "propellant" in self.component_masses:
            self.component_masses["propellant"]["current_mass"] = current_propellant_mass
    
    def calculate_center_of_mass(self):
        total_mass = 0
        mass_moment = 0
        for component, data in self.component_masses.items():
            if component == "propellant":
                mass = data["current_mass"]
            else:
                mass = data["mass"]
            if mass is not None:
                position = data["position"]
                mass_moment += mass * position
                total_mass += mass
        if total_mass > 0:
            self.center_of_mass = mass_moment / total_mass
        else:
            self.center_of_mass = self.length / 2
        return self.center_of_mass
    
    def calculate_center_of_pressure(self):
        if self.nose_cone_shape == "conical":
            cp_nose = self.nose_cone_length * 0.466
            cn_nose = 2.0
        elif self.nose_cone_shape == "ogive":
            cp_nose = self.nose_cone_length * 0.466
            cn_nose = 2.0
        else:  # Default to elliptical
            cp_nose = self.nose_cone_length * 0.466
            cn_nose = 2.0
            
        cn_nose_moment = cn_nose * cp_nose
        body_length = self.length - self.nose_cone_length
        cn_body = 1.1 * self.aoa_rad * body_length / self.diameter if self.aoa_rad > 0 else 0
        body_cp = self.nose_cone_length + (body_length * 0.6)  # CP at 60% of body length
        cn_body_moment = cn_body * body_cp
        fin_area = 0.5 * self.fin_width * self.fin_height
        total_fin_area = fin_area * self.num_fins
        mac = self.fin_width * 0.7
        cp_fin = self.fin_position + mac
        interference_factor = 1.5  
        fin_effect_multiplier = 2.0  
        cn_fin = interference_factor * fin_effect_multiplier * total_fin_area / (np.pi * self.radius**2) * 4
        cn_fin_moment = cn_fin * cp_fin
        boat_tail_length = getattr(self, 'boat_tail_length', self.length * 0.05)
        boat_tail_position = self.length - boat_tail_length / 2
        cn_boat_tail = -0.3
        cn_boat_tail_moment = cn_boat_tail * boat_tail_position
        cn_total = cn_nose + cn_body + cn_fin + cn_boat_tail
        cn_moment_total = cn_nose_moment + cn_body_moment + cn_fin_moment + cn_boat_tail_moment
        if cn_total > 0:
            self.center_of_pressure = cn_moment_total / cn_total
        else:
            self.center_of_pressure = self.length * 0.7  
        if self.center_of_pressure < 1.0:  
            cp_correction = self.length * 0.2 
            self.center_of_pressure += cp_correction
        
        return self.center_of_pressure
    
    def calculate_stability(self):
        if self.center_of_mass is None:
            self.calculate_center_of_mass()
            
        if self.center_of_pressure is None:
            self.calculate_center_of_pressure()
            
        self.stability_margin = self.center_of_pressure - self.center_of_mass
        self.stability_calibers = self.stability_margin / self.diameter
        
        return {
            "margin": self.stability_margin,
            "calibers": self.stability_calibers
        }
    
    def get_stability_status(self):
        if self.stability_calibers is None:
            self.calculate_stability()
            
        if self.stability_calibers < 0:
            return "unstable"
        elif self.stability_calibers < config["stability"]["min_caliber_stability"]:
            return "marginally stable"
        elif self.stability_calibers > config["stability"]["max_caliber_stability"]:
            return "overstable"
        else:
            return "stable"
    
    def plot_stability_diagram(self, show_components=True):
        if self.center_of_mass is None:
            self.calculate_center_of_mass()
        if self.center_of_pressure is None:
            self.calculate_center_of_pressure()
        if self.stability_calibers is None:
            self.calculate_stability()
        if hasattr(config, 'show_rocket_configuration') and config["visualisation"]["show_rocket_configuration"] == "1D":
            return self._plot_1d_stability()
        else:
            return self._plot_2d_stability(show_components)
    
    def _plot_1d_stability(self):
        fig, ax = plt.subplots(figsize=(10, 2))
        ax.plot([0, self.length], [0, 0], 'k-', linewidth=2)
        ax.plot(self.center_of_mass, 0, 'bo', markersize=10, label='Center of Mass')
        ax.plot(self.center_of_pressure, 0, 'ro', markersize=10, label='Center of Pressure')
        stability_status = self.get_stability_status()
        ax.text(0.05, 0.5, 
                f"Stability Margin: {self.stability_margin:.3f} m\n"
                f"Stability: {self.stability_calibers:.2f} calibers\n"
                f"Status: {stability_status}",
                transform=ax.transAxes,
                bbox=dict(facecolor='white', alpha=0.7))
        ax.set_xlim(-0.1, self.length * 1.1)
        ax.set_ylim(-0.5, 0.5)
        ax.set_xlabel('Distance from Nose Tip (m)')
        ax.set_title('Rocket Stability Diagram')
        ax.legend()
        ax.set_yticks([])
        plt.tight_layout()
        return fig, ax
    
    def _plot_2d_stability(self, show_components=True):
        fig, ax = plt.subplots(figsize=(12, 4))
        self._draw_rocket_2d(ax)
        if show_components and config["visualisation"]["show_component_cgs"]:
            self._draw_component_cgs(ax)
        
        ax.plot(self.center_of_mass, 0, 'bo', markersize=10, label='Center of Mass')
        ax.plot(self.center_of_pressure, 0, 'ro', markersize=10, label='Center of Pressure')
        
        if config["visualisation"]["show_stability_margin"]:
            self._draw_stability_margin(ax)
        
        stability_status = self.get_stability_status()
        info_text = (f"Stability Margin: {self.stability_margin:.3f} m\n"
                    f"Stability: {self.stability_calibers:.2f} calibers\n"
                    f"Status: {stability_status}")
                    
        if self.stability_calibers < 0:
            info_color = 'red'
        elif self.stability_calibers < config["stability"]["min_caliber_stability"]:
            info_color = 'orange'
        elif self.stability_calibers > config["stability"]["max_caliber_stability"]:
            info_color = 'orange'
        else:
            info_color = 'green'
            
        ax.text(0.02, 0.95, info_text,
                transform=ax.transAxes, verticalalignment='top',
                bbox=dict(facecolor='white', alpha=0.7, boxstyle='round'),
                color=info_color)
        
        ax.set_xlim(-0.1, self.length * 1.1)
        ax.set_ylim(-self.diameter * 1.5, self.diameter * 1.5)
        ax.set_xlabel('Distance from Nose Tip (m)')
        ax.set_title('Rocket Stability Diagram')
        ax.legend(loc='lower right')
        ax.set_aspect('equal')
        plt.tight_layout()
        return fig, ax
        
    def _draw_rocket_2d(self, ax):
        nose_x = np.linspace(0, self.nose_cone_length, 20)
        
        if self.nose_cone_shape == "conical":
            nose_y = np.linspace(0, self.radius, 20)
        elif self.nose_cone_shape == "ogive":
            rho = (self.radius**2 + self.nose_cone_length**2) / (2 * self.radius)
            y_offset = np.sqrt(rho**2 - self.nose_cone_length**2)
            nose_y = np.sqrt(rho**2 - (self.nose_cone_length - nose_x)**2) - y_offset
        else:
            nose_y = self.radius * np.sqrt(1 - (nose_x / self.nose_cone_length)**2)
        
        nose_y_bottom = -nose_y
        ax.plot(nose_x, nose_y, 'k-', linewidth=2)
        ax.plot(nose_x, nose_y_bottom, 'k-', linewidth=2)
        body_x = [self.nose_cone_length, self.length]
        body_y_top = [self.radius, self.radius]
        body_y_bottom = [-self.radius, -self.radius]
        ax.plot(body_x, body_y_top, 'k-', linewidth=2)
        ax.plot(body_x, body_y_bottom, 'k-', linewidth=2)
        ax.plot([self.length, self.length], [self.radius, -self.radius], 'k-', linewidth=2)
        if self.fin_height and self.fin_width:
            fin_x_top = np.array([
                self.fin_position,
                self.fin_position + self.fin_sweep,
                self.fin_position + self.fin_width,
                self.fin_position
            ])
            fin_y_top = np.array([
                self.radius,
                self.radius + self.fin_height,
                self.radius,
                self.radius
            ])
            
            fin_x_bottom = fin_x_top.copy()
            fin_y_bottom = -fin_y_top + 2 * (-self.radius)
            if self.num_fins >= 3:
                fin_x_side = fin_x_top.copy()
                fin_y_side_left = np.zeros_like(fin_x_side)
                fin_y_side_right = np.zeros_like(fin_x_side)
                visible_height = self.fin_height * 0.3 
                fin_y_side_left = np.array([
                    self.radius * 0.5,
                    self.radius * 0.5 + visible_height,
                    self.radius * 0.5,
                    self.radius * 0.5
                ])
                
                fin_y_side_right = -fin_y_side_left
                if self.num_fins >= 3:
                    ax.plot(fin_x_side, fin_y_side_left, 'k-', linewidth=1.5)
                    ax.fill(fin_x_side, fin_y_side_left, color='lightgray', alpha=0.4)
                
                if self.num_fins >= 4:
                    ax.plot(fin_x_side, fin_y_side_right, 'k-', linewidth=1.5)
                    ax.fill(fin_x_side, fin_y_side_right, color='lightgray', alpha=0.4)
            ax.plot(fin_x_top, fin_y_top, 'k-', linewidth=2)
            ax.fill(fin_x_top, fin_y_top, color='lightgray', alpha=0.6)
            ax.plot(fin_x_bottom, fin_y_bottom, 'k-', linewidth=2)
            ax.fill(fin_x_bottom, fin_y_bottom, color='lightgray', alpha=0.6)
    
    def _draw_component_cgs(self, ax):
        for component, data in self.component_masses.items():
            if component == "propellant":
                mass = data["current_mass"]
            else:
                mass = data["mass"]
                
            if mass and mass > 0:
                position = data["position"]
                marker_size = 30 * (mass / 2) 
                ax.plot(position, 0, 'gx', markersize=marker_size)
                ax.text(position, -self.radius/2, component, 
                        ha='center', va='center', fontsize=8,
                        bbox=dict(facecolor='white', alpha=0.7))
    
    def _draw_stability_margin(self, ax):
        if self.stability_margin > 0:
            arrow_props = dict(
                arrowstyle='<->',
                color='green',
                lw=2
            )
            ax.annotate('', 
                       xy=(self.center_of_pressure, self.radius/2), 
                       xytext=(self.center_of_mass, self.radius/2),
                       arrowprops=arrow_props)
            midpoint = (self.center_of_mass + self.center_of_pressure) / 2
            ax.text(midpoint, self.radius/2 + 0.02, 
                    f"{self.stability_margin:.3f} m\n{self.stability_calibers:.2f} cal",
                    ha='center', va='bottom', color='green',
                    bbox=dict(facecolor='white', alpha=0.7))
        else:
            arrow_props = dict(
                arrowstyle='<->',
                color='red',
                lw=2
            )
            ax.annotate('', 
                       xy=(self.center_of_mass, self.radius/2), 
                       xytext=(self.center_of_pressure, self.radius/2),
                       arrowprops=arrow_props)
            midpoint = (self.center_of_mass + self.center_of_pressure) / 2
            ax.text(midpoint, self.radius/2 + 0.02, 
                    f"{abs(self.stability_margin):.3f} m\n{self.stability_calibers:.2f} cal",
                    ha='center', va='bottom', color='red',
                    bbox=dict(facecolor='white', alpha=0.7))
    

def plot_rocket_stability(rocket_fin=None, current_mass=None, mach=None):
    stability = RocketStability()
    if rocket_fin:
        stability.set_fin_properties(rocket_fin)
    if mach:
        stability.set_flight_conditions(mach)
    if current_mass is not None:
        stability.set_propellant_mass(current_mass)
    stability.calculate_center_of_mass()
    stability.calculate_center_of_pressure()
    stability.calculate_stability()
    show_components = True
    if hasattr(config, 'show_component_cgs'):
        show_components = config["visualisation"]["show_component_cgs"]
    
    fig, ax = stability.plot_stability_diagram(show_components=show_components)
    
    return fig, ax

def main():
    from rocket_fin_dimensions import RocketFin
    from component_manager import ComponentData
    component_manager = ComponentData()
    '''
    component_manager.update_from_team_files()
    component_manager.update_config(config)
    component_manager.print_component_summary()
    '''
    fin = RocketFin()
    fin.calculate_fin_dimensions(verbose=True)
    propellant_mass = component_manager.get_component_data().get("propellant", {}).get("mass", config["mass_properties"]["propellant_mass"])
    print("\nStability with full propellant load:")
    fig, ax = plot_rocket_stability(
        rocket_fin=fin,
        current_mass=propellant_mass,
        mach=0.1
    )
    
    print("\nStability with half propellant load:")
    fig, ax = plot_rocket_stability(
        rocket_fin=fin,
        current_mass=propellant_mass * 0.5,  
        mach=2.0
    )
    
    print("\nStability with empty propellant load:")
    fig, ax = plot_rocket_stability(
        rocket_fin=fin,
        current_mass=0.0, 
        mach=0.5 
    )
    propellant_fractions = [1.0, 0.75, 0.5, 0.25, 0.0]
    
    fig, axes = plt.subplots(len(propellant_fractions), 1, figsize=(12, 4*len(propellant_fractions)))
    total_propellant = propellant_mass
    
    for i, fraction in enumerate(propellant_fractions):
        current_mass = total_propellant * fraction
        
        stability = RocketStability()
        stability.set_fin_properties(fin)
        stability.set_flight_conditions(mach=2.0)
        stability.set_propellant_mass(current_mass)
        stability.calculate_center_of_mass()
        stability.calculate_center_of_pressure()
        stability.calculate_stability()
        stability._draw_rocket_2d(axes[i])
        axes[i].plot(stability.center_of_mass, 0, 'bo', markersize=10, label='Center of Mass')
        axes[i].plot(stability.center_of_pressure, 0, 'ro', markersize=10, label='Center of Pressure')
        stability._draw_stability_margin(axes[i])
        axes[i].set_title(f"Propellant remaining: {fraction*100:.0f}% - Stability: {stability.stability_calibers:.2f} calibers")
        axes[i].set_xlim(-0.1, stability.length * 1.1)
        axes[i].set_ylim(-stability.diameter, stability.diameter)
        axes[i].set_aspect('equal')
        
        if i == len(propellant_fractions) - 1:
            axes[i].set_xlabel('Distance from Nose Tip (m)')
        
        axes[i].legend(loc='lower right')
    
    plt.tight_layout()

if __name__ == "__main__":
    main()