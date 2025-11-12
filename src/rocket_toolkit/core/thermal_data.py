import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from src.rocket_toolkit.core.thermal_analyzer import ThermalAnalysis
from src.rocket_toolkit.geometry.rocket_fin import RocketFin
import pandas as pd
import time

mesh_size = 40
comparison_mesh_size = 24

class Visualization:
    def __init__(self, rocket_fin):
        self.fin = rocket_fin
        self.thermal_analyzer = ThermalAnalysis(rocket_fin)
        self.material_name = self.fin.material_name
        self.max_service_temp = self.fin.max_service_temp
        self.velocity = self.fin.velocity
        self.altitude = self.fin.altitude
    
    def plot_temperature_profile(self, nx=mesh_size, ny=mesh_size, return_fig=False):
        """Plot temperature profile with option to return figure instead of showing"""
        X, Y, temperature, heat_info = self.thermal_analyzer.calculate_temperature_profile(nx, ny)
        
        air_temp = heat_info["air_temp"]
        colors = [(0, 'blue'), (0.5, 'yellow'), (1, 'red')]
        cm = LinearSegmentedColormap.from_list('thermal', colors)
        
        min_temp = np.min(temperature)
        max_temp = np.max(temperature)
        
        mask = np.zeros_like(temperature, dtype=bool)
        height_m = self.fin.fin_height / 1000
        width_m = self.fin.fin_width / 1000
        
        for i in range(X.shape[0]):
            for j in range(X.shape[1]):
                y_val = Y[i, j]
                x_val = X[i, j]
                leading_edge_x = (y_val / height_m) * width_m
                if x_val < leading_edge_x:
                    mask[i, j] = True
        
        masked_temp = np.ma.array(temperature, mask=mask)
        
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        surf = ax.plot_surface(X, Y, masked_temp, cmap=cm, 
                              edgecolor='none', 
                              rstride=1, cstride=1,
                              alpha=0.8, 
                              antialiased=True)
        
        cbar = fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5)
        cbar.set_label('Temperature (K)')
        
        ax.set_xlabel('Width (m) - Chord Direction')
        ax.set_ylabel('Height (m) - Span Direction')
        ax.set_zlabel('Temperature (K)')
        
        title = f'Temperature Profile on {self.material_name} Delta Fin\n'
        title += f'Mach: {heat_info["mach"]:.2f}, Altitude: {self.altitude} m\n'
        title += f'Max Temp: {max_temp:.1f} K, Material Limit: {self.max_service_temp} K'
        ax.set_title(title)
        
        ax.view_init(elev=30, azim=-130)
        
        mask_edge = np.ones_like(X, dtype=bool)
        for i in range(X.shape[0]):
            for j in range(X.shape[1]):
                y_val = Y[i, j]
                x_val = X[i, j]
                leading_edge_x = (y_val / height_m) * width_m
                if (x_val >= leading_edge_x and
                    (j == 0 or j == X.shape[1]-1 or
                     i == 0 or i == X.shape[0]-1)):
                    mask_edge[i, j] = False
        
        X_edge = np.ma.array(X, mask=mask_edge)
        Y_edge = np.ma.array(Y, mask=mask_edge)
        Z_edge = np.ma.array(air_temp * np.ones_like(X), mask=mask_edge)
        ax.plot_wireframe(X_edge, Y_edge, Z_edge, color='black', linewidth=1)
        
        fig2, ax2 = plt.subplots(figsize=(10, 10))
        
        contour = ax2.contourf(X, Y, masked_temp, cmap=cm, levels=20)
        cbar2 = fig2.colorbar(contour, ax=ax2)
        cbar2.set_label('Temperature (K)')
        
        # Draw fin outline
        leading_edge_x_vals = []
        y_vals = np.linspace(0, height_m, 50)
        for y_val in y_vals:
            leading_edge_x = (y_val / height_m) * width_m
            leading_edge_x_vals.append(leading_edge_x)
        
        ax2.plot(leading_edge_x_vals, y_vals, 'k-', linewidth=2)
        ax2.plot([width_m, width_m], [0, height_m], 'k-', linewidth=2)
        ax2.plot([0, width_m], [0, 0], 'k-', linewidth=2)
        ax2.plot([leading_edge_x_vals[-1], width_m], [height_m, height_m], 'k-', linewidth=2)
        
        if np.max(temperature) > self.max_service_temp:
            over_temp = np.ma.masked_where((temperature <= self.max_service_temp) | mask, temperature)
            ax2.contourf(X, Y, over_temp, colors='red', alpha=0.3, levels=[self.max_service_temp, np.max(temperature)])
            ax2.contour(X, Y, masked_temp, levels=[self.max_service_temp], colors='red', linestyles='dashed')
        
        ax2.text(width_m + 0.001, height_m/2, "Free end", ha='left', va='center', fontsize=12, rotation=90)
        
        ax2.arrow(-0.003, height_m/2, 0.003, 0, head_width=0.002, head_length=0.001, 
                  fc='black', ec='black', width=0.0005)
        ax2.text(-0.001, height_m/2 + 0.003, "Airflow", ha='right', fontsize=10)
        
        max_temp_idx = np.unravel_index(np.argmax(masked_temp), masked_temp.shape)
        hottest_x = X[max_temp_idx]
        hottest_y = Y[max_temp_idx]
        ax2.plot(hottest_x, hottest_y, 'ro', markersize=8)
        
        label_offset = height_m * 0.05
        ax2.text(hottest_x, hottest_y + label_offset, f"Max: {max_temp:.1f}K", 
                ha='center', fontsize=10, bbox=dict(facecolor='white', alpha=0.7))
        
        ax2.set_xlabel('Width (m) - Chord Direction')
        ax2.set_ylabel('Height (m) - Span Direction')
        ax2.set_title(f'Temperature Distribution on {self.material_name} Delta Fin (Top View)')
        ax2.set_aspect('equal')
        
        plt.subplots_adjust(bottom=0.30)
        
        info_text = f'Flight Conditions:\n'
        info_text += f'  Velocity: {self.velocity} m/s\n'
        info_text += f'  Altitude: {self.altitude} m\n'
        info_text += f'  Mach: {heat_info["mach"]:.2f}\n'
        info_text += f'  Reynolds: {heat_info["reynolds"]:.2e}\n\n'
        info_text += f'Material: {self.material_name}\n'
        info_text += f'  Max Service Temp: {self.max_service_temp} K\n'
        info_text += f'  Max Fin Temp: {max_temp:.1f} K\n'
        info_text += f'  Margin: {(self.max_service_temp - max_temp):.1f} K'
        
        plt.figtext(0.5, 0.03, info_text, ha='center', va='bottom',
                   bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.5'))
        
        plt.tight_layout(rect=[0, 0.25, 1, 0.95]) 
        
        if return_fig:
            return fig, fig2
        else:
            plt.show()
            return fig, fig2
    
    def compare_materials(self, velocities=None, altitudes=None, use_cached=True, fast_mode=True, return_data=False):
        """Compare materials with option to return data instead of showing plots"""
        if velocities is None:
            velocities = [self.velocity]
        if altitudes is None:
            altitudes = [self.altitude]
        
        materials = self.fin.get_available_materials()
        results = []
        
        if fast_mode:
            self.thermal_analyzer.set_comparison_mode(True)
        
        current_material = self.fin.material_name
        current_velocity = self.fin.velocity
        current_altitude = self.fin.altitude
        
        start_time = time.time()
        
        if use_cached and not hasattr(self.fin, 'all_materials_data'):
            self.fin.calculate_all_material_dimensions(verbose=False)
        
        for i, velocity in enumerate(velocities):
            for j, altitude in enumerate(altitudes):
                for k, material in enumerate(materials):
                    progress = (i * len(altitudes) * len(materials) + 
                               j * len(materials) + k + 1) / (len(velocities) * len(altitudes) * len(materials))
                    elapsed = time.time() - start_time
                    estimated_total = elapsed / progress if progress > 0 else 0
                    remaining = estimated_total - elapsed
                    
                    print(f"\rComparing materials: {progress:.1%} complete. Est. remaining: {remaining:.1f}s", end="")
                    
                    self.fin.set_material(material)
                    self.fin.velocity = velocity
                    self.fin.altitude = altitude
                    self.material_name = self.fin.material_name
                    self.max_service_temp = self.fin.max_service_temp

                    nx = ny = comparison_mesh_size if fast_mode else mesh_size
                    _, _, temperature, heat_info = self.thermal_analyzer.calculate_temperature_profile(nx, ny)
                    max_temp = np.max(temperature)
                    
                    dims = self.fin.get_material_specific_dimensions(material)
                    mass = dims["mass"]
                    temp_margin = self.max_service_temp - max_temp
                    
                    results.append({
                        "Material": material,
                        "Velocity (m/s)": velocity,
                        "Altitude (m)": altitude,
                        "Height (mm)": dims["height"],
                        "Width (mm)": dims["width"],
                        "Max Temp (K)": max_temp,
                        "Max Service Temp (K)": self.max_service_temp,
                        "Temp Margin (K)": temp_margin,
                        "Mass (kg)": mass,
                        "Density (kg/m³)": self.fin.density,
                        "Thermal Conductivity (W/m·K)": self.fin.thermal_conductivity,
                        "Within Limits": max_temp <= self.max_service_temp
                    })
        
        self.fin.set_material(current_material)
        self.fin.velocity = current_velocity
        self.fin.altitude = current_altitude
        self.material_name = self.fin.material_name
        self.max_service_temp = self.fin.max_service_temp
        
        if fast_mode:
            self.thermal_analyzer.set_comparison_mode(False)
        
        print(f"\nComparison completed in {time.time() - start_time:.2f} seconds.")
        
        df = pd.DataFrame(results)
        df_sorted = df.sort_values(by=["Within Limits", "Mass (kg)"], ascending=[False, True])
        
        print("\nMaterial Comparison Results:")
        print(f"{'Material':<33} {'Max Temp (K)':<12} {'Temp Margin (K)':<15} {'Mass (kg)':<10} {'Within Limits':<15}")
        print("-" * 85)
        
        for _, row in df_sorted.iterrows():
            print(f"{row['Material']:<33} {row['Max Temp (K)']:<12.3f} {row['Temp Margin (K)']:<15.1f} {row['Mass (kg)']:<10.5f} {row['Within Limits']}")
        
        if return_data:
            return df_sorted
        else:
            return self.plot_material_comparison(velocities, altitudes, df_sorted)
    
    def plot_material_comparison(self, velocities=None, altitudes=None, df=None, return_fig=False):
        """Plot material comparison with option to return figures instead of showing"""
        if df is None:
            df = self.compare_materials(velocities, altitudes)
        
        if len(velocities) == 1 and len(altitudes) == 1:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 14))
            
            materials = df["Material"].tolist()
            positions = np.arange(len(materials))
            width = 0.2
            
            temp_bars = ax1.bar(positions - width/2, df["Max Temp (K)"], width, 
                               label="Max Temperature (K)", color='red', alpha=0.7)
            
            for i, material in enumerate(materials):
                limit = df[df["Material"] == material]["Max Service Temp (K)"].values[0]
                ax1.plot([positions[i] - width*1.5, positions[i] - width/2], [limit, limit], 'r--', linewidth=3)
                ax1.text(positions[i] - width, limit, f"{limit:.0f}K", ha='center', va='bottom')
            
            ax2_twin = ax1.twinx()
            mass_bars = ax2_twin.bar(positions + width/2, df["Mass (kg)"], width, color='orange', alpha=0.6, label="Mass (kg)")
            
            ax1.set_xlabel("Material")
            ax1.set_ylabel("Temperature (K)")
            ax2_twin.set_ylabel("Mass (kg)")
            ax1.set_title(f"Temperature Comparison by Material (Enhanced Accuracy)")
            
            ax1.set_xticks(positions)
            ax1.set_xticklabels(materials, rotation=45, ha='right')
            
            ax1.legend(loc='upper left')
            ax2_twin.legend(loc='upper right')
            
            # Add ambient temperature reference
            ambient_temp = 288.15
            ax1.axhline(y=ambient_temp, color='blue', linestyle=':', alpha=0.5,
                       label=f"Ambient Temp ({ambient_temp}K)")
            
            # Plot 2: Mass comparison with temperature safety rating
            results_mass = sorted(df.to_dict('records'), key=lambda x: x["Mass (kg)"])
            materials_by_mass = [r["Material"] for r in results_mass]
            masses_sorted = np.array([r["Mass (kg)"] for r in results_mass])
            within_limits = [r["Within Limits"] for r in results_mass]
            temp_margins_mass = np.array([r["Temp Margin (K)"] for r in results_mass])
            
            positions2 = np.arange(len(materials_by_mass))
            mass_bars = ax2.bar(positions2, masses_sorted, label="Total Fins Mass (kg)")
            
            # Color code bars based on temperature margin
            colors = []
            for margin, limit_ok in zip(temp_margins_mass, within_limits):
                if not limit_ok:
                    colors.append('red')
                elif margin < 50:
                    colors.append('orange')
                elif margin < 150:
                    colors.append('yellow')
                else:
                    colors.append('green')
            
            # Apply colors
            for bar, color, limit_ok in zip(mass_bars, colors, within_limits):
                bar.set_color(color)
                if not limit_ok:
                    bar.set_hatch('///')
            
            # Add mass annotations
            for i, mass in enumerate(masses_sorted):
                ax2.annotate(f"{mass:.4f}kg", xy=(i, mass + 0.01),
                           ha='center', va='bottom', fontsize=8)
            
            # Set labels and formatting
            ax2.set_xlabel("Material")
            ax2.set_ylabel("Mass (kg)")
            ax2.set_title("Mass Comparison by Material (With Temperature Safety Rating)")
            ax2.set_xticks(positions2)
            ax2.set_xticklabels(materials_by_mass, rotation=45, ha='right')
            ax2.grid(True, linestyle='--', alpha=0.7)
            
            # Add color coding legend
            import matplotlib.patches as mpatches
            legend_elements = [
                mpatches.Patch(color='red', hatch='///', label='Exceeds Temperature Limit'),
                mpatches.Patch(color='orange', label='Margin < 50K'),
                mpatches.Patch(color='yellow', label='Margin < 150K'),
                mpatches.Patch(color='green', label='Margin ≥ 150K')
            ]
            ax2.legend(handles=legend_elements, loc='upper right')
            
            plt.tight_layout()
            
            if return_fig:
                return fig
            else:
                plt.show()
                return fig

def main():
    """Main function - now only shows plots interactively, doesn't save files"""
    fin = RocketFin()

    print("Available materials:")
    for material in fin.get_available_materials():
        print(f"- {material}")
    
    fin.calculate_all_material_dimensions(verbose=False)
    
    fin.velocity = 1273.011  # m/s
    fin.altitude = 20770.795  # m
    visualizer = Visualization(fin)
    
    print("\nComparing materials for weight optimization...")
    comparison_results = visualizer.compare_materials(
        velocities=[fin.velocity], 
        altitudes=[fin.altitude],
        use_cached=True,
        fast_mode=True
    )
    
    visualizer.plot_material_comparison(
        velocities=[fin.velocity], 
        altitudes=[fin.altitude],
        df=comparison_results
    )
    
    best_material = comparison_results[comparison_results["Within Limits"]].iloc[0]["Material"]
    fin.set_material(best_material)
    visualizer = Visualization(fin)
    top_materials = comparison_results[comparison_results["Within Limits"]].iloc[:3]["Material"].tolist()
    print(f"\nComparing temperature profiles for top 3 materials: {top_materials}")
    
    for material in top_materials:
        print(f"Analyzing temperature profile for {material}...")
        fin.set_material(material)
        visualizer = Visualization(fin)
        visualizer.plot_temperature_profile()

if __name__ == "__main__":
    main()