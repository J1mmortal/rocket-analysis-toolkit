import numpy as np
import matplotlib.pyplot as plt
from rocket_fin_dimensions import RocketFin
from rocket_fin_tracker import FinTemperatureTracker
import main
import config
import time

def compare_fin_materials_for_flight(fast_mode=True):
    """
    Optimized material comparison with aggressive performance improvements
    """
    start_time = time.time()
    
    rocket_fin = RocketFin()
    materials = rocket_fin.get_available_materials()
    results = []
    
    print(f"Starting material comparison for {len(materials)} materials...")
    
    # PRE-CALCULATION PHASE: Calculate all fin dimensions once
    print("Pre-calculating fin dimensions for all materials...")
    precalc_start = time.time()
    rocket_fin.calculate_all_material_dimensions(verbose=False)
    print(f"Fin dimensions pre-calculated in {time.time() - precalc_start:.3f} seconds")
    
    # OPTIMIZATION: Set up consistent mesh size
    if fast_mode:
        original_mesh_size = main.mesh_size
        main.mesh_size = 12  # Smaller mesh for speed
    
    # OPTIMIZATION: Determine max_q once if not set
    if not hasattr(config, 'max_q') or config.max_q <= 0:
        print("Running initial simulation to determine dynamic pressure parameters...")
        from component_manager import ComponentData
        component_manager = ComponentData()
        component_manager.update_from_team_files()
        component_manager.update_config()
        
        main.component_manager = component_manager
        main.main(skip_plots=True, material_name="Titanium Ti-6Al-4V", fast_mode=True, skip_animation=True)
        print(f"Initial simulation completed. Maximum dynamic pressure: {config.max_q:.1f} Pa")
    
    rocket_fin.max_q = config.max_q
    print(f"Using dynamic pressure (max_q) for all material comparisons: {rocket_fin.max_q:.1f} Pa")
    
    # MAIN COMPARISON LOOP - HEAVILY OPTIMIZED
    simulation_times = []
    
    for i, material in enumerate(materials):
        material_start_time = time.time()
        progress = (i + 1) / len(materials)
        
        # Progress reporting (optimized)
        if i == 0:
            print(f"Running material {i+1}/{len(materials)}: {material}")
        else:
            avg_time = np.mean(simulation_times)
            remaining_materials = len(materials) - i
            estimated_remaining = avg_time * remaining_materials
            
            print(f"Running material {i+1}/{len(materials)}: {material} - "
                  f"{progress:.1%} complete. Est. remaining: {estimated_remaining:.1f}s")
        
        # OPTIMIZATION: Reset main module state efficiently
        main.r = None
        main.rc = None
        main.ec = None
        main.time_points = None
        main.fin_tracker = None
        
        # Run optimized simulation
        sim_start = time.time()
        main.main(skip_plots=True, material_name=material, fast_mode=fast_mode, skip_animation=True)
        sim_time = time.time() - sim_start
        simulation_times.append(sim_time)
        
        # OPTIMIZATION: Get maximum temperature efficiently
        if hasattr(main.fin_tracker, 'absolute_max_temperature') and main.fin_tracker.absolute_max_temperature is not None:
            max_temp = main.fin_tracker.absolute_max_temperature
            critical_points = main.fin_tracker.get_critical_time_points()
        else:
            max_temp = main.fin_tracker.get_max_temperature()
            critical_points = main.fin_tracker.get_critical_time_points()
        
        # Get fin properties efficiently
        fin = main.fin_tracker.fin
        max_service_temp = fin.max_service_temp
        temp_margin = max_service_temp - max_temp
        within_limits = temp_margin >= 0
        
        # Store results
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
        
        # Clear thermal analyzer caches to free memory
        if hasattr(main.fin_tracker, 'thermal_analyzer'):
            if hasattr(main.fin_tracker.thermal_analyzer, 'clear_caches'):
                main.fin_tracker.thermal_analyzer.clear_caches()
        
        material_total_time = time.time() - material_start_time
        print(f"  Material {material} completed in {material_total_time:.3f}s (sim: {sim_time:.3f}s)")
    
    # OPTIMIZATION: Restore original mesh size
    if fast_mode:
        main.mesh_size = original_mesh_size
    
    total_time = time.time() - start_time
    avg_sim_time = np.mean(simulation_times)
    
    print(f"\nMaterial comparison completed in {total_time:.2f} seconds")
    print(f"Average simulation time per material: {avg_sim_time:.3f} seconds")
    print(f"Total simulation time: {sum(simulation_times):.3f} seconds")
    print(f"Overhead time: {total_time - sum(simulation_times):.3f} seconds")
    
    # Sort results by temperature margin and mass
    results.sort(key=lambda x: (not x["Within Limits"], x["Mass (kg)"]))
    
    return results

# Remove all plotting functions since they're now handled in run_analysis.py
# The old plot_material_comparison function is no longer needed

if __name__ == "__main__":
    print("Starting optimized material comparison...")
    start_time = time.time()
    
    results = compare_fin_materials_for_flight(fast_mode=True)
    
    print(f"\nTotal execution time: {time.time() - start_time:.3f} seconds")
    print(f"Number of materials compared: {len(results)}")
    
    # Performance summary
    sim_times = [r["Simulation Time (s)"] for r in results]
    print(f"\nPerformance Summary:")
    print(f"  Fastest simulation: {min(sim_times):.3f}s")
    print(f"  Slowest simulation: {max(sim_times):.3f}s")
    print(f"  Average simulation: {np.mean(sim_times):.3f}s")
    print(f"  Total simulation time: {sum(sim_times):.3f}s")
    
    # Print results table without showing plots
    print("\nMaterial Comparison Results:")
    print(f"{'Material':<33} {'Max Temp (K)':<12} {'Temp Margin (K)':<15} {'Mass (kg)':<10} {'Within Limits':<15}")
    print("-" * 85)
    
    for result in results:
        print(f"{result['Material']:<33} {result['Max Temperature (K)']:<12.3f} {result['Temperature Margin (K)']:<15.1f} {result['Mass (kg)']:<10.5f} {result['Within Limits']}")