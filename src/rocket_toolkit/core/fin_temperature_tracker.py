import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from src.rocket_toolkit.core.thermal_analyzer import ThermalAnalysis
from src.rocket_toolkit.geometry.rocket_fin import RocketFin

class FinTemperatureTracker:
    """
    Class to track fin temperature during flight simulation with completely consistent maximum temperature tracking
    """
    def __init__(self, rocket_fin):
        self.fin = rocket_fin
        self.thermal_analyzer = ThermalAnalysis(rocket_fin)
        
        # Storage for temperature history
        self.time_points = []
        self.max_temp_history = []
        self.avg_temp_history = []
        self.altitude_history = []
        self.velocity_history = []
        self.mach_history = []
        
        # Store absolute maximum temperature ever reached
        self.absolute_max_temperature = None
        self.absolute_max_temperature_info = None
        
        # Points to track (normalized coordinates)
        self.track_points = [
            {"name": "Leading Edge Mid", "x_norm": 0.0, "y_norm": 0.5},
            {"name": "Trailing Edge Mid", "x_norm": 1.0, "y_norm": 0.5},
            {"name": "Fin Root Mid", "x_norm": 0.5, "y_norm": 0.0},
            {"name": "Fin Tip Mid", "x_norm": 0.5, "y_norm": 1.0},
            {"name": "Center", "x_norm": 0.5, "y_norm": 0.5}
        ]
        
        # Initialize temperature history for track points
        self.track_point_temps = {point["name"]: [] for point in self.track_points}
        
        # For visualization
        self.colors = [(0, 'blue'), (0.5, 'yellow'), (1, 'red')]
        self.cmap = LinearSegmentedColormap.from_list('thermal', self.colors)
        
        # Store mask once calculated
        self.mask = None
        
        # Reset thermal analyzer's maximum temperature tracking
        if hasattr(self.thermal_analyzer, 'reset_max_temperature'):
            self.thermal_analyzer.reset_max_temperature()
    
    def update(self, time, altitude, velocity, dt):
        """
        Update fin temperature based on current flight conditions with enhanced tracking
        """
        # Update fin flight conditions
        self.fin.altitude = altitude
        self.fin.velocity = velocity
        
        # Update temperature field
        X, Y, temperature, heat_info = self.thermal_analyzer.update_temperature_field(dt)
        
        # Record data
        self.time_points.append(time)
        
        # Create mask for points outside the fin if not already created
        if self.mask is None:
            self.mask = np.zeros_like(temperature, dtype=bool)
            height_m = self.fin.fin_height / 1000
            width_m = self.fin.fin_width / 1000
            
            for i in range(X.shape[0]):
                for j in range(X.shape[1]):
                    y_val = Y[i, j]
                    x_val = X[i, j]
                    leading_edge_x = (y_val / height_m) * width_m
                    if x_val < leading_edge_x:
                        self.mask[i, j] = True
        elif self.mask.shape != temperature.shape:
            # If mesh size changed, recalculate mask
            self.mask = np.zeros_like(temperature, dtype=bool)
            height_m = self.fin.fin_height / 1000
            width_m = self.fin.fin_width / 1000
            
            for i in range(X.shape[0]):
                for j in range(X.shape[1]):
                    y_val = Y[i, j]
                    x_val = X[i, j]
                    leading_edge_x = (y_val / height_m) * width_m
                    if x_val < leading_edge_x:
                        self.mask[i, j] = True
        
        # Apply mask to temperature data
        masked_temp = np.ma.array(temperature, mask=self.mask)
        
        # Record max and average temperature
        current_max_temp = np.max(masked_temp)
        self.max_temp_history.append(current_max_temp)
        self.avg_temp_history.append(np.mean(masked_temp[~self.mask]))
        
        # Record flight conditions
        self.altitude_history.append(altitude)
        self.velocity_history.append(velocity)
        self.mach_history.append(heat_info["mach"])
        
        # Check if we have a new absolute maximum temperature
        # First, check if the thermal analyzer has a max_temp_ever field
        if "max_temp_ever" in heat_info:
            max_global = heat_info["max_temp_ever"]
            
            # Update if higher than our current absolute max
            if self.absolute_max_temperature is None or max_global > self.absolute_max_temperature:
                self.absolute_max_temperature = max_global
                
                # Get additional information about when this max temperature occurred
                if hasattr(self.thermal_analyzer, 'get_max_temperature_info'):
                    max_info = self.thermal_analyzer.get_max_temperature_info()
                    if max_info is not None:
                        self.absolute_max_temperature_info = {
                            "time": time,  # Current time as approximation
                            "altitude": altitude,  # Current altitude as approximation
                            "velocity": velocity,  # Current velocity as approximation
                            "mach": heat_info["mach"],  # Current mach as approximation
                            "temperature": max_global
                        }
                        
                        # Update with more accurate information if available
                        if "mach" in max_info:
                            self.absolute_max_temperature_info["mach"] = max_info["mach"]
                        if "altitude" in max_info:
                            self.absolute_max_temperature_info["altitude"] = max_info["altitude"]
                        if "velocity" in max_info:
                            self.absolute_max_temperature_info["velocity"] = max_info["velocity"]
                else:
                    # Create basic info
                    self.absolute_max_temperature_info = {
                        "time": time,
                        "altitude": altitude,
                        "velocity": velocity,
                        "mach": heat_info["mach"],
                        "temperature": max_global
                    }
        else:
            # Use the traditional method as fallback
            if self.absolute_max_temperature is None or current_max_temp > self.absolute_max_temperature:
                self.absolute_max_temperature = current_max_temp
                self.absolute_max_temperature_info = {
                    "time": time,
                    "altitude": altitude,
                    "velocity": velocity,
                    "mach": heat_info["mach"],
                    "temperature": current_max_temp
                }
        
        # Record temperatures at track points
        nx, ny = temperature.shape[1], temperature.shape[0]
        height_m = self.fin.fin_height / 1000
        width_m = self.fin.fin_width / 1000
        
        for point in self.track_points:
            # Convert normalized coordinates to array indices
            x_norm, y_norm = point["x_norm"], point["y_norm"]
            
            # For leading edge, we need to account for the delta fin shape
            if x_norm == 0.0:  # Leading edge
                # Find the leading edge x-coordinate at this y position
                y_idx = int(y_norm * (ny - 1))
                y_val = Y[y_idx, 0]
                leading_edge_x = (y_val / height_m) * width_m
                
                # Find the closest x-index
                x_positions = X[0, :]
                x_idx = np.argmin(np.abs(x_positions - leading_edge_x))
                
                # Check if this is within the fin
                if not self.mask[y_idx, x_idx]:
                    point_temp = temperature[y_idx, x_idx]
                else:
                    # Try the next point inward
                    point_temp = temperature[y_idx, x_idx+1] if x_idx < nx-1 else temperature[y_idx, x_idx-1]
            else:
                # For other points, use geometric scaling
                y_idx = int(y_norm * (ny - 1))
                
                # For x, we need to account for the delta fin shape
                y_val = Y[y_idx, 0]
                leading_edge_x = (y_val / height_m) * width_m
                trailing_edge_x = width_m
                
                # Map x_norm to actual position between leading and trailing edge
                actual_x = leading_edge_x + x_norm * (trailing_edge_x - leading_edge_x)
                
                # Find closest x-index
                x_positions = X[0, :]
                x_idx = np.argmin(np.abs(x_positions - actual_x))
                
                point_temp = temperature[y_idx, x_idx]
            
            self.track_point_temps[point["name"]].append(point_temp)
    
    def plot_temperature_history(self):
        """Plot temperature history throughout the flight with enhanced accuracy"""
        # Create figure with increased size
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 15), sharex=True)
        
        # Plot 1: Max and average temperature
        ax1.plot(self.time_points, self.max_temp_history, 'r-', label='Max Temperature')
        ax1.plot(self.time_points, self.avg_temp_history, 'b-', label='Average Temperature')
        
        # Add absolute maximum temperature annotation
        if self.absolute_max_temperature is not None:
            # Add a marker for the actual maximum point
            if self.absolute_max_temperature_info:
                max_time = self.absolute_max_temperature_info["time"]
                ax1.plot(max_time, self.absolute_max_temperature, 'ko', markersize=8)
                
                # Add annotation with arrow
                ax1.annotate(f"Max: {self.absolute_max_temperature:.1f}K at t={max_time:.1f}s",
                         xy=(max_time, self.absolute_max_temperature),
                         xytext=(max_time + 10, self.absolute_max_temperature + 5),
                         arrowprops=dict(facecolor='black', shrink=0.05))
        
        # Add material temperature limit
        ax1.axhline(y=self.fin.max_service_temp, color='r', linestyle='--', 
                   label=f'Max Service Temp ({self.fin.max_service_temp}K)')
        
        ax1.set_ylabel('Temperature (K)')
        ax1.set_title(f'Fin Temperature History - {self.fin.material_name}')
        ax1.legend(loc='upper left')
        ax1.grid(True)
        
        # Plot 2: Flight conditions
        ax2.plot(self.time_points, self.altitude_history, 'g-', label='Altitude (m)')
        
        # Add second y-axis for velocity
        ax2_vel = ax2.twinx()
        ax2_vel.plot(self.time_points, self.velocity_history, 'b-', label='Velocity (m/s)')
        ax2_vel.plot(self.time_points, [m * 343 for m in self.mach_history], 'm--', label='Mach Speed (m/s)')
        
        # Add markers for maximum temperature
        if self.absolute_max_temperature_info:
            max_temp_time = self.absolute_max_temperature_info["time"]
            max_temp_altitude = self.absolute_max_temperature_info["altitude"]
            max_temp_velocity = self.absolute_max_temperature_info["velocity"]
            
            ax2.plot(max_temp_time, max_temp_altitude, 'ro', markersize=8, label='Max Temp Point')
            ax2_vel.plot(max_temp_time, max_temp_velocity, 'ro', markersize=8)
        
        ax2.set_ylabel('Altitude (m)')
        ax2_vel.set_ylabel('Velocity (m/s)')
        
        # Add legends to both y-axes
        lines1, labels1 = ax2.get_legend_handles_labels()
        lines2, labels2 = ax2_vel.get_legend_handles_labels()
        ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        
        ax2.grid(True)
        
        # Plot 3: Temperature at specific points
        for point_name, temps in self.track_point_temps.items():
            ax3.plot(self.time_points, temps, label=point_name)
        
        ax3.set_xlabel('Time (s)')
        ax3.set_ylabel('Temperature (K)')
        ax3.set_title('Temperature at Track Points')
        ax3.legend()
        ax3.grid(True)
        
        plt.tight_layout()
        return fig
    
    def plot_temperature_snapshot(self, idx, current_time, current_mach):
        """Plot a snapshot of temperature distribution at a specific time"""
        # Get dimensions and create mesh
        height_m = self.fin.fin_height / 1000
        width_m = self.fin.fin_width / 1000
        
        # For maximum temperature snapshots, try to use the global maximum temperature field
        use_max_temp_field = False
        temperature = None
        
        # Check if we should use the maximum temperature field
        if hasattr(self.thermal_analyzer, 'max_temperature_reached') and self.absolute_max_temperature_info:
            max_temp_time = self.absolute_max_temperature_info["time"]
            
            # If we're within 0.1s of max temperature time, use max field
            if abs(current_time - max_temp_time) < 0.1:
                temperature = self.thermal_analyzer.max_temperature_reached.copy()
                use_max_temp_field = True
        
        # Otherwise use current field
        if temperature is None:
            temperature = self.thermal_analyzer.current_temperature.copy()
            
        X, Y = self.thermal_analyzer.X, self.thermal_analyzer.Y
        
        # Apply mask to temperature data
        masked_temp = np.ma.array(temperature, mask=self.mask)
        
        # Create figure with increased size
        fig, ax = plt.subplots(figsize=(10, 10))
        
        # Plot contours
        contour = ax.contourf(X, Y, masked_temp, cmap=self.cmap, levels=20)
        cbar = fig.colorbar(contour, ax=ax)
        cbar.set_label('Temperature (K)')
        
        # Draw fin outline with improved accuracy
        # Get the y coordinates
        y_vals = np.unique(Y)
        
        # Draw the leading edge of the delta fin
        for i in range(len(y_vals)):
            if i > 0:  # Skip the first point
                y_curr = y_vals[i]
                y_prev = y_vals[i-1]
                x_curr = (y_curr / height_m) * width_m
                x_prev = (y_prev / height_m) * width_m
                ax.plot([x_prev, x_curr], [y_prev, y_curr], 'k-', linewidth=2)
        
        # Draw the rest of the outline
        ax.plot([width_m, width_m], [0, height_m], 'k-', linewidth=2)
        ax.plot([0, width_m], [0, 0], 'k-', linewidth=2)
        ax.plot([(height_m / height_m) * width_m, width_m], [height_m, height_m], 'k-', linewidth=2)
        
        # Highlight regions above max service temperature
        if np.max(masked_temp) > self.fin.max_service_temp:
            over_temp = np.ma.masked_where((masked_temp <= self.fin.max_service_temp) | self.mask, masked_temp)
            ax.contourf(X, Y, over_temp, colors='red', alpha=0.3, 
                        levels=[self.fin.max_service_temp, np.max(masked_temp)])
            ax.contour(X, Y, masked_temp, levels=[self.fin.max_service_temp], 
                      colors='red', linestyles='dashed')
        
        # Adjust placement of annotations
        ax.text(width_m/2, -0.003, "Fuselage side", ha='center', fontsize=12)
        ax.text(width_m + 0.001, height_m/2, "Free end", ha='left', va='center', fontsize=12, rotation=90)
        
        # Adjust arrow and label positioning
        arrow_y = height_m/2
        ax.arrow(-0.003, arrow_y, 0.003, 0, head_width=0.002, head_length=0.001, 
                fc='black', ec='black', width=0.0005)
        ax.text(-0.001, arrow_y + 0.003, "Airflow", ha='right', fontsize=10)
        
        # Find and mark the hottest point
        max_temp_idx = np.unravel_index(np.argmax(masked_temp), masked_temp.shape)
        hottest_x = X[max_temp_idx]
        hottest_y = Y[max_temp_idx]
        ax.plot(hottest_x, hottest_y, 'ro', markersize=8)
        
        # Add a text background for better readability and adjust position
        label_offset = height_m * 0.05
        
        # Get the current max temperature and the global max for reference
        current_max = np.max(masked_temp)
        
        # Show both current and absolute max if different
        if self.absolute_max_temperature is not None and abs(current_max - self.absolute_max_temperature) > 0.1:
            ax.text(hottest_x, hottest_y + label_offset, 
                   f"Current max: {current_max:.1f}K\nGlobal max: {self.absolute_max_temperature:.1f}K", 
                   ha='center', fontsize=10, bbox=dict(facecolor='white', alpha=0.7))
        else:
            ax.text(hottest_x, hottest_y + label_offset, f"Max: {current_max:.1f}K", 
                  ha='center', fontsize=10, bbox=dict(facecolor='white', alpha=0.7))
        
        ax.set_xlabel('Width (m) - Chord Direction')
        ax.set_ylabel('Height (m) - Span Direction')
        
        # Update title to include information about the visualization
        if use_max_temp_field:
            ax.set_title(f'Maximum Temperature Distribution (up to t={current_time:.1f}s), Mach={current_mach:.2f}')
        else:
            ax.set_title(f'Temperature Distribution at t={current_time:.1f}s, Mach={current_mach:.2f}')
            
        ax.set_aspect('equal')
        
        # Adjust subplot layout to accommodate info text
        plt.subplots_adjust(bottom=0.3)
        
        # Create improved information text box
        info_text = f'Flight Conditions:\n'
        info_text += f'  Time: {current_time:.1f} s\n'
        info_text += f'  Velocity: {self.velocity_history[idx]:.1f} m/s\n'
        info_text += f'  Altitude: {self.altitude_history[idx]:.1f} m\n'
        info_text += f'  Mach: {current_mach:.2f}\n\n'
        info_text += f'Material: {self.fin.material_name}\n'
        info_text += f'  Max Service Temp: {self.fin.max_service_temp} K\n'
        
        # Use absolute maximum temperature for margin calculation if available
        if self.absolute_max_temperature is not None:
            info_text += f'  Peak Fin Temp: {self.absolute_max_temperature:.1f} K\n'
            margin = self.fin.max_service_temp - self.absolute_max_temperature
            info_text += f'  Safety Margin: {margin:.1f} K'
            
            # Add warning if margin is negative
            if margin < 0:
                info_text += f' (EXCEEDS LIMIT by {abs(margin):.1f}K)'
        else:
            info_text += f'  Max Fin Temp: {current_max:.1f} K\n'
            margin = self.fin.max_service_temp - current_max
            info_text += f'  Margin: {margin:.1f} K'
        
        # Positioned with better parameters to avoid overlap
        plt.figtext(0.5, 0.02, info_text, ha='center', 
                    bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.5'))
        
        return fig
    
    def get_max_temperature(self):
        """Get maximum temperature reached during flight, accounting for absolute maximum"""
        if self.absolute_max_temperature is not None:
            return self.absolute_max_temperature
        
        if self.max_temp_history:
            return max(self.max_temp_history)
            
        return None
    
    def get_critical_time_points(self):
        """Get time points of interest (max temperature, max velocity, etc.)"""
        if not self.time_points:
            return {}
            
        # If we have an absolute maximum, use that info
        if self.absolute_max_temperature_info:
            max_temp_info = self.absolute_max_temperature_info
        else:
            # Find max temperature point using traditional method
            max_temp_idx = np.argmax(self.max_temp_history)
            max_temp_info = {
                "time": self.time_points[max_temp_idx],
                "value": self.max_temp_history[max_temp_idx],
                "altitude": self.altitude_history[max_temp_idx],
                "velocity": self.velocity_history[max_temp_idx],
                "mach": self.mach_history[max_temp_idx],
                "temperature": self.max_temp_history[max_temp_idx]
            }
        
        # Find max velocity point
        max_vel_idx = np.argmax(self.velocity_history)
        
        # Find max altitude point
        max_alt_idx = np.argmax(self.altitude_history)
        
        return {
            "max_temperature": {
                "time": max_temp_info["time"],
                "value": max_temp_info.get("temperature", max_temp_info.get("value")),
                "altitude": max_temp_info["altitude"],
                "velocity": max_temp_info["velocity"],
                "mach": max_temp_info["mach"]
            },
            "max_velocity": {
                "time": self.time_points[max_vel_idx],
                "value": self.velocity_history[max_vel_idx],
                "temperature": self.max_temp_history[max_vel_idx],
                "altitude": self.altitude_history[max_vel_idx],
                "mach": self.mach_history[max_vel_idx]
            },
            "max_altitude": {
                "time": self.time_points[max_alt_idx],
                "value": self.altitude_history[max_alt_idx],
                "temperature": self.max_temp_history[max_alt_idx],
                "velocity": self.velocity_history[max_alt_idx],
                "mach": self.mach_history[max_alt_idx]
            }
        }