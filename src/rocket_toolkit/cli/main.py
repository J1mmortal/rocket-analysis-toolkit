import argparse
import os
import time
import json
import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
from src.rocket_toolkit.core import flight_simulator
from src.rocket_toolkit.core import thermal_analyzer
from src.rocket_toolkit.geometry.rocket_fin import RocketFin
from src.rocket_toolkit.core.fin_temperature_tracker import FinTemperatureTracker
from src.rocket_toolkit.plotting.fin_animation import create_fin_temperature_animation
from src.rocket_toolkit.core.stability_analyzer import RocketStability, plot_rocket_stability
from src.rocket_toolkit.geometry.component_manager import ComponentData
from src.rocket_toolkit.core.trajectory_optimizer import TrajectoryOptimizer
from docs.examples import material_comparison_example

CONFIG_FILE = "src/rocket_toolkit/config.json"
EDITABLE_KEYS = {"paths": ["team_data", "output"], 
                 "simulation": ["v0", "h0", "q0"], 
                 "engine": ["isp_sea", "isp_vac", "fuel_flow_rate"],
                 "rocket": ["rocket_radius", "drag_coefficient", "max_q"]}



def load_config():
    global config
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "paths": {
                "team_data": "./Team_data",
                "output": "./output"
            },
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=2)
        print("\nCant find config.json file, will load default config")
        return default_config
    with open(CONFIG_FILE) as f:
        print("\nConfig file found succesfully")
        config = json.load(f)
        return config

def configure_settings():
    config = load_config()
    print("\nEnter new values or press Enter to keep current value:")
    for section, section_values in config.items():
        print(f"\n[{section}]")
        if isinstance(section_values, dict):
            editable_keys = EDITABLE_KEYS.get(section, [])
            for key, value in section_values.items():
                if key not in editable_keys:
                    print(f"{key} [{value}]: [READ-ONLY]")
                    continue
                new_val = input(f"{key} [{value}]: ").strip()
                if new_val:
                    try:
                        cast_val = type(value)(new_val)
                    except Exception:
                        cast_val = new_val
                    section_values[key] = cast_val
        else:
            pass
    save_config(config)
    print("Configuration updated!")

def add_new_material():
    config = load_config()
    materials = config.get("materials", {})

    print("\n=== Add New Material ===")
    name = input("Material name (e.g. 'My Fancy Alloy'): ").strip()
    if not name:
        print("No name entered, aborting.")
        return
    if name in materials:
        overwrite = input("Material already exists. Overwrite? (y/N): ").strip().lower()
        if overwrite not in ("y", "yes"):
            print("Aborting, existing material kept.")
            return

    def ask_float(prompt, default=None):
        while True:
            if default is not None:
                text = input(f"{prompt} [{default}]: ").strip()
                if text == "":
                    return default
            else:
                text = input(f"{prompt}: ").strip()
            try:
                return float(text)
            except ValueError:
                print("Please enter a numeric value.")

    print("\nEnter material properties (SI units):")
    thermal_conductivity = ask_float("Thermal conductivity (W/m·K)")
    density = ask_float("Density (kg/m³)")
    specific_heat = ask_float("Specific heat (J/kg·K)")
    max_service_temp = ask_float("Max service temperature (K)")
    yield_strength = ask_float("Yield strength (MPa)")
    thermal_expansion = ask_float("Thermal expansion (1/K)")
    emissivity = ask_float("Emissivity (0-1)")

    materials[name] = {
        "thermal_conductivity": thermal_conductivity,
        "density": density,
        "specific_heat": specific_heat,
        "max_service_temp": max_service_temp,
        "yield_strength": yield_strength,
        "thermal_expansion": thermal_expansion,
        "emissivity": emissivity,
    }

    config["materials"] = materials
    save_config(config)
    print(f"\nMaterial '{name}' added/updated successfully.")

def apply_preset_menu():
    config = load_config()
    presets = config.get("presets", {})
    if not presets:
        print("\nNo presets defined in config.json under 'presets'.")
        return

    print("\n=== Available Rocket Presets ===")
    names = list(presets.keys())
    for i, name in enumerate(names, 1):
        print(f"{i}. {name}")
    print(f"{len(names)+1}. Cancel")
    choice = input("\nSelect preset to apply: ").strip()
    try:
        idx = int(choice)
    except ValueError:
        print("Invalid choice.")
        return
    if idx < 1 or idx > len(names) + 1:
        print("Choice out of range.")
        return
    if idx == len(names) + 1:
        print("Cancelled.")
        return

    preset_name = names[idx - 1]
    preset = presets[preset_name]
    print(f"\nApplying preset: {preset_name}")
    confirm = input("This will overwrite current rocket-related settings. Continue? (y/N): ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Aborted.")
        return

    apply_preset_to_config(config, preset)
    save_config(config)
    print(f"Preset '{preset_name}' applied and saved.")

def apply_preset_to_config(config, preset):
    for section, values in preset.items():
        if isinstance(values, dict):
            base_section = config.get(section, {})
            if not isinstance(base_section, dict):
                base_section = {}
            for key, val in values.items():
                base_section[key] = val
            config[section] = base_section
        else:
            config[section] = values


def settings_and_materials_menu():
    while True:
        print("\n===== Settings & Materials =====")
        print("1. Configure config settings")
        print("2. Add new material")
        print("3. Apply rocket preset")
        print("4. Return to main menu")

        sub_choice = input("\nEnter choice (1-4): ").strip()

        if sub_choice == '1':
            configure_settings()
        elif sub_choice == '2':
            add_new_material()
        elif sub_choice == '3':
            apply_preset_menu()
        elif sub_choice == '4':
            break
        else:
            print("Invalid choice, please enter 1–4.")


def get_fin_material():
    with open(CONFIG_FILE) as f:
        config = json.load(f)
    return config.get("fin_analysis", {}).get("fin_material", "Aluminum 6061-T6")

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def bootstrap():
    config = load_config()
    paths = config.get("paths", {})
    updated = False

    for folder_key in ["team_data", "output"]:
        folder_path = paths.get(folder_key, f"./{folder_key.capitalize()}")
        if not os.path.exists(folder_path):
            print(f"The folder '{folder_path}' for '{folder_key}' was not found.")
            create = input(f"Do you want to create it? [Y/n]: ").strip().lower()
            if create in ("", "y", "yes"):
                os.makedirs(folder_path)
                print(f"Created folder: {folder_path}")
            else:
                new_path = input(f"Enter path to existing {folder_key} folder or press Enter to skip: ").strip()
                if new_path and os.path.exists(new_path):
                    folder_path = new_path
                else:
                    print(f"Warning: {folder_key} folder not configured!")
            paths[folder_key] = folder_path
            updated = True

    if updated:
        config["paths"] = paths
        save_config(config)

def load_team_data():
    load_start = time.time()
    component_manager = ComponentData()
    component_manager.update_from_team_files()
    component_manager.update_config(config)
    
    load_time = time.time() - load_start
    print(f"Team data loaded in {load_time:.3f} seconds")
    
    return component_manager

def create_initial_conditions_page(simulation_type, **kwargs):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if simulation_type == "flight":
        content = _create_flight_conditions_content(**kwargs)
    elif simulation_type == "material_comparison":
        content = _create_material_comparison_conditions_content(**kwargs)
    elif simulation_type == "stability":
        content = _create_stability_conditions_content(**kwargs)
    elif simulation_type == "trajectory":
        content = _create_trajectory_conditions_content(**kwargs)
    else:
        content = "Unknown simulation type"
    
    content_lines = content.split('\n')
    
    available_height = 0.85  
    line_height = 0.012
    max_lines_per_page = int(available_height / line_height)
    
    figures = []
    
    total_lines = len(content_lines)
    current_start = 0
    page_num = 1
    
    while current_start < total_lines:
        fig = plt.figure(figsize=(11, 8.5))
        fig.patch.set_facecolor('white')
        
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        if page_num == 1:
            title = f"INITIAL CONDITIONS AND PARAMETERS\n{simulation_type.upper()} SIMULATION"
            ax.text(0.5, 0.96, title, ha='center', va='top', fontsize=14, fontweight='bold', 
                    transform=ax.transAxes)
            
            ax.text(0.5, 0.91, f"Generated: {timestamp}", ha='center', va='top', fontsize=10, 
                    transform=ax.transAxes, style='italic')
            
            content_start_y = 0.88
        else:
            title = f"INITIAL CONDITIONS (CONTINUED) - PAGE {page_num}\n{simulation_type.upper()} SIMULATION"
            ax.text(0.5, 0.96, title, ha='center', va='top', fontsize=14, fontweight='bold', 
                    transform=ax.transAxes)
            content_start_y = 0.91
        
        current_end = min(current_start + max_lines_per_page, total_lines)
        page_content = '\n'.join(content_lines[current_start:current_end])
        ax.text(0.05, content_start_y, page_content, ha='left', va='top', fontsize=8, 
                fontfamily='monospace', transform=ax.transAxes, linespacing=1.1)
        
        if total_lines > max_lines_per_page:
            total_pages = (total_lines + max_lines_per_page - 1) // max_lines_per_page  # Ceiling division
            ax.text(0.95, 0.02, f"Page {page_num} of {total_pages}", ha='right', va='bottom', 
                    fontsize=8, transform=ax.transAxes, style='italic')
        
        figures.append(fig)
        
        current_start = current_end
        page_num += 1
    
    return figures

def _create_flight_conditions_content(material_name=None, component_manager=None, fast_mode=False, **kwargs):
    content = []
    content.append("="*70)
    content.append("SIMULATION PARAMETERS")
    content.append("="*70)
    content.append(f"Fin Material:               {material_name}")
    content.append(f"Fast Mode:                  {fast_mode}")
    content.append(f"Time Step (dt):             {config["simulation"]["dt"]} s")
    content.append(f"After Top Reached:          {config["simulation"]["after_top_reached"]} cycles")
    content.append(f"Animation Enabled:          {getattr(config, 'create_temperature_animation', False)}")
    content.append("")
    content.append("="*70)
    content.append("COMPONENT MASSES AND POSITIONS")
    content.append("="*70)
    
    if component_manager and component_manager.get_component_data():
        components = component_manager.get_component_data()
        content.append(f"{'Component':<25} {'Mass (kg)':<12} {'Position (m)':<15} {'Team':<10}")
        content.append("-"*70)
        
        total_dry_mass = 0
        propellant_mass = 0
        
        for name, data in components.items():
            mass = data.get('mass', 0)
            position = data.get('position', 0)
            team = data.get('team', 'N/A')
            
            content.append(f"{name:<25} {mass:<12.3f} {position:<15.3f} {team:<10}")
            
            if 'propellant' in name.lower():
                propellant_mass += mass
            else:
                total_dry_mass += mass
        
        content.append("-"*70)
        content.append(f"{'Total Dry Mass':<25} {total_dry_mass:<12.3f}")
        content.append(f"{'Total Propellant':<25} {propellant_mass:<12.3f}")
        content.append(f"{'Total Mass':<25} {total_dry_mass + propellant_mass:<12.3f}")
        content.append(f"{'Mass Ratio':<25} {(total_dry_mass + propellant_mass) / total_dry_mass if total_dry_mass > 0 else 0:<12.3f}")
    else:
        content.append("Using legacy config values:")
        content.append(f"{'Dry Weight':<25} {config.dry_weight:<12.3f} kg")
        content.append(f"{'Propellant Mass':<25} {config["mass_properties"]["propellant_mass"]:<12.3f} kg")
    
    content.append("")
    
    content.append("="*70)
    content.append("ROCKET GEOMETRY")
    content.append("="*70)
    content.append(f"Rocket Length:              {getattr(config, 'rocket_length', "NOT FOUND")} m")
    content.append(f"Rocket Diameter:            {getattr(config, 'rocket_diameter', "NOT FOUND")} m")
    content.append(f"Rocket Radius:              {config["rocket"]["diameter"] / 2} m")
    content.append(f"Nose Cone Length:           {getattr(config, 'nose_cone_length', "NOT FOUND")} m")
    content.append(f"Nose Cone Shape:            {getattr(config, 'nose_cone_shape', 'ogive')}")
    content.append("")
    
    content.append("="*70)
    content.append("ENGINE PARAMETERS")
    content.append("="*70)
    content.append(f"ISP Sea Level:              {config["engine"]["isp_sea"]} s")
    content.append(f"ISP Vacuum:                 {config["engine"]["isp_vac"]} s")
    content.append(f"Fuel Flow Rate:             {config["engine"]["fuel_flow_rate"]} kg/s")
    content.append("")
    
    content.append("="*70)
    content.append("INITIAL CONDITIONS")
    content.append("="*70)
    content.append(f"Initial Velocity:           {config["simulation"]["v0"]} m/s")
    content.append(f"Initial Altitude:           {config["simulation"]["h0"]} m")
    content.append(f"Initial Dynamic Pressure:   {config["simulation"]["q0"]} Pa")
    content.append("")
    
    content.append("="*70)
    content.append("AERODYNAMIC PARAMETERS")
    content.append("="*70)
    content.append(f"Drag Coefficient:           {config["rocket"]["drag_coefficient"]}")
    content.append(f"Max Dynamic Pressure:       {config["rocket"]["max_q"]} Pa")
    content.append("")
    
    content.append("="*70)
    content.append("EARTH CONSTANTS")
    content.append("="*70)
    content.append(f"Gravitational Constant:     {config["earth_constants"]["gravitational_constant"]}")
    content.append(f"Earth Mass:                 {config["earth_constants"]["mass_earth"]} kg")
    content.append(f"Earth Radius:               {config["earth_constants"]["earth_radius"]} m")
    content.append("")
    
    if material_name:
        try:
            fin_material = get_fin_material()
            fin = RocketFin(material_name=fin_material)
            fin.set_material(material_name)
            fin.calculate_fin_dimensions(verbose=False)
            
            content.append("="*70)
            content.append("FIN PARAMETERS")
            content.append("="*70)
            content.append(f"Material:                   {fin.material_name}")
            content.append(f"Number of Fins:             {fin.num_fins}")
            content.append(f"Fin Height:                 {fin.fin_height:.2f} mm")
            content.append(f"Fin Width:                  {fin.fin_width:.2f} mm")
            content.append(f"Fin Mass (single):          {fin.fin_mass:.6f} kg")
            content.append(f"Total Fin Mass:             {fin.fin_mass * fin.num_fins:.6f} kg")
            content.append(f"Wall Thickness:             {fin.wall_thickness} mm")
            content.append(f"Fin Set CG Position:        {getattr(config, 'fin_set_cg_position', 2.1)} m")
            content.append("")
            
            content.append("="*70)
            content.append("MATERIAL PROPERTIES")
            content.append("="*70)
            content.append(f"Thermal Conductivity:       {fin.thermal_conductivity} W/(m·K)")
            content.append(f"Density:                    {fin.density} kg/m³")
            content.append(f"Specific Heat:              {fin.specific_heat} J/(kg·K)")
            content.append(f"Max Service Temperature:    {fin.max_service_temp} K")
            content.append(f"Yield Strength:             {fin.yield_strength} MPa")
            content.append(f"Thermal Expansion:          {fin.thermal_expansion} 1/K")
            content.append(f"Emissivity:                 {fin.emissivity}")
            
        except Exception as e:
            content.append("="*70)
            content.append("FIN PARAMETERS")
            content.append("="*70)
            content.append(f"Error calculating fin parameters: {str(e)}")
    
    return "\n".join(content)

def _create_material_comparison_conditions_content(fast_mode=False, component_manager=None, **kwargs):
    content = []
    
    try:
        fin_material = get_fin_material()
        fin = RocketFin(material_name=fin_material)
        materials = fin.get_available_materials()
    except:
        materials = ["Unable to load materials"]
    
    content.append("="*70)
    content.append("MATERIAL COMPARISON PARAMETERS")
    content.append("="*70)
    content.append(f"Comparison Mode:            {'Fast' if fast_mode else 'Detailed'}")
    content.append(f"Number of Materials:        {len(materials)}")
    content.append(f"Mesh Size:                  {'Reduced' if fast_mode else 'Full'}")
    content.append("")
    
    content.append("Materials Compared:")
    content.append("-" * 30)
    for i, material in enumerate(materials, 1):
        content.append(f"{i:2d}. {material}")
    content.append("")
    
    content.append("="*70)
    content.append("COMMON SIMULATION PARAMETERS")
    content.append("="*70)
    content.append(f"Time Step (dt):             {config["simulation"]["dt"]} s")
    content.append(f"Max Dynamic Pressure:       {config["rocket"]["max_q"]} Pa")
    content.append(f"Drag Coefficient:           {config["rocket"]["drag_coefficient"]}")
    content.append(f"ISP Sea Level:              {config["engine"]["isp_sea"]} s")
    content.append(f"ISP Vacuum:                 {config["engine"]["isp_vac"]} s")
    content.append(f"Fuel Flow Rate:             {config["engine"]["fuel_flow_rate"]} kg/s")
    content.append("")
    
    if component_manager and component_manager.get_component_data():
        components = component_manager.get_component_data()
        content.append("="*70)
        content.append("COMPONENT MASSES (USED FOR ALL MATERIALS)")
        content.append("="*70)
        content.append(f"{'Component':<25} {'Mass (kg)':<12} {'Position (m)':<15}")
        content.append("-"*60)
        
        for name, data in components.items():
            mass = data.get('mass', 0)
            position = data.get('position', 0)
            content.append(f"{name:<25} {mass:<12.3f} {position:<15.3f}")
    
    return "\n".join(content)

def _create_stability_conditions_content(flight_stage=None, component_manager=None, **kwargs):
    content = []
    
    content.append("="*70)
    content.append("STABILITY ANALYSIS PARAMETERS")
    content.append("="*70)
    content.append(f"Flight Stage Analyzed:      {flight_stage if flight_stage else 'All Stages'}")
    content.append(f"Min Caliber Stability:      {getattr(config, 'min_caliber_stability', 1.5)}")
    content.append(f"Max Caliber Stability:      {getattr(config, 'max_caliber_stability', 4.0)}")
    content.append(f"Show Component CGs:         {getattr(config, 'show_component_cgs', True)}")
    content.append(f"Show Stability Margin:      {getattr(config, 'show_stability_margin', True)}")
    content.append("")
    
    content.append("="*70)
    content.append("ROCKET CONFIGURATION")
    content.append("="*70)
    content.append(f"Rocket Length:              {getattr(config, 'rocket_length', 2.5)} m")
    content.append(f"Rocket Diameter:            {getattr(config, 'rocket_diameter', 0.5)} m")
    content.append(f"Nose Cone Length:           {getattr(config, 'nose_cone_length', 0.3)} m")
    content.append(f"Nose Cone Shape:            {getattr(config, 'nose_cone_shape', 'ogive')}")
    content.append("")
    
    if component_manager and component_manager.get_component_data():
        components = component_manager.get_component_data()
        content.append("="*70)
        content.append("COMPONENT MASSES AND CG POSITIONS")
        content.append("="*70)
        content.append(f"{'Component':<25} {'Mass (kg)':<12} {'CG Position (m)':<18}")
        content.append("-"*60)
        
        for name, data in components.items():
            mass = data.get('mass', 0)
            position = data.get('position', 0)
            content.append(f"{name:<25} {mass:<12.3f} {position:<18.3f}")
    
    content.append("")
    
    if flight_stage and flight_stage != "all":
        content.append("="*70)
        content.append(f"FLIGHT CONDITIONS FOR {flight_stage.upper()} STAGE")
        content.append("="*70)
        
        if flight_stage.lower() == "launch":
            content.append("Mach Number:                0.1")
            content.append("Propellant Load:            100%")
        elif flight_stage.lower() == "burnout":
            content.append("Mach Number:                2.0")
            content.append("Propellant Load:            0%")
        elif flight_stage.lower() == "apogee":
            content.append("Mach Number:                0.5")
            content.append("Propellant Load:            0%")
        elif flight_stage.lower() == "landing":
            content.append("Mach Number:                0.2")
            content.append("Propellant Load:            0%")
    
    return "\n".join(content)

def _create_trajectory_conditions_content(target_altitude=100000, component_manager=None, **kwargs):
    content = []
    
    content.append("="*70)
    content.append("TRAJECTORY OPTIMIZATION PARAMETERS")
    content.append("="*70)
    content.append(f"Target Altitude:            {target_altitude/1000:.0f} km ({target_altitude} m)")
    content.append("Analysis Type:              Trajectory optimization")
    content.append("")
    
    content.append("="*70)
    content.append("OPTIMIZATION ANALYSIS CATEGORIES")
    content.append("="*70)
    content.append("1. Mass Reduction Analysis")
    content.append("2. Aerodynamic Improvements")
    content.append("3. Propellant Optimization")
    content.append("4. Staging Considerations")
    content.append("5. Trajectory Shape Optimization")
    content.append("")
    
    content.append("="*70)
    content.append("BASELINE SIMULATION PARAMETERS")
    content.append("="*70)
    content.append(f"Material Used:              {getattr(config, 'fin_material', 'Titanium Ti-6Al-4V')}")
    content.append("Fast Mode:                  True")
    content.append(f"Time Step (dt):             {config["simulation"]["dt"]} s")
    content.append(f"Max Dynamic Pressure:       {config["rocket"]["max_q"]} Pa")
    content.append("")
    
    if component_manager and component_manager.get_component_data():
        components = component_manager.get_component_data()
        content.append("="*70)
        content.append("CURRENT ROCKET CONFIGURATION")
        content.append("="*70)
        
        total_mass = sum(comp['mass'] for comp in components.values())
        dry_mass = sum(comp['mass'] for name, comp in components.items() 
                      if 'propellant' not in name.lower())
        propellant_mass = total_mass - dry_mass
        
        content.append(f"Total Mass:                 {total_mass:.3f} kg")
        content.append(f"Dry Mass:                   {dry_mass:.3f} kg")
        content.append(f"Propellant Mass:            {propellant_mass:.3f} kg")
        content.append(f"Mass Ratio:                 {total_mass/dry_mass if dry_mass > 0 else 0:.3f}")
        content.append("")
        
        content.append("Component Breakdown:")
        content.append("-" * 30)
        for name, data in sorted(components.items(), key=lambda x: x[1]['mass'], reverse=True):
            percentage = (data['mass'] / total_mass) * 100
            content.append(f"{name:<20} {data['mass']:>8.3f} kg ({percentage:>5.1f}%)")
    
    return "\n".join(content)

def create_flight_simulation_pdf(output_path, material_name, component_manager=None, fast_mode=False):
    
    with PdfPages(output_path) as pdf:
        times = np.array(flight_simulator.time_points)
        speeds = np.array([i.speed for i in flight_simulator.r])
        altitudes = np.array([i.altitude for i in flight_simulator.r])
        dynamic_pressures = np.array([i.dynamic_pressure for i in flight_simulator.r])
        nose_cone_temps = np.array([i.nose_cone_temp for i in flight_simulator.r])
        
        # Page 1
        fig1 = plt.figure(figsize=(12, 8))
        
        ax1 = plt.subplot(2, 1, 1)
        ax1.plot(times, speeds, 'b-', linewidth=1.5)
        ax1.set_title("Speed vs Time")
        ax1.set_xlabel("Time (s)")
        ax1.set_ylabel("Speed (m/s)")
        ax1.grid(True, linestyle='--', alpha=0.7)
        
        ax2 = plt.subplot(2, 1, 2)
        ax2.plot(times, altitudes, 'g-', linewidth=1.5)
        ax2.set_title("Altitude vs Time")
        ax2.set_xlabel("Time (s)")
        ax2.set_ylabel("Altitude (m)")
        ax2.grid(True, linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        pdf.savefig(fig1)
        plt.close(fig1)
        
        # Page 2
        if flight_simulator.fin_tracker:
            fig2 = flight_simulator.fin_tracker.plot_temperature_history()
            pdf.savefig(fig2)
            plt.close(fig2)
            
            # Page 3
            fig3 = plt.figure(figsize=(12, 8))
            
            ax1 = plt.subplot(2, 2, 1)
            ax1.plot(flight_simulator.fin_tracker.time_points, flight_simulator.fin_tracker.altitude_history, 'g-', label='Altitude (m)')
            if hasattr(flight_simulator.fin_tracker, 'absolute_max_temperature_info') and flight_simulator.fin_tracker.absolute_max_temperature_info:
                max_info = flight_simulator.fin_tracker.absolute_max_temperature_info
                ax1.plot(max_info["time"], max_info["altitude"], 'ro', markersize=8, label='Max Temp Point')
            ax1.set_xlabel('Time (s)')
            ax1.set_ylabel('Altitude (m)')
            ax1.set_title('Altitude vs Time')
            ax1.legend()
            ax1.grid(True)
            
            ax2 = plt.subplot(2, 2, 2)
            ax2.plot(flight_simulator.fin_tracker.time_points, flight_simulator.fin_tracker.velocity_history, 'b-', label='Velocity (m/s)')
            if hasattr(flight_simulator.fin_tracker, 'absolute_max_temperature_info') and flight_simulator.fin_tracker.absolute_max_temperature_info:
                ax2.plot(max_info["time"], max_info["velocity"], 'ro', markersize=8, label='Max Temp Point')
            ax2.set_xlabel('Time (s)')
            ax2.set_ylabel('Velocity (m/s)')
            ax2.set_title('Velocity vs Time')
            ax2.legend()
            ax2.grid(True)
            
            ax3 = plt.subplot(2, 2, 3)
            ax3.plot(flight_simulator.fin_tracker.time_points, flight_simulator.fin_tracker.mach_history, 'm-', label='Mach Number')
            if hasattr(flight_simulator.fin_tracker, 'absolute_max_temperature_info') and flight_simulator.fin_tracker.absolute_max_temperature_info:
                ax3.plot(max_info["time"], max_info["mach"], 'ro', markersize=8, label='Max Temp Point')
            ax3.set_xlabel('Time (s)')
            ax3.set_ylabel('Mach Number')
            ax3.set_title('Mach Number vs Time')
            ax3.legend()
            ax3.grid(True)
            
            ax4 = plt.subplot(2, 2, 4)
            ax4.plot(flight_simulator.fin_tracker.time_points, flight_simulator.fin_tracker.max_temp_history, 'r-', label='Max Temperature')
            if hasattr(flight_simulator.fin_tracker, 'absolute_max_temperature_info') and flight_simulator.fin_tracker.absolute_max_temperature_info:
                ax4.plot(max_info["time"], max_info["temperature"], 'ro', markersize=8, label='Max Temp Point')
                ax4.text(0.05, 0.95, f'Max Temp: {max_info["temperature"]:.1f}K\nTime: {max_info["time"]:.1f}s\nMach: {max_info["mach"]:.2f}', 
                        transform=ax4.transAxes, verticalalignment='top',
                        bbox=dict(facecolor='white', alpha=0.7))
            ax4.set_xlabel('Time (s)')
            ax4.set_ylabel('Temperature (K)')
            ax4.set_title('Maximum Temperature vs Time')
            ax4.legend()
            ax4.grid(True)
            
            plt.tight_layout()
            pdf.savefig(fig3)
            plt.close(fig3)
            
            # Page 4
            critical_points = flight_simulator.fin_tracker.get_critical_time_points()
            if "max_temperature" in critical_points:
                max_temp_time = critical_points["max_temperature"]["time"]
                max_temp_mach = critical_points["max_temperature"]["mach"]
                max_temp_idx = flight_simulator.fin_tracker.time_points.index(max_temp_time)
                
                fig4 = flight_simulator.fin_tracker.plot_temperature_snapshot(max_temp_idx, max_temp_time, max_temp_mach)
                fig4.suptitle("Temperature Distribution at Maximum Temperature", fontsize=16)
                pdf.savefig(fig4)
                plt.close(fig4)
            
            # Page 5
            if "max_velocity" in critical_points:
                max_vel_time = critical_points["max_velocity"]["time"]
                max_vel_mach = critical_points["max_velocity"]["mach"]
                max_vel_idx = flight_simulator.fin_tracker.time_points.index(max_vel_time)
                
                fig5 = flight_simulator.fin_tracker.plot_temperature_snapshot(max_vel_idx, max_vel_time, max_vel_mach)
                fig5.suptitle("Temperature Distribution at Maximum Velocity", fontsize=16)
                pdf.savefig(fig5)
                plt.close(fig5)
        
        # LAST PAGES
        fig_conditions_list = create_initial_conditions_page(
            "flight", 
            material_name=material_name, 
            component_manager=component_manager,
            fast_mode=fast_mode
        )
        for fig_conditions in fig_conditions_list:
            pdf.savefig(fig_conditions)
            plt.close(fig_conditions)

def create_material_comparison_pdf(output_path, results, fast_mode=False, component_manager=None):
    
    with PdfPages(output_path) as pdf:
        # Page 1
        fig1, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12))
        results_margin = sorted(results, key=lambda x: x["Temperature Margin (K)"], reverse=True)
        
        materials = [r["Material"] for r in results_margin]
        max_temps = np.array([r["Max Temperature (K)"] for r in results_margin])
        max_service_temps = np.array([r["Max Service Temp (K)"] for r in results_margin])
        margins = np.array([r["Temperature Margin (K)"] for r in results_margin])
        
        positions = np.arange(len(materials))
        bar_width = 0.35
        
        temp_bars = ax1.bar(positions - bar_width/2, max_temps, bar_width, 
                           label="Max Temperature (K)", color='red', alpha=0.7)
        limit_bars = ax1.bar(positions + bar_width/2, max_service_temps, bar_width, 
                            label="Max Service Temperature (K)", color='blue', alpha=0.6)
        
        for i, (margin, pos) in enumerate(zip(margins, positions)):
            color = 'green' if margin >= 0 else 'red'
            annotation = f"+{margin:.1f}K" if margin >= 0 else f"{margin:.1f}K"
            
            y_pos = max(max_temps[i], max_service_temps[i]) + 20
            ax1.annotate(annotation, xy=(pos, y_pos), ha='center', va='bottom',
                         color=color, weight='bold', fontsize=8)
        
        ax1.set_xlabel("Material")
        ax1.set_ylabel("Temperature (K)")
        ax1.set_title("Temperature Comparison by Material")
        ax1.set_xticks(positions)
        ax1.set_xticklabels(materials, rotation=45, ha='right')
        ax1.legend()
        ax1.grid(True, linestyle='--', alpha=0.7)
        
        results_mass = sorted(results, key=lambda x: x["Mass (kg)"])
        materials_by_mass = [r["Material"] for r in results_mass]
        masses_sorted = np.array([r["Mass (kg)"] for r in results_mass])
        within_limits = [r["Within Limits"] for r in results_mass]
        temp_margins_mass = np.array([r["Temperature Margin (K)"] for r in results_mass])
        
        positions2 = np.arange(len(materials_by_mass))
        mass_bars = ax2.bar(positions2, masses_sorted, label="Total Fins Mass (kg)")
        
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
        
        for bar, color, limit_ok in zip(mass_bars, colors, within_limits):
            bar.set_color(color)
            if not limit_ok:
                bar.set_hatch('///')
        
        for i, mass in enumerate(masses_sorted):
            ax2.annotate(f"{mass:.4f}kg", xy=(i, mass + 0.01),
                       ha='center', va='bottom', fontsize=8)
        
        ax2.set_xlabel("Material")
        ax2.set_ylabel("Mass (kg)")
        ax2.set_title("Mass Comparison by Material (With Temperature Safety Rating)")
        ax2.set_xticks(positions2)
        ax2.set_xticklabels(materials_by_mass, rotation=45, ha='right')
        ax2.grid(True, linestyle='--', alpha=0.7)
        
        import matplotlib.patches as mpatches
        legend_elements = [
            mpatches.Patch(color='red', hatch='///', label='Exceeds Temperature Limit'),
            mpatches.Patch(color='orange', label='Margin < 50K'),
            mpatches.Patch(color='yellow', label='Margin < 150K'),
            mpatches.Patch(color='green', label='Margin ≥ 150K')
        ]
        ax2.legend(handles=legend_elements, loc='upper right')
        
        plt.tight_layout()
        pdf.savefig(fig1)
        plt.close(fig1)
        
        # Page 2
        fig2, ax3 = plt.subplots(figsize=(10, 8))
        
        thermal_conductivities = np.array([r["Thermal Conductivity (W/m·K)"] for r in results])
        densities = np.array([r["Density (kg/m³)"] for r in results])
        emissivities = np.array([r["Emissivity"] for r in results])
        materials_orig = [r["Material"] for r in results]
        margins_orig = np.array([r["Temperature Margin (K)"] for r in results])
        
        colors = np.where(margins_orig < 0, 'red',
                         np.where(margins_orig < 50, 'orange',
                                 np.where(margins_orig < 150, 'yellow', 'green')))
        
        scatter = ax3.scatter(thermal_conductivities, densities, 
                            s=emissivities*500,
                            c=colors, alpha=0.7)
        
        for i, material in enumerate(materials_orig):
            short_name = material.split()[0]
            ax3.annotate(short_name, 
                       xy=(thermal_conductivities[i], densities[i]),
                       xytext=(5, 0), textcoords='offset points',
                       fontsize=8)
        
        ax3.set_xlabel("Thermal Conductivity (W/m·K)")
        ax3.set_ylabel("Density (kg/m³)")
        ax3.set_title("Material Properties Relationship (With Temperature Safety Rating)")
        
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor='gray', 
                  label=f'Low Emissivity: {min(emissivities):.2f}', markersize=8),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='gray', 
                  label=f'High Emissivity: {max(emissivities):.2f}', markersize=16),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='red', 
                  label='Exceeds Limit', markersize=10),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='orange', 
                  label='Margin < 50K', markersize=10),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='yellow', 
                  label='Margin < 150K', markersize=10),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='green', 
                  label='Margin ≥ 150K', markersize=10)
        ]
        
        ax3.legend(handles=legend_elements, loc='best')
        ax3.grid(True, linestyle='--', alpha=0.7)
        
        pdf.savefig(fig2)
        plt.close(fig2)
        
        # Page 3
        fig3, (ax4, ax5) = plt.subplots(1, 2, figsize=(14, 8))
        
        heights = [r["Height (mm)"] for r in results]
        widths = [r["Width (mm)"] for r in results]
        materials_list = [r["Material"] for r in results]
        
        x_pos = np.arange(len(materials_list))
        bars1 = ax4.bar(x_pos, heights, color='skyblue', alpha=0.7)
        ax4.set_xlabel("Material")
        ax4.set_ylabel("Height (mm)")
        ax4.set_title("Fin Height by Material")
        ax4.set_xticks(x_pos)
        ax4.set_xticklabels([m.split()[0] for m in materials_list], rotation=45, ha='right')
        ax4.grid(True, linestyle='--', alpha=0.7)
        
        for bar, height in zip(bars1, heights):
            ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f'{height:.1f}', ha='center', va='bottom', fontsize=8)
        
        bars2 = ax5.bar(x_pos, widths, color='lightcoral', alpha=0.7)
        ax5.set_xlabel("Material")
        ax5.set_ylabel("Width (mm)")
        ax5.set_title("Fin Width by Material")
        ax5.set_xticks(x_pos)
        ax5.set_xticklabels([m.split()[0] for m in materials_list], rotation=45, ha='right')
        ax5.grid(True, linestyle='--', alpha=0.7)
        
        for bar, width in zip(bars2, widths):
            ax5.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f'{width:.1f}', ha='center', va='bottom', fontsize=8)
        
        plt.tight_layout()
        pdf.savefig(fig3)
        plt.close(fig3)
        
        # LAST PAGES
        fig_conditions_list = create_initial_conditions_page(
            "material_comparison", 
            fast_mode=fast_mode,
            component_manager=component_manager
        )
        for fig_conditions in fig_conditions_list:
            pdf.savefig(fig_conditions)
            plt.close(fig_conditions)

def run_single_material_analysis(material_name=None, fast_mode=True):
    analysis_start = time.time()
    
    component_manager = load_team_data()
    
    if material_name is None:
        material_name = config["fin_analysis"]["fin_material"]
    
    print(f"\nRunning flight simulation with fin material: {material_name}")    
    component_manager.print_component_summary()
    print("\nSetting dynamic pressure parameters for fin calculations...")
    
    fin_start = time.time()
    fin_material = get_fin_material()
    fin = RocketFin(material_name=fin_material)
    
    fin.max_q = config["rocket"]["max_q"]
    
    print(f"Setting dynamic pressure (fin.max_q) for fin calculations: {fin.max_q} Pa")
    
    if not fin.set_material(material_name):
        print(f"Error: Material '{material_name}' not found. Using default material.")
        fin.set_material(config["fin_analysis"]["fin_material"])
        material_name = config["fin_analysis"]["fin_material"]
    
    fin.calculate_fin_dimensions(verbose=True)
    fin_time = time.time() - fin_start
    print(f"Fin initialization completed in {fin_time:.3f} seconds")

    tracker = FinTemperatureTracker(fin)
    flight_simulator.fin_tracker = tracker
    flight_simulator.component_manager = component_manager
    
    sim_start = time.time()
    flight_simulator.main(material_name=material_name, fast_mode=fast_mode, skip_animation=True)
    sim_time = time.time() - sim_start
    
    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    material_abbrev = material_name.replace(' ', '_').replace('-', '_')
    pdf_filename = f"FS_{material_abbrev}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)
    
    print(f"\nGenerating comprehensive PDF report: {pdf_filename}")
    pdf_start = time.time()
    create_flight_simulation_pdf(pdf_path, material_name, component_manager, fast_mode)
    pdf_time = time.time() - pdf_start
    print(f"PDF report generated in {pdf_time:.3f} seconds")
    
    if not fast_mode and config["fin_analysis"]["create_temperature_animation"]:
        anim_start = time.time()
        
        output_path = os.path.join(output_dir, f"fin_temp_{material_name.replace(' ', '_')}.mp4")
        
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
                print(f"Removed existing animation file: {output_path}")
            except Exception as e:
                print(f"Warning: Could not remove existing file: {e}")
                output_path = os.path.join(output_dir, f"fin_temp_{material_name.replace(' ', '_')}_{int(time.time())}.mp4")
        
        animation_tracker = flight_simulator.fin_tracker
        if animation_tracker and len(animation_tracker.time_points) > 0:
            print(f"\nCreating temperature animation for {material_name} fins...")
            
            if hasattr(animation_tracker, 'absolute_max_temperature') and animation_tracker.absolute_max_temperature is not None:
                max_temp = animation_tracker.absolute_max_temperature
            else:
                max_temp = max(animation_tracker.max_temp_history) if hasattr(animation_tracker, 'max_temp_history') else 0
                
            if max_temp > animation_tracker.fin.max_service_temp:
                print(f"WARNING: Maximum temperature ({max_temp:.2f}K) exceeds material service limit ({animation_tracker.fin.max_service_temp}K)")
                print(f"Temperature margin: {(animation_tracker.fin.max_service_temp - max_temp):.2f}K (negative indicates excess)")
                
                if hasattr(animation_tracker, 'absolute_max_temperature_info'):
                    max_time = animation_tracker.absolute_max_temperature_info["time"]
                    max_altitude = animation_tracker.absolute_max_temperature_info["altitude"]
                    max_velocity = animation_tracker.absolute_max_temperature_info["velocity"]
                    max_mach = animation_tracker.absolute_max_temperature_info["mach"]
                    
                    print("Maximum temperature occurs at:")
                    print(f"  - Time: {max_time:.2f}s")
                    print(f"  - Altitude: {max_altitude:.2f}m")
                    print(f"  - Velocity: {max_velocity:.2f}m/s")
                    print(f"  - Mach: {max_mach:.2f}")
            else:
                print(f"Material temperature is within limits. Maximum: {max_temp:.2f}K, Service limit: {animation_tracker.fin.max_service_temp}K")
            
            try:
                create_fin_temperature_animation(animation_tracker, output_path)
            except Exception as e:
                print(f"Error creating animation: {e}")
        
        anim_time = time.time() - anim_start
        print(f"Animation creation completed in {anim_time:.3f} seconds")
    
    flight_simulator.clear_simulation_caches()
    
    total_time = time.time() - analysis_start
    print(f"Complete analysis finished in {total_time:.3f} seconds (simulation: {sim_time:.3f}s)")

def run_material_comparison(fast_mode=True):

    comparison_start = time.time()
    component_manager = load_team_data()
    flight_simulator.component_manager = component_manager
    
    print("\nRunning material comparison for all available materials...")
    results = material_comparison_example.compare_fin_materials_for_flight(fast_mode=fast_mode)
    results.sort(key=lambda x: (not x["Within Limits"], x["Mass (kg)"]))
    
    print("\nMaterial Comparison Results (with improved accuracy):")
    print(f"{'Material':<33} {'Max Temp (K)':<12} {'Temp Margin (K)':<15} {'Mass (kg)':<10} {'Within Limits':<15}")
    print("-" * 85)
    
    for result in results:
        print(f"{result['Material']:<33} {result['Max Temperature (K)']:<12.3f} {result['Temperature Margin (K)']:<15.1f} {result['Mass (kg)']:<10.5f} {result['Within Limits']}")
    
    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    mode_suffix = "fast" if fast_mode else "detailed"
    pdf_filename = f"MC_{mode_suffix}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)
    
    print(f"\nGenerating material comparison PDF report: {pdf_filename}")
    pdf_start = time.time()
    create_material_comparison_pdf(pdf_path, results, fast_mode, component_manager)
    pdf_time = time.time() - pdf_start
    print(f"PDF report generated in {pdf_time:.3f} seconds")
    
    best_material = next((r["Material"] for r in results if r["Within Limits"]), None)
    if best_material:
        print(f"\nRecommended material: {best_material}")
        if not fast_mode:
            user_input = input("\nRun detailed analysis for the recommended material? (y/n): ")
            if user_input.lower() == 'y':
                run_single_material_analysis(best_material, fast_mode=False)
    else:
        print("\nWarning: No material can withstand the thermal conditions of this flight profile.")
        results.sort(key=lambda x: -x["Temperature Margin (K)"])
        least_bad_material = results[0]["Material"]
        print(f"Least problematic material: {least_bad_material}")
        if not fast_mode:
            user_input = input("\nRun detailed analysis for this material? (y/n): ")
            if user_input.lower() == 'y':
                run_single_material_analysis(least_bad_material, fast_mode=False)

    flight_simulator.clear_simulation_caches()
    comparison_time = time.time() - comparison_start
    print(f"Material comparison completed in {comparison_time:.3f} seconds")

def run_stability_analysis(flight_stage=None):
    stability_start = time.time()
    component_manager = load_team_data()
    
    fin_init_start = time.time()
    fin_material = get_fin_material()
    fin = RocketFin(material_name=fin_material)
    fin.calculate_fin_dimensions(verbose=False)
    fin_init_time = time.time() - fin_init_start
    
    stability = RocketStability()
    stability.set_fin_properties(fin)
    component_manager.print_component_summary()    
    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    if flight_stage is None or flight_stage == "all":
        print("\nRunning full flight simulation to get trajectory data...")
        sim_start = time.time()
        tracker = FinTemperatureTracker(fin)
        flight_simulator.fin_tracker = tracker
        flight_simulator.component_manager = component_manager  # Pass the component manager to main
        flight_simulator.main(material_name=config["fin_analysis"]["fin_material"], fast_mode=True, skip_animation=True)
        sim_time = time.time() - sim_start
        print(f"Flight simulation completed in {sim_time:.3f} seconds")
        print("\nGenerating stability diagrams throughout flight...")
        plot_start = time.time()
        fig = flight_simulator.plot_stability_during_flight()
        plot_time = time.time() - plot_start
        
        pdf_filename = "SA_all_stages.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)
        
        print(f"Generating stability analysis PDF: {pdf_filename}")
        pdf_start = time.time()
        with PdfPages(pdf_path) as pdf:
            pdf.savefig(fig)
            fig_conditions_list = create_initial_conditions_page(
                "stability", 
                flight_stage="all",
                component_manager=component_manager
            )
            for fig_conditions in fig_conditions_list:
                pdf.savefig(fig_conditions)
                plt.close(fig_conditions)
        pdf_time = time.time() - pdf_start
        plt.close(fig)
        
        print(f"PDF report generated in {pdf_time:.3f} seconds")
        print(f"Plotting completed in {plot_time:.3f} seconds")
    else:
        print(f"\nAnalyzing stability at flight stage: {flight_stage}")
        
        propellant_mass = component_manager.get_component_data().get("propellant", {}).get("mass", config["mass_properties"]["propellant_mass"])
        
        if flight_stage.lower() == "launch":
            stability.set_flight_conditions(mach=0.1)
            stability.set_propellant_mass(propellant_mass)
        elif flight_stage.lower() == "burnout":
            stability.set_flight_conditions(mach=2.0)
            stability.set_propellant_mass(0)
        elif flight_stage.lower() == "apogee":
            stability.set_flight_conditions(mach=0.5)
            stability.set_propellant_mass(0)
        elif flight_stage.lower() == "landing":
            stability.set_flight_conditions(mach=0.2)
            stability.set_propellant_mass(0)
        else:
            print(f"Unknown flight stage: {flight_stage}")
            print("Available stages: launch, burnout, apogee, landing")
            return
        
        calc_start = time.time()
        stability.calculate_center_of_mass()
        stability.calculate_center_of_pressure()
        stability.calculate_stability()
        calc_time = time.time() - calc_start
        
        print("\nStability Analysis Results:")
        print(f"Center of Mass position: {stability.center_of_mass:.3f} m from nose tip")
        print(f"Center of Pressure position: {stability.center_of_pressure:.3f} m from nose tip")
        print(f"Stability margin: {stability.stability_margin:.3f} m")
        print(f"Stability in calibers: {stability.stability_calibers:.2f}")
        print(f"Stability status: {stability.get_stability_status()}")
        print(f"Calculation completed in {calc_time:.4f} seconds")
        
        plot_start = time.time()
        fig, ax = stability.plot_stability_diagram(show_components=True)
        plot_time = time.time() - plot_start
        
        pdf_filename = f"SA_{flight_stage}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)
        
        print(f"Generating stability analysis PDF: {pdf_filename}")
        pdf_start = time.time()
        with PdfPages(pdf_path) as pdf:
            pdf.savefig(fig)
            fig_conditions_list = create_initial_conditions_page(
                "stability", 
                flight_stage=flight_stage,
                component_manager=component_manager
            )
            for fig_conditions in fig_conditions_list:
                pdf.savefig(fig_conditions)
                plt.close(fig_conditions)
        pdf_time = time.time() - pdf_start
        plt.close(fig)
        
        print(f"PDF report generated in {pdf_time:.3f} seconds")
        print(f"Plotting completed in {plot_time:.3f} seconds")

    
    flight_simulator.clear_simulation_caches()
    
    stability_time = time.time() - stability_start
    print(f"Stability analysis completed in {stability_time:.3f} seconds")

def manage_team_data():
    management_start = time.time()
    component_manager = ComponentData()
    
    print("\nComponent Data Management:")
    print("1. Create template files for teams")
    print("2. Load team data from files")
    print("3. Show component summary")
    print("4. Exit")
    
    choice = input("\nEnter choice (1-4): ")
    
    if choice == '1':
        template_start = time.time()
        component_manager.create_all_templates()
        template_time = time.time() - template_start
        print(f"\nTemplate files created in {template_time:.3f} seconds")
        print("Distribute these files to the respective teams to fill in their component data")
    elif choice == '2':
        load_start = time.time()
        component_manager.update_from_team_files()
        component_manager.update_config(config)
        load_time = time.time() - load_start
        print(f"\nTeam data loaded and config updated in {load_time:.3f} seconds")
    elif choice == '3':
        summary_start = time.time()
        component_manager.print_component_summary()
        summary_time = time.time() - summary_start
        print(f"Summary generated in {summary_time:.4f} seconds")
    elif choice == '4':
        print("Exiting...")
    else:
        print("Invalid choice")
    
    management_time = time.time() - management_start
    print(f"Team data management completed in {management_time:.3f} seconds")

def run_trajectory_optimization():

    optimization_start = time.time()
    
    print("\nRunning trajectory optimization analysis...")
    
    component_manager = load_team_data()
    flight_simulator.component_manager = component_manager
    print("Simulating current configuration...")
    sim_start = time.time()
    used_material = flight_simulator.init(material_name=config["fin_analysis"]["fin_material"], fast_mode=True)
    limit_reached = flight_simulator.run_simulation()
    sim_time = time.time() - sim_start
    print(f"Simulation completed in {sim_time:.3f} seconds")
    
    analysis_start = time.time()
    optimizer = TrajectoryOptimizer(target_altitude=100000)
    
    results = optimizer.analyze_trajectory(flight_simulator.r, flight_simulator.rc, flight_simulator.time_points)
    suggestions = optimizer.generate_suggestions()
    analysis_time = time.time() - analysis_start
    print(f"Analysis completed in {analysis_time:.3f} seconds")
    print("\n" + optimizer.generate_report())
    
    print("\nGenerating analysis plots...")
    plot_start = time.time()
    fig = optimizer.plot_analysis()
    plot_time = time.time() - plot_start
    
    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    save_start = time.time()
    pdf_filename = "TO_analysis.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)
    
    print(f"Generating trajectory optimization PDF: {pdf_filename}")
    with PdfPages(pdf_path) as pdf:
        pdf.savefig(fig)
        fig_conditions_list = create_initial_conditions_page(
            "trajectory", 
            target_altitude=100000,
            component_manager=component_manager
        )
        for fig_conditions in fig_conditions_list:
            pdf.savefig(fig_conditions)
            plt.close(fig_conditions)
    save_time = time.time() - save_start
    
    print(f"PDF report generated in {save_time:.3f} seconds")
    print(f"Plotting completed in {plot_time:.3f} seconds")
    
    if suggestions and optimizer.altitude_deficit > 0:
        print("\nWould you like to explore specific optimization scenarios?")
        print("1. Mass reduction details")
        print("2. Aerodynamic improvements")
        print("3. Propellant optimization")
        print("4. Return to main menu")
        
        choice = input("\nEnter choice (1-4): ")
        
        if choice in ['1', '2', '3']:
            category_map = {
                '1': 'Mass Reduction',
                '2': 'Aerodynamics', 
                '3': 'Propellant Optimization'
            }
            
            category = category_map.get(choice)
            filtered = [s for s in suggestions if s['category'] == category or s['category'] == 'Structural Optimization']
            
            if filtered:
                print(f"\n{category} Details:")
                print("-" * 40)
                for suggestion in filtered:
                    print(f"\n• {suggestion['suggestion']}")
                    print(f"  Impact: {suggestion['impact']}")
                    if 'implementation' in suggestion:
                        print(f"  How to implement: {suggestion['implementation']}")
            else:
                print(f"\nNo specific suggestions available for {category}")
    
    flight_simulator.clear_simulation_caches()
    optimization_time = time.time() - optimization_start
    print(f"Trajectory optimization completed in {optimization_time:.3f} seconds")

def main_menu():
    menu_start = time.time()
    
    while True:
        print("\n===== Rocket Analysis Tools =====")
        print("1. Run flight simulation with default material")
        print("2. Run flight simulation with specific material")
        print("3. Run material comparison (fast mode)")
        print("4. Run material comparison (detailed mode)")
        print("5. Run stability analysis (all flight stages)")
        print("6. Run stability analysis (specific flight stage)")
        print("7. Trajectory optimization (100km target)") 
        print("8. Manage team component data")
        print("9. Configure settings")
        print("0. Exit")
        
        choice = input("\nEnter choice (1-0): ")
        choice_start = time.time()
        
        if choice == '1':
            run_single_material_analysis(fast_mode=False)
        elif choice == '2':
            material_start = time.time()
            fin_material = get_fin_material()
            fin = RocketFin(material_name=fin_material)
            materials = fin.get_available_materials()
            material_load_time = time.time() - material_start
            
            print(f"\nAvailable materials (loaded in {material_load_time:.3f}s):")
            for i, material in enumerate(materials, 1):
                print(f"{i}. {material}")
            
            mat_choice = input("\nSelect material (enter number): ")
            try:
                mat_idx = int(mat_choice) - 1
                if 0 <= mat_idx < len(materials):
                    run_single_material_analysis(materials[mat_idx], fast_mode=False)
                else:
                    print("Invalid selection, using default material.")
                    run_single_material_analysis(fast_mode=False)
            except ValueError:
                print("Invalid input, using default material.")
                run_single_material_analysis(fast_mode=False)
        elif choice == '3':
            run_material_comparison(fast_mode=True)
        elif choice == '4':
            run_material_comparison(fast_mode=False)
        elif choice == '5':
            run_stability_analysis(flight_stage="all")
        elif choice == '6':
            print("\nAvailable flight stages:")
            print("1. Launch")
            print("2. Burnout")
            print("3. Apogee")
            print("4. Landing")
            
            stage_choice = input("\nSelect flight stage (enter number): ")
            stages = ["launch", "burnout", "apogee", "landing"]
            
            try:
                stage_idx = int(stage_choice) - 1
                if 0 <= stage_idx < len(stages):
                    run_stability_analysis(flight_stage=stages[stage_idx])
                else:
                    print("Invalid selection, analyzing all stages.")
                    run_stability_analysis(flight_stage="all")
            except ValueError:
                print("Invalid input, analyzing all stages.")
                run_stability_analysis(flight_stage="all")
        elif choice == '7': 
            run_trajectory_optimization()
        elif choice == '8':
            manage_team_data()
        elif choice == '9':
            settings_and_materials_menu()
        elif choice == '0': 
            plt.close('all')
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 9.")
        
        choice_time = time.time() - choice_start
        print(f"Menu option completed in {choice_time:.3f} seconds")
    
    menu_time = time.time() - menu_start
    print(f"Menu session lasted {menu_time:.3f} seconds")
            
if __name__ == "__main__":
    execution_start = time.time()
    bootstrap()
    
    parser = argparse.ArgumentParser(description="Rocket Analysis Tools (Optimized)")
    parser.add_argument("-m", "--material", help="Specify fin material")
    parser.add_argument("-c", "--compare", action="store_true", help="Run material comparison")
    parser.add_argument("-f", "--fast", action="store_true", help="Run in fast mode")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive menu mode")
    parser.add_argument("-s", "--stability", action="store_true", help="Run stability analysis")
    parser.add_argument("--stage", help="Flight stage for stability analysis (launch, burnout, apogee, landing)")
    parser.add_argument("-t", "--team-data", action="store_true", help="Manage team component data")
    
    args = parser.parse_args()

    if args.interactive:
        main_menu()
    elif args.stability:
        run_stability_analysis(flight_stage=args.stage)
    elif args.team_data:
        manage_team_data()
    elif args.compare:
        run_material_comparison(fast_mode=args.fast)
    elif args.material:
        run_single_material_analysis(args.material, fast_mode=args.fast)
    else:
        run_single_material_analysis(fast_mode=args.fast)
    
    execution_time = time.time() - execution_start
    print(f"\nTotal program execution time: {execution_time:.3f} seconds")
    