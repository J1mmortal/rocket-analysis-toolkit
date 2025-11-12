import numpy as np
import matplotlib.pyplot as plt
from src.rocket_toolkit.geometry.rocket_fin import RocketFin
from src.rocket_toolkit.core.fin_temperature_tracker import FinTemperatureTracker
from src.rocket_toolkit.core import flight_simulator
from src.rocket_toolkit import config
import time

def compare_fin_materials_for_flight(fast_mode=True):
    start_time = time.time()
    
    rocket_fin = RocketFin()
    materials = rocket_fin.get_available_materials()
    results = []
    
    print(f"Starting material comparison for {len(materials)} materials...")
    print("Pre-calculating fin dimensions for all materials...")
    precalc_start = time.time()
    rocket_fin.calculate_all_material_dimensions(verbose=False)
    print(f"Fin dimensions pre-calculated in {time.time() - precalc_start:.3f} seconds")
    
    if fast_mode:
        original_mesh_size = flight_simulator.mesh_size
        flight_simulator.mesh_size = 12  # Smaller mesh for speed
    
    if not hasattr(config, 'max_q') or config.max_q <= 0:
        print("Running initial simulation to determine dynamic pressure parameters...")
        from component_manager import ComponentData
        component_manager = ComponentData()
        component_manager.update_from_team_files()
        component_manager.update_config()
        
        flight_simulator.component_manager = component_manager
        flight_simulator.main(material_name="Titanium Ti-6Al-4V", fast_mode=True, skip_animation=True)
        print(f"Initial simulation completed. Maximum dynamic pressure: {config.max_q:.1f} Pa")
    
    rocket_fin.max_q = config.max_q
    print(f"Using dynamic pressure (max_q) for all material comparisons: {rocket_fin.max_q:.1f} Pa")
    
    simulation_times = []
    
    for i, material in enumerate(materials):
        material_start_time = time.time()
        progress = (i + 1) / len(materials)
        
        if i == 0:
            print(f"Running material {i+1}/{len(materials)}: {material}")
        else:
            avg_time = np.mean(simulation_times)
            remaining_materials = len(materials) - i
            estimated_remaining = avg_time * remaining_materials
            
            print(f"Running material {i+1}/{len(materials)}: {material} - "
                  f"{progress:.1%} complete. Est. remaining: {estimated_remaining:.1f}s")
        
        flight_simulator.r = None
        flight_simulator.rc = None
        flight_simulator.ec = None
        flight_simulator.time_points = None
        flight_simulator.fin_tracker = None
        
        sim_start = time.time()
        flight_simulator.main(material_name=material, fast_mode=fast_mode, skip_animation=True)
        sim_time = time.time() - sim_start
        simulation_times.append(sim_time)
        
        if hasattr(flight_simulator.fin_tracker, 'absolute_max_temperature') and flight_simulator.fin_tracker.absolute_max_temperature is not None:
            max_temp = flight_simulator.fin_tracker.absolute_max_temperature
            critical_points = flight_simulator.fin_tracker.get_critical_time_points()
        else:
            max_temp = flight_simulator.fin_tracker.get_max_temperature()
            critical_points = flight_simulator.fin_tracker.get_critical_time_points()
        
        fin = flight_simulator.fin_tracker.fin
        max_service_temp = fin.max_service_temp
        temp_margin = max_service_temp - max_temp
        within_limits = temp_margin >= 0
        
        results.append({
            "Material": material,
            "Max Temperature (K)": max_temp,
            "Max Service Temp (K)": max_service_temp,
            "Temperature Margin (K)": temp_margin,
            "Within Limits": within_limits,
            "Mass (kg)": fin.fin_mass * fin.num_fins,
            "Max Temp Time (s)": critical_points["max_temperature"]["time"] if "max_temperature" in critical_points else 0,
            "Height (mm)": fin.fin_height,
            "Width (mm)": fin.fin_width,
            "Thermal Conductivity (W/m·K)": fin.thermal_conductivity,
            "Density (kg/m³)": fin.density,
            "Emissivity": fin.emissivity,
            "Simulation Time (s)": sim_time
        })
        
        if hasattr(flight_simulator.fin_tracker, 'thermal_analyzer'):
            if hasattr(flight_simulator.fin_tracker.thermal_analyzer, 'clear_caches'):
                flight_simulator.fin_tracker.thermal_analyzer.clear_caches()
        
        material_total_time = time.time() - material_start_time
        print(f"  Material {material} completed in {material_total_time:.3f}s (sim: {sim_time:.3f}s)")
    
    if fast_mode:
        flight_simulator.mesh_size = original_mesh_size
    
    total_time = time.time() - start_time
    avg_sim_time = np.mean(simulation_times)
    
    print(f"\nMaterial comparison completed in {total_time:.2f} seconds")
    print(f"Average simulation time per material: {avg_sim_time:.3f} seconds")
    print(f"Total simulation time: {sum(simulation_times):.3f} seconds")
    print(f"Overhead time: {total_time - sum(simulation_times):.3f} seconds")
    
    results.sort(key=lambda x: (not x["Within Limits"], x["Mass (kg)"]))
    
    return results

if __name__ == "__main__":
    print("Starting optimized material comparison...")
    start_time = time.time()
    
    results = compare_fin_materials_for_flight(fast_mode=True)
    
    print(f"\nTotal execution time: {time.time() - start_time:.3f} seconds")
    print(f"Number of materials compared: {len(results)}")
    
    sim_times = [r["Simulation Time (s)"] for r in results]
    print("\nPerformance Summary:")
    print(f"  Fastest simulation: {min(sim_times):.3f}s")
    print(f"  Slowest simulation: {max(sim_times):.3f}s")
    print(f"  Average simulation: {np.mean(sim_times):.3f}s")
    print(f"  Total simulation time: {sum(sim_times):.3f}s")
    
    print("\nMaterial Comparison Results:")
    print(f"{'Material':<33} {'Max Temp (K)':<12} {'Temp Margin (K)':<15} {'Mass (kg)':<10} {'Within Limits':<15}")
    print("-" * 85)
    
    for result in results:
        print(f"{result['Material']:<33} {result['Max Temperature (K)']:<12.3f} {result['Temperature Margin (K)']:<15.1f} {result['Mass (kg)']:<10.5f} {result['Within Limits']}")