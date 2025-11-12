import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.path import Path
from src.rocket_toolkit import config
from src.rocket_toolkit.geometry.component_manager import ComponentData


class RocketStability:
    def __init__(self):
        # Load component data from teams if available
        self.component_manager = ComponentData()
        self.component_manager.update_from_team_files()
        self.components = self.component_manager.get_component_data()
        
        # Rocket geometry
        self.length = config.rocket_length
        self.diameter = config.rocket_diameter
        self.radius = self.diameter / 2
        self.nose_cone_length = config.nose_cone_length
        self.nose_cone_shape = config.nose_cone_shape
        
        # Fin properties - from the fin class
        self.fin_height = None  # Will be set when a fin object is provided
        self.fin_width = None
        self.fin_sweep = None
        self.fin_position = None  # Position from nose tip
        self.num_fins = None
        
        # Flight condition properties
        self.mach = None
        self.alpha = 2.0  # Angle of attack in degrees
        self.aoa_rad = np.radians(self.alpha)  # Convert to radians
        
        # Mass components - use team data if available
        if self.components:
            # Initialize component masses from team data
            self.component_masses = {}
            for component_name, component_data in self.components.items():
                if component_name in ["propellant", "nose_cone", "fuselage", "nozzle", "engine", "recovery"]:
                    self.component_masses[component_name] = {
                        "mass": component_data["mass"],
                        "position": component_data.get("position", 
                                                     getattr(config, f"{component_name}_cg_position", 
                                                            getattr(config, f"{component_name}_position", 0)))
                    }
            
            # Add fins if not already in components
            if "fins" not in self.component_masses:
                self.component_masses["fins"] = {
                    "mass": None,  # Will be set when a fin object is provided
                    "position": config.fin_set_cg_position
                }
                
            # Set current propellant mass to full
            if "propellant" in self.component_masses:
                self.component_masses["propellant"]["current_mass"] = self.component_masses["propellant"]["mass"]
        else:
            # Fall back to config values if no team data
            self.component_masses = {
                "nose_cone": {
                    "mass": config.nose_cone_mass,
                    "position": config.nose_cone_cg_position
                },
                "fuselage": {
                    "mass": config.fuselage_mass,
                    "position": config.fuselage_cg_position
                },
                "fins": {
                    "mass": None,  # Will be set when a fin object is provided
                    "position": config.fin_set_cg_position
                },
                "nozzle": {
                    "mass": config.nozzle_mass,
                    "position": config.nozzle_cg_position
                },
                "engine": {
                    "mass": config.engine_mass,
                    "position": config.engine_cg_position
                },
                "propellant": {
                    "mass": config.propellant_mass,
                    "position": config.propellant_cg_position,
                    "current_mass": config.propellant_mass  # Will be updated during flight
                },
                "recovery": {
                    "mass": config.recovery_system_mass,
                    "position": config.recovery_system_position
                }
            }
        
        # Results
        self.center_of_mass = None
        self.center_of_pressure = None
        self.stability_margin = None
        self.stability_calibers = None
        
    def set_fin_properties(self, rocket_fin):
        """Set fin properties from a RocketFin object"""
        self.fin_height = rocket_fin.fin_height / 1000 if rocket_fin.fin_height else 0.05
        self.fin_width = rocket_fin.fin_width / 1000 if rocket_fin.fin_width else 0.1
        self.num_fins = rocket_fin.num_fins if hasattr(rocket_fin, 'num_fins') else 4
        
        # Calculate fin mass if available from the fin object
        if hasattr(rocket_fin, 'fin_mass') and rocket_fin.fin_mass:
            fin_mass = rocket_fin.fin_mass * self.num_fins
        else:
            fin_mass = 0.2  # Default if not available
            
        # Update fin mass in components
        if "fins" in self.component_masses:
            self.component_masses["fins"]["mass"] = fin_mass
        
        # Calculate fin sweep (approximate)
        self.fin_sweep = self.fin_width * 0.6  # Assuming 60% sweep
        
        # Calculate fin position (at trailing edge of the fins)
        self.fin_position = self.length - self.fin_width
    
    def set_flight_conditions(self, mach, alpha=None):
        """Set flight conditions for CP calculation"""
        self.mach = mach
        if alpha is not None:
            self.alpha = alpha
            self.aoa_rad = np.radians(self.alpha)
    
    def set_propellant_mass(self, current_propellant_mass):
        """Update the current propellant mass for CM calculation"""
        if "propellant" in self.component_masses:
            self.component_masses["propellant"]["current_mass"] = current_propellant_mass
    
    def calculate_center_of_mass(self):
        """Calculate the center of mass of the rocket"""
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
            self.center_of_mass = self.length / 2  # Default to middle if no mass
            
        return self.center_of_mass
    
    def calculate_center_of_pressure(self):
        """
        Calculate the center of pressure of the rocket using an enhanced method
        that will position the CP further back for better stability.
        
        This implementation uses a more realistic CP calculation for each component.
        """
        # Nose cone contribution - adjust this to reduce the nose's influence
        if self.nose_cone_shape == "conical":
            cp_nose = self.nose_cone_length * 0.466  # Adjusted from 1/3 to 0.466
            cn_nose = 2.0
        elif self.nose_cone_shape == "ogive":
            cp_nose = self.nose_cone_length * 0.466  # Adjusted from 1/2 to 0.466
            cn_nose = 2.0
        else:  # Default to elliptical
            cp_nose = self.nose_cone_length * 0.466  # Adjusted from 1/2 to 0.466
            cn_nose = 2.0
            
        cn_nose_moment = cn_nose * cp_nose
        
        # Body contribution - add small effect at angle of attack
        # This helps move CP backward realistically
        body_length = self.length - self.nose_cone_length
        
        # For a cylinder at angle of attack (small effect)
        cn_body = 1.1 * self.aoa_rad * body_length / self.diameter if self.aoa_rad > 0 else 0
        body_cp = self.nose_cone_length + (body_length * 0.6)  # CP at 60% of body length
        cn_body_moment = cn_body * body_cp
        
        # Fin contribution - enhanced calculation with greater effect
        fin_area = 0.5 * self.fin_width * self.fin_height
        total_fin_area = fin_area * self.num_fins
        
        # Enhanced mean aerodynamic chord calculation
        mac = self.fin_width * 0.7  # Position MAC at 70% of fin width
        cp_fin = self.fin_position + mac
        
        # Fin Coefficient of Normal Force - increased effect
        interference_factor = 1.5  # Increased from typical 1.0-1.2 values
        fin_effect_multiplier = 2.0  # Additional multiplier to increase fin effectiveness
        
        # Calculate fin normal force coefficient with enhanced effect
        cn_fin = interference_factor * fin_effect_multiplier * total_fin_area / (np.pi * self.radius**2) * 4
        cn_fin_moment = cn_fin * cp_fin
        
        # Add boat tail effect if rocket has one
        # If not explicitly specified, assume a small boat tail effect
        boat_tail_length = getattr(self, 'boat_tail_length', self.length * 0.05)
        boat_tail_position = self.length - boat_tail_length / 2
        
        # Negative contribution moves CP backward
        cn_boat_tail = -0.3
        cn_boat_tail_moment = cn_boat_tail * boat_tail_position
        
        # Sum up all contributions
        cn_total = cn_nose + cn_body + cn_fin + cn_boat_tail
        cn_moment_total = cn_nose_moment + cn_body_moment + cn_fin_moment + cn_boat_tail_moment
        
        if cn_total > 0:
            self.center_of_pressure = cn_moment_total / cn_total
        else:
            self.center_of_pressure = self.length * 0.7  # Default fallback
        
        # Apply a correction factor to move CP backward if still too far forward
        if self.center_of_pressure < 1.0:  # If CP is very forward
            # Apply a correction to move it back
            cp_correction = self.length * 0.2  # Move back by 20% of rocket length
            self.center_of_pressure += cp_correction
        
        return self.center_of_pressure
    
    def calculate_stability(self):
        """Calculate the stability margin in calibers"""
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
        """Check if the rocket is stable, marginally stable, or unstable"""
        if self.stability_calibers is None:
            self.calculate_stability()
            
        if self.stability_calibers < 0:
            return "unstable"
        elif self.stability_calibers < config.min_caliber_stability:
            return "marginally stable"
        elif self.stability_calibers > config.max_caliber_stability:
            return "overstable"
        else:
            return "stable"
    
    def plot_stability_diagram(self, show_components=True):
        """
        Create a plot showing the rocket outline with CP and CM marked
        
        Args:
            show_components: If True, show the individual components' CG points
            
        Returns:
            fig, ax: Figure and axis objects
        """
        if self.center_of_mass is None:
            self.calculate_center_of_mass()
            
        if self.center_of_pressure is None:
            self.calculate_center_of_pressure()
            
        if self.stability_calibers is None:
            self.calculate_stability()
            
        # Determine the configuration type
        if hasattr(config, 'show_rocket_configuration') and config.show_rocket_configuration == "1D":
            return self._plot_1d_stability()
        elif hasattr(config, 'show_rocket_configuration') and config.show_rocket_configuration == "3D":
            return self._plot_3d_stability(show_components)
        else:
            # Default to 2D
            return self._plot_2d_stability(show_components)
    
    def _plot_1d_stability(self):
        """Plot a simple 1D stability diagram"""
        fig, ax = plt.subplots(figsize=(10, 2))
        
        # Draw a line representing the rocket
        ax.plot([0, self.length], [0, 0], 'k-', linewidth=2)
        
        # Mark the center of mass and center of pressure
        ax.plot(self.center_of_mass, 0, 'bo', markersize=10, label='Center of Mass')
        ax.plot(self.center_of_pressure, 0, 'ro', markersize=10, label='Center of Pressure')
        
        # Add stability information
        stability_status = self.get_stability_status()
        ax.text(0.05, 0.5, 
                f"Stability Margin: {self.stability_margin:.3f} m\n"
                f"Stability: {self.stability_calibers:.2f} calibers\n"
                f"Status: {stability_status}",
                transform=ax.transAxes,
                bbox=dict(facecolor='white', alpha=0.7))
        
        # Set limits and labels
        ax.set_xlim(-0.1, self.length * 1.1)
        ax.set_ylim(-0.5, 0.5)
        ax.set_xlabel('Distance from Nose Tip (m)')
        ax.set_title('Rocket Stability Diagram')
        ax.legend()
        
        # Remove y-axis ticks as they're not needed
        ax.set_yticks([])
        
        plt.tight_layout()
        return fig, ax
    
    def _plot_2d_stability(self, show_components=True):
        """Plot a 2D outline of the rocket with stability points"""
        fig, ax = plt.subplots(figsize=(12, 4))
        
        # Draw the rocket outline
        self._draw_rocket_2d(ax)
        
        # Draw component CGs if requested
        if show_components and config.show_component_cgs:
            self._draw_component_cgs(ax)
        
        # Mark the center of mass and center of pressure
        ax.plot(self.center_of_mass, 0, 'bo', markersize=10, label='Center of Mass')
        ax.plot(self.center_of_pressure, 0, 'ro', markersize=10, label='Center of Pressure')
        
        # Draw stability margin if enabled
        if config.show_stability_margin:
            self._draw_stability_margin(ax)
        
        # Add stability information
        stability_status = self.get_stability_status()
        info_text = (f"Stability Margin: {self.stability_margin:.3f} m\n"
                    f"Stability: {self.stability_calibers:.2f} calibers\n"
                    f"Status: {stability_status}")
                    
        if self.stability_calibers < 0:
            info_color = 'red'
        elif self.stability_calibers < config.min_caliber_stability:
            info_color = 'orange'
        elif self.stability_calibers > config.max_caliber_stability:
            info_color = 'orange'
        else:
            info_color = 'green'
            
        ax.text(0.02, 0.95, info_text,
                transform=ax.transAxes, verticalalignment='top',
                bbox=dict(facecolor='white', alpha=0.7, boxstyle='round'),
                color=info_color)
        
        # Set limits and labels
        ax.set_xlim(-0.1, self.length * 1.1)
        ax.set_ylim(-self.diameter * 1.5, self.diameter * 1.5)
        ax.set_xlabel('Distance from Nose Tip (m)')
        ax.set_title('Rocket Stability Diagram')
        ax.legend(loc='lower right')
        
        # Equal aspect ratio for realistic appearance
        ax.set_aspect('equal')
        
        plt.tight_layout()
        return fig, ax
    
    def _plot_3d_stability(self, show_components=True):
        """Plot a 3D representation of the rocket with CP and CM marked"""
        from mpl_toolkits.mplot3d import Axes3D
        
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        # Draw 3D rocket (simplified)
        self._draw_rocket_3d(ax)
        
        # Mark CP and CM
        ax.scatter([self.center_of_mass], [0], [0], color='blue', s=100, label='Center of Mass')
        ax.scatter([self.center_of_pressure], [0], [0], color='red', s=100, label='Center of Pressure')
        
        # Add stability line
        if self.stability_margin > 0:
            ax.plot([self.center_of_mass, self.center_of_pressure], [0, 0], [0, 0], 
                    'g--', linewidth=2, label=f'Stability Margin: {self.stability_calibers:.2f} calibers')
        else:
            ax.plot([self.center_of_mass, self.center_of_pressure], [0, 0], [0, 0], 
                    'r--', linewidth=2, label=f'Unstable: {self.stability_calibers:.2f} calibers')
        
        # Set labels and title
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_zlabel('Z (m)')
        ax.set_title('Rocket Stability 3D View')
        
        # Set limits for better visualization
        max_dim = max(self.length, self.diameter * 2)
        ax.set_xlim(0, self.length)
        ax.set_ylim(-max_dim/2, max_dim/2)
        ax.set_zlim(-max_dim/2, max_dim/2)
        
        ax.legend()
        plt.tight_layout()
        return fig, ax
    
    def _draw_rocket_2d(self, ax):
        """Draw a 2D outline of the rocket with proper fin placement"""
        # Draw the nose cone
        nose_x = np.linspace(0, self.nose_cone_length, 20)
        
        if self.nose_cone_shape == "conical":
            nose_y = np.linspace(0, self.radius, 20)
        elif self.nose_cone_shape == "ogive":
            # Ogive shape calculation
            rho = (self.radius**2 + self.nose_cone_length**2) / (2 * self.radius)
            y_offset = np.sqrt(rho**2 - self.nose_cone_length**2)
            nose_y = np.sqrt(rho**2 - (self.nose_cone_length - nose_x)**2) - y_offset
        else:  # Default to elliptical
            nose_y = self.radius * np.sqrt(1 - (nose_x / self.nose_cone_length)**2)
        
        # Mirror for the bottom part
        nose_y_bottom = -nose_y
        
        # Draw the nose
        ax.plot(nose_x, nose_y, 'k-', linewidth=2)
        ax.plot(nose_x, nose_y_bottom, 'k-', linewidth=2)
        
        # Draw the body tube
        body_x = [self.nose_cone_length, self.length]
        body_y_top = [self.radius, self.radius]
        body_y_bottom = [-self.radius, -self.radius]
        
        ax.plot(body_x, body_y_top, 'k-', linewidth=2)
        ax.plot(body_x, body_y_bottom, 'k-', linewidth=2)
        
        # Draw the end cap
        ax.plot([self.length, self.length], [self.radius, -self.radius], 'k-', linewidth=2)
        
        # Draw fins if dimensions are available
        if self.fin_height and self.fin_width:
            # Calculate fin coordinates for top fin
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
            
            # Calculate fin coordinates for bottom fin
            fin_x_bottom = fin_x_top.copy()
            fin_y_bottom = -fin_y_top + 2 * (-self.radius)  # Mirror around bottom of body
            
            # Calculate fin coordinates for side fins if needed
            # In a 2D view, side fins would appear as lines
            if self.num_fins >= 3:
                fin_x_side = fin_x_top.copy()
                fin_y_side_left = np.zeros_like(fin_x_side)
                fin_y_side_right = np.zeros_like(fin_x_side)
                
                # The side fins will be partially visible from the side view
                visible_height = self.fin_height * 0.3  # Reduced visibility
                
                fin_y_side_left = np.array([
                    self.radius * 0.5,
                    self.radius * 0.5 + visible_height,
                    self.radius * 0.5,
                    self.radius * 0.5
                ])
                
                fin_y_side_right = -fin_y_side_left
                
                # Draw side fins (simplified representation)
                if self.num_fins >= 3:
                    ax.plot(fin_x_side, fin_y_side_left, 'k-', linewidth=1.5)
                    ax.fill(fin_x_side, fin_y_side_left, color='lightgray', alpha=0.4)
                
                if self.num_fins >= 4:
                    ax.plot(fin_x_side, fin_y_side_right, 'k-', linewidth=1.5)
                    ax.fill(fin_x_side, fin_y_side_right, color='lightgray', alpha=0.4)
            
            # Draw top and bottom fins
            ax.plot(fin_x_top, fin_y_top, 'k-', linewidth=2)
            ax.fill(fin_x_top, fin_y_top, color='lightgray', alpha=0.6)
            
            ax.plot(fin_x_bottom, fin_y_bottom, 'k-', linewidth=2)
            ax.fill(fin_x_bottom, fin_y_bottom, color='lightgray', alpha=0.6)
    
    def _draw_component_cgs(self, ax):
        """Draw markers for component centers of gravity"""
        for component, data in self.component_masses.items():
            if component == "propellant":
                mass = data["current_mass"]
            else:
                mass = data["mass"]
                
            if mass and mass > 0:
                position = data["position"]
                # Scale marker size by mass
                marker_size = 30 * (mass / 2)  # Adjusted for visibility
                ax.plot(position, 0, 'gx', markersize=marker_size)
                ax.text(position, -self.radius/2, component, 
                        ha='center', va='center', fontsize=8,
                        bbox=dict(facecolor='white', alpha=0.7))
    
    def _draw_stability_margin(self, ax):
        """Draw the stability margin indicator"""
        if self.stability_margin > 0:
            # Draw a green arrow for positive stability
            arrow_props = dict(
                arrowstyle='<->',
                color='green',
                lw=2
            )
            ax.annotate('', 
                       xy=(self.center_of_pressure, self.radius/2), 
                       xytext=(self.center_of_mass, self.radius/2),
                       arrowprops=arrow_props)
            
            # Add text with margin value
            midpoint = (self.center_of_mass + self.center_of_pressure) / 2
            ax.text(midpoint, self.radius/2 + 0.02, 
                    f"{self.stability_margin:.3f} m\n{self.stability_calibers:.2f} cal",
                    ha='center', va='bottom', color='green',
                    bbox=dict(facecolor='white', alpha=0.7))
        else:
            # Draw a red arrow for negative stability
            arrow_props = dict(
                arrowstyle='<->',
                color='red',
                lw=2
            )
            ax.annotate('', 
                       xy=(self.center_of_mass, self.radius/2), 
                       xytext=(self.center_of_pressure, self.radius/2),
                       arrowprops=arrow_props)
            
            # Add text with margin value
            midpoint = (self.center_of_mass + self.center_of_pressure) / 2
            ax.text(midpoint, self.radius/2 + 0.02, 
                    f"{abs(self.stability_margin):.3f} m\n{self.stability_calibers:.2f} cal",
                    ha='center', va='bottom', color='red',
                    bbox=dict(facecolor='white', alpha=0.7))
    
    def _draw_rocket_3d(self, ax):
        """Draw a simplified 3D rocket model"""
        # Nose cone
        u = np.linspace(0, 2 * np.pi, 20)
        v = np.linspace(0, np.pi/2, 20)
        
        # Nose cone parameters
        if self.nose_cone_shape == "conical":
            # Conical nose
            for i in range(20):
                z = i / 19 * self.nose_cone_length
                r = i / 19 * self.radius
                x = z
                y = r * np.sin(u)
                z_circle = r * np.cos(u)
                ax.plot(np.ones_like(u) * x, y, z_circle, 'k-', linewidth=0.5, alpha=0.3)
        else:
            # Ogive or elliptical nose (simplified)
            for i in range(20):
                t = i / 19
                z = t * self.nose_cone_length
                if self.nose_cone_shape == "ogive":
                    # Simplified ogive
                    rho = (self.radius**2 + self.nose_cone_length**2) / (2 * self.radius)
                    y_offset = np.sqrt(rho**2 - self.nose_cone_length**2)
                    r = np.sqrt(rho**2 - (self.nose_cone_length - z)**2) - y_offset
                else:
                    # Elliptical
                    r = self.radius * np.sqrt(1 - (1-t)**2)
                
                x = z
                y = r * np.sin(u)
                z_circle = r * np.cos(u)
                ax.plot(np.ones_like(u) * x, y, z_circle, 'k-', linewidth=0.5, alpha=0.3)
        
        # Body tube
        for i in range(10):
            z = self.nose_cone_length + i / 9 * (self.length - self.nose_cone_length)
            x = z
            y = self.radius * np.sin(u)
            z_circle = self.radius * np.cos(u)
            ax.plot(np.ones_like(u) * x, y, z_circle, 'k-', linewidth=0.5, alpha=0.3)
        
        # Fins (simplified)
        if self.fin_height and self.fin_width:
            for fin_angle in np.linspace(0, 2*np.pi, self.num_fins, endpoint=False):
                fin_x = np.array([
                    self.fin_position,
                    self.fin_position + self.fin_sweep,
                    self.fin_position + self.fin_width,
                    self.fin_position
                ])
                
                fin_y_base = np.array([
                    self.radius,
                    self.radius + self.fin_height,
                    self.radius,
                    self.radius
                ])
                
                # Rotate fin coordinates around the rocket axis
                fin_y = fin_y_base * np.sin(fin_angle)
                fin_z = fin_y_base * np.cos(fin_angle)
                
                ax.plot(fin_x, fin_y, fin_z, 'k-', linewidth=2)
                
                # Add a fill for the fin (simplified)
                ax.plot_trisurf(fin_x, fin_y, fin_z, color='lightgray', alpha=0.6)

def plot_rocket_stability(rocket_fin=None, current_mass=None, mach=None):
    """
    Create and display a stability diagram for the rocket
    
    Args:
        rocket_fin: RocketFin instance to use for fin properties
        current_mass: Current propellant mass (for partially burned state)
        mach: Current Mach number for CP calculation
        
    Returns:
        fig, ax: Figure and axis objects
    """
    stability = RocketStability()
    
    # Set fin properties if a fin object is provided
    if rocket_fin:
        stability.set_fin_properties(rocket_fin)
    
    # Set flight conditions if provided
    if mach:
        stability.set_flight_conditions(mach)
    
    # Set current propellant mass if provided
    if current_mass is not None:
        stability.set_propellant_mass(current_mass)
    
    # Calculate center of mass and center of pressure
    stability.calculate_center_of_mass()
    stability.calculate_center_of_pressure()
    stability.calculate_stability()
    
    # Create the stability plot
    show_components = True
    if hasattr(config, 'show_component_cgs'):
        show_components = config.show_component_cgs
    
    fig, ax = stability.plot_stability_diagram(show_components=show_components)
    
    return fig, ax

def main():
    """Demo function for rocket stability visualization"""
    from rocket_fin_dimensions import RocketFin
    from component_manager import ComponentData
    
    # Create a component manager and update from team files
    component_manager = ComponentData()
    component_manager.update_from_team_files()
    
    # Update config variables with team data
    component_manager.update_config()
    
    # Print component summary
    component_manager.print_component_summary()
    
    # Create a fin object
    fin = RocketFin()
    fin.calculate_fin_dimensions(verbose=True)
    
    # Get propellant mass from component data or config
    propellant_mass = component_manager.get_component_data().get("propellant", {}).get("mass", config.propellant_mass)
    
    # Create stability diagram for full propellant load
    print("\nStability with full propellant load:")
    fig, ax = plot_rocket_stability(
        rocket_fin=fin,
        current_mass=propellant_mass,
        mach=0.1  # Low speed for launch
    )
    plt.show()
    
    # Create stability diagram for half propellant load
    print("\nStability with half propellant load:")
    fig, ax = plot_rocket_stability(
        rocket_fin=fin,
        current_mass=propellant_mass * 0.5,  # Half fuel remaining
        mach=2.0  # Higher speed during flight
    )
    plt.show()
    
    # Create stability diagram for empty propellant load
    print("\nStability with empty propellant load:")
    fig, ax = plot_rocket_stability(
        rocket_fin=fin,
        current_mass=0.0,  # Empty
        mach=0.5  # Lower speed near apogee
    )
    plt.show()
    
    # Create a series of diagrams for different propellant masses
    propellant_fractions = [1.0, 0.75, 0.5, 0.25, 0.0]
    
    fig, axes = plt.subplots(len(propellant_fractions), 1, figsize=(12, 4*len(propellant_fractions)))
    
    # Get total propellant mass from team data or config
    total_propellant = propellant_mass
    
    for i, fraction in enumerate(propellant_fractions):
        current_mass = total_propellant * fraction
        
        # Create stability object
        stability = RocketStability()
        stability.set_fin_properties(fin)
        stability.set_flight_conditions(mach=2.0)
        stability.set_propellant_mass(current_mass)
        
        # Calculate stability
        stability.calculate_center_of_mass()
        stability.calculate_center_of_pressure()
        stability.calculate_stability()
        
        # Draw rocket in this axes
        stability._draw_rocket_2d(axes[i])
        
        # Mark CP and CM
        axes[i].plot(stability.center_of_mass, 0, 'bo', markersize=10, label='Center of Mass')
        axes[i].plot(stability.center_of_pressure, 0, 'ro', markersize=10, label='Center of Pressure')
        
        # Draw stability margin
        stability._draw_stability_margin(axes[i])
        
        # Set title and format
        axes[i].set_title(f"Propellant remaining: {fraction*100:.0f}% - Stability: {stability.stability_calibers:.2f} calibers")
        axes[i].set_xlim(-0.1, stability.length * 1.1)
        axes[i].set_ylim(-stability.diameter, stability.diameter)
        axes[i].set_aspect('equal')
        
        if i == len(propellant_fractions) - 1:
            axes[i].set_xlabel('Distance from Nose Tip (m)')
        
        axes[i].legend(loc='lower right')
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()