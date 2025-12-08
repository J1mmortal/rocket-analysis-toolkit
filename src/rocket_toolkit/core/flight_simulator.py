import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import os
import json
import time
from src.rocket_toolkit.geometry.rocket_fin import RocketFin
from src.rocket_toolkit.core.fin_temperature_tracker import FinTemperatureTracker
from src.rocket_toolkit.core.stability_analyzer import RocketStability
from src.rocket_toolkit.geometry.component_manager import ComponentData
from src.rocket_toolkit.plotting import fin_animation
import docs.examples.material_comparison_example
import isacalc as isa

std_atm = isa.Atmosphere()

r = None
rc = None
ec = None
time_points = None
fin_tracker = None
component_manager = None  
mesh_size = 20

_cache = {}
_atmosphere_cache = {}

config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

def get_cached_atmosphere(altitude):
    global _atmosphere_cache
    
    cache_key = round(altitude / 100) * 100  # Round to nearest 100m
    if cache_key not in _atmosphere_cache:
        _atmosphere_cache[cache_key] = std_atm.calculate(cache_key)
        # Limit cache size
        if len(_atmosphere_cache) > 100:
            oldest_keys = list(_atmosphere_cache.keys())[:50]
            for key in oldest_keys:
                del _atmosphere_cache[key]
    return _atmosphere_cache[cache_key]

class rocket_variables:
    def __init__(self, speed, altitude, fuel_mass, nose_cone_temp, engine_isp, dynamic_pressure):
        self.speed = speed
        self.altitude = altitude
        self.fuel_mass = fuel_mass
        self.nose_cone_temp = nose_cone_temp
        self.engine_isp = engine_isp
        self.dynamic_pressure = dynamic_pressure

class rocket_constants:
    def __init__(self, dry_weight, fuel_flow_rate, rocket_radius, drag_coefficient, isp_sea, isp_vac):
        self.dry_weight = dry_weight
        self.fuel_flow_rate = fuel_flow_rate
        self.rocket_radius = rocket_radius
        self.drag_coefficient = drag_coefficient
        self.isp_sea = isp_sea
        self.isp_vac = isp_vac

class earth_constants:
    def __init__(self, gravitational_constant, mass_earth, earth_radius):
        self.gravitational_constant = gravitational_constant
        self.mass_earth = mass_earth
        self.earth_radius = earth_radius

def load_component_data():
    global component_manager
    if component_manager is None:
        component_manager = ComponentData()
    component_manager.update_from_team_files()
    component_data = component_manager.get_component_data()
    dry_weight = 0
    propellant_mass = 0
    
    for name, data in component_data.items():
        if "propellant" in name.lower():
            propellant_mass += data["mass"]
        else:
            dry_weight += data["mass"]
    
    if propellant_mass == 0:
        propellant_mass = config["mass_properties"]["propellant_mass"]
        
    min_realistic_dry_weight = 30  
    if dry_weight < min_realistic_dry_weight:
        print(f"WARNING: Dry weight of {dry_weight:.2f} kg is unrealistically low for this rocket!")
        print("Consider increasing structural component masses for more realistic results.")
    
    return dry_weight, propellant_mass

def altitude_adjusted_isp(r1, isp_sea, isp_vac):
    height = r1.altitude
    atm_data = get_cached_atmosphere(height)
    P = atm_data[2]
    P0 = get_cached_atmosphere(0)[2]
    isp = isp_vac - (isp_vac - isp_sea) * (P / P0)
    return isp

def engine_thrust(r1, rc, ec, burn_time, t):
    if t >= burn_time:
        return 0
    
    g = ec.gravitational_constant * ec.mass_earth / (r1.altitude + ec.earth_radius)**2
    F = rc.fuel_flow_rate * r1.engine_isp * g
    return F

def drag_force(r1, rc):
    height = r1.altitude
    atm_data = get_cached_atmosphere(height)
    rho = atm_data[3]
    
    A = np.pi * rc.rocket_radius ** 2
    speed = r1.speed
    
    Fd = -0.5 * rho * rc.drag_coefficient * A * speed * abs(speed)
    return Fd

def gravitational_force(r1, rc, ec):
    m = r1.fuel_mass + rc.dry_weight
    distance_squared = (ec.earth_radius + r1.altitude)**2
    Fg = -ec.gravitational_constant * m * ec.mass_earth / distance_squared
    return Fg

def Fres(F, Fd, Fg):
    return F + Fd + Fg

def acceleration(Fres, mass):
    return Fres / mass

def mach_Number(r1):
    height = r1.altitude
    atm_data = get_cached_atmosphere(height)
    local_speed_of_sound = atm_data[4]
    M = r1.speed / local_speed_of_sound
    return M

def nose_cone_temp(r1):
    height = r1.altitude
    atm_data = get_cached_atmosphere(height)
    T0 = atm_data[1]
    M = mach_Number(r1)
    Tstag = T0 * (1 + 0.2 * M**2)
    return Tstag

def dynamic_pressure(r1):
    height = r1.altitude
    speed = r1.speed
    atm_data = get_cached_atmosphere(height)
    rho = atm_data[3]
    q = 0.5 * rho * speed**2
    return q

def init(material_name=None, fast_mode=False):
    init_start = time.time()
    global r, rc, ec, time_points, fin_tracker, component_manager
    time_points = [0]
    dry_weight, propellant_mass = load_component_data()
    atm_data = get_cached_atmosphere(config["simulation"]["h0"])
    initial_nose_cone_temp = atm_data[1]
    r0 = rocket_variables(
        config["simulation"]["v0"], 
        config["simulation"]["h0"], 
        propellant_mass,
        initial_nose_cone_temp, 
        config["engine"]["isp_sea"], 
        config["simulation"]["q0"]
    )
    r = [r0]
    
    rc = rocket_constants(
        dry_weight,
        config["engine"]["fuel_flow_rate"], 
        config["rocket"]["diameter"]/2, 
        config["rocket"]["drag_coefficient"], 
        config["engine"]["isp_sea"], 
        config["engine"]["isp_vac"]
    )
    
    ec = earth_constants(
        config["earth_constants"]["gravitational_constant"], 
        config["earth_constants"]["mass_earth"], 
        config["earth_constants"]["earth_radius"]
    )
    
    fin = RocketFin()
    
    if material_name is not None:
        fin.set_material(material_name)
    else:
        selected_material = config["fin_analysis"]["fin_material"] if hasattr(config, 'fin_material') else "Titanium Ti-6Al-4V"
        fin.set_material(selected_material)
    
    fin.calculate_fin_dimensions(verbose=False)
    component_manager.add_calculated_fin_mass(fin.fin_mass, config["mass_properties"]["fin_set_cg_position"], fin.num_fins)

    fin_tracker = FinTemperatureTracker(fin)
    if fast_mode and hasattr(fin_tracker.thermal_analyzer, 'set_comparison_mode'):
        fin_tracker.thermal_analyzer.set_comparison_mode(True)
    init_time = time.time() - init_start
    if not fast_mode:
        print(f"Simulation initialized with team data - Dry weight: {dry_weight:.2f} kg, Propellant: {propellant_mass:.2f} kg")
        
        mass_ratio = propellant_mass / dry_weight if dry_weight > 0 else float('inf')
        if mass_ratio > 30:
            print(f"WARNING: Mass ratio (propellant/dry) of {mass_ratio:.1f} is unusually high!")
            print("This may lead to unrealistic simulation results.")
            print("Typical mass ratios for orbital rockets are between 10:1 and 20:1")
        
        print(f"Initialization completed in {init_time:.3f} seconds")
    
    return fin_tracker.fin.material_name

def run_simulation():
    sim_start = time.time()
    global r, time_points
    
    t = 0
    burn_time = r[0].fuel_mass / rc.fuel_flow_rate if rc.fuel_flow_rate > 0 else 0  # seconds
    
    upwards = True
    run = True
    end = 0
    altitude_limit = 500000
    limit_reached = False
    t += config["simulation"]["dt"]
    fin_tracker.update(0.0, r[0].altitude, r[0].speed, config["simulation"]["dt"])
    dt = config["simulation"]["dt"]
    afterTopReached = config["simulation"]["after_top_reached"]
    
    iteration_count = 0
    while run:
        iteration_count += 1
        current_state = r[-1]
        
        thrust = engine_thrust(current_state, rc, ec, burn_time, t)
        drag = drag_force(current_state, rc)
        gravity = gravitational_force(current_state, rc, ec)

        total_mass = rc.dry_weight + current_state.fuel_mass
        a = acceleration(Fres(thrust, drag, gravity), total_mass)
        
        speed = current_state.speed + a * dt
        avg_speed = (current_state.speed + speed) * 0.5
        altitude = current_state.altitude + avg_speed * dt

        if altitude > altitude_limit:
            altitude = altitude_limit
            limit_reached = True
            if iteration_count % 1000 == 0:
                print(f"WARNING: Hit altitude limit of {altitude_limit/1000:.0f} km at time t={t:.1f}s")
        elif altitude < 0:
            altitude = 0 
            speed = 0  
            print(f"Rocket landing at t={t:.1f}s")

        if current_state.fuel_mass > 0:
            fuel_mass = max(0, current_state.fuel_mass - rc.fuel_flow_rate * dt)
        else:
            fuel_mass = 0

        nose_cone_temperature = nose_cone_temp(current_state)
        engine_isp = altitude_adjusted_isp(current_state, rc.isp_sea, rc.isp_vac)
        q = dynamic_pressure(current_state)

        new = rocket_variables(speed, altitude, fuel_mass, nose_cone_temperature, engine_isp, q)
        r.append(new)
        
        if not hasattr(fin_tracker.thermal_analyzer, 'is_comparison_mode') or not fin_tracker.thermal_analyzer.is_comparison_mode or iteration_count % 5 == 0:
            fin_tracker.update(t, altitude, abs(speed), dt)
        if speed < 0:
            upwards = False
        if not upwards:
            end += 1
        if end >= afterTopReached or altitude == 0:
            run = False
        
        t += dt
        time_points.append(t)
    
    if hasattr(fin_tracker.thermal_analyzer, 'max_temperature_reached'):
        masked_max = np.ma.array(
            fin_tracker.thermal_analyzer.max_temperature_reached,
            mask=fin_tracker.mask if hasattr(fin_tracker, 'mask') else None
        )
        global_max = np.max(masked_max)
        
        if (not hasattr(fin_tracker, 'absolute_max_temperature') or 
            fin_tracker.absolute_max_temperature is None or 
            global_max > fin_tracker.absolute_max_temperature):
            
            max_idx = np.argmax(fin_tracker.max_temp_history)
            fin_tracker.absolute_max_temperature = global_max
            fin_tracker.absolute_max_temperature_info = {
                "time": fin_tracker.time_points[max_idx],
                "altitude": fin_tracker.altitude_history[max_idx],
                "velocity": fin_tracker.velocity_history[max_idx],
                "mach": fin_tracker.mach_history[max_idx],
                "temperature": global_max
            }
    
    sim_time = time.time() - sim_start
    if not hasattr(fin_tracker.thermal_analyzer, 'is_comparison_mode') or not fin_tracker.thermal_analyzer.is_comparison_mode:
        print(f"Flight simulation completed in {sim_time:.3f} seconds ({iteration_count} iterations)")
    
    return limit_reached

def main(material_name=None, fast_mode=False, skip_animation=False):
    start_time = time.time()
    
    used_material = init(material_name, fast_mode)
    
    if not fast_mode:
        print(f"Running simulation with {used_material} fins...")
    
    limit_reached = run_simulation()
    
    if not fast_mode:
        report(limit_reached)
    
    if fast_mode and hasattr(fin_tracker.thermal_analyzer, 'set_comparison_mode'):
        fin_tracker.thermal_analyzer.set_comparison_mode(False)

    
    plot_start = time.time()
    flight_fig = plot_flight_data()  
    temp_figs = plot_fin_temperature()
    plot_time = time.time() - plot_start
    
    if not fast_mode:
        print(f"Plotting completed in {plot_time:.3f} seconds")

    if not fast_mode and not skip_animation and hasattr(config, 'create_temperature_animation') and config["fin_analysis"]["create_temperature_animation"]:
        anim_start = time.time()
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        material_name_clean = fin_tracker.fin.material_name.replace(' ', '_')
        output_path = os.path.join(output_dir, f"fin_temp_{material_name_clean}.mp4")
        fin_animation.create_fin_temperature_animation(fin_tracker, output_path)
        anim_time = time.time() - anim_start
        print(f"Animation created in {anim_time:.3f} seconds")
    
    total_time = time.time() - start_time
    if not fast_mode:
        print(f"Total simulation completed in {total_time:.3f} seconds")

def plot_flight_data():
    plot_start = time.time()
    
    times = np.array(time_points)
    speeds = np.array([i.speed for i in r])
    altitudes = np.array([i.altitude for i in r])
    dynamic_pressures = np.array([i.dynamic_pressure for i in r])
    nose_cone_temps = np.array([i.nose_cone_temp for i in r])
    
    fig, ax = plt.subplots(2, 2, figsize=(10, 6))

    ax[0, 0].plot(times, speeds, 'b-', linewidth=1.5)
    ax[0, 0].set_title("Speed vs Time")
    ax[0, 0].set_xlabel("Time (s)")
    ax[0, 0].set_ylabel("Speed (m/s)")
    ax[0, 0].grid(True, linestyle='--', alpha=0.7)

    ax[0, 1].plot(times, altitudes, 'g-', linewidth=1.5)
    ax[0, 1].set_title("Altitude vs Time")
    ax[0, 1].set_xlabel("Time (s)")
    ax[0, 1].set_ylabel("Altitude (m)")
    ax[0, 1].grid(True, linestyle='--', alpha=0.7)

    ax[1, 0].plot(times, dynamic_pressures, 'r-', linewidth=1.5)
    ax[1, 0].set_title("Dynamic Pressure vs Time")
    ax[1, 0].set_xlabel("Time (s)")
    ax[1, 0].set_ylabel("Pressure (Pa)")
    ax[1, 0].grid(True, linestyle='--', alpha=0.7)

    ax[1, 1].plot(times, nose_cone_temps, 'm-', linewidth=1.5)
    ax[1, 1].set_title("Nose Cone Temperature vs Time")
    ax[1, 1].set_xlabel("Time (s)")
    ax[1, 1].set_ylabel("Temperature (K)")
    ax[1, 1].grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout() 
    print(f"Flight data plotting completed in {time.time() - plot_start:.3f} seconds")
    
    return fig
    
def plot_fin_temperature():
    plot_start = time.time()
    
    figures = []
    
    if fin_tracker:
        fig = fin_tracker.plot_temperature_history()
        figures.append(fig)
        
        critical_points = fin_tracker.get_critical_time_points()
        if "max_temperature" in critical_points:
            max_temp_time = critical_points["max_temperature"]["time"]
            max_temp_mach = critical_points["max_temperature"]["mach"]
            max_temp_idx = fin_tracker.time_points.index(max_temp_time)
            
            fig = fin_tracker.plot_temperature_snapshot(max_temp_idx, max_temp_time, max_temp_mach)
            fig.suptitle("Temperature Distribution at Maximum Temperature", fontsize=16)
            figures.append(fig)
    
        if "max_velocity" in critical_points:
            max_vel_time = critical_points["max_velocity"]["time"]
            max_vel_mach = critical_points["max_velocity"]["mach"]
            max_vel_idx = fin_tracker.time_points.index(max_vel_time)
            
            fig = fin_tracker.plot_temperature_snapshot(max_vel_idx, max_vel_time, max_vel_mach)
            fig.suptitle("Temperature Distribution at Maximum Velocity", fontsize=16)
            figures.append(fig)
        
        plot_time = time.time() - plot_start
        print(f"Temperature plotting completed in {plot_time:.3f} seconds")
        return figures
    return []

def plot_stability_during_flight():
    plot_start = time.time()
    global r, time_points
    
    if not r or len(r) < 2:
        print("No flight data available for stability analysis")
        return None
    
    stability = RocketStability()
    stability.set_fin_properties(fin_tracker.fin)
    speeds = np.array([abs(point.speed) for point in r])
    altitudes = np.array([point.altitude for point in r])
    dynamic_pressures = np.array([point.dynamic_pressure for point in r])
    analysis_points = [
        {"name": "Launch", "idx": 0},
        {"name": "Max-Q", "idx": np.argmax(dynamic_pressures)},
        {"name": "Burnout", "idx": min(len(r)-1, int(r[0].fuel_mass / rc.fuel_flow_rate / config["simulation"]["dt"]))},
        {"name": "Max Velocity", "idx": np.argmax(speeds)},
        {"name": "Apogee", "idx": np.argmax(altitudes)},
        {"name": "Landing", "idx": len(r)-1}
    ]
    
    # Create multi-panel figure
    fig, axes = plt.subplots(len(analysis_points), 1, figsize=(12, 4*len(analysis_points)))
    if len(analysis_points) == 1:
        axes = [axes]  # Make sure axes is always a list
    
    for i, point in enumerate(analysis_points):
        idx = point["idx"]
        flight_time = time_points[idx]
        
        # Get flight conditions
        altitude = r[idx].altitude
        velocity = r[idx].speed
        fuel_mass = r[idx].fuel_mass
        
        # Calculate Mach number (cached atmospheric data)
        atm_props = get_cached_atmosphere(altitude)
        speed_of_sound = atm_props[4]
        mach = abs(velocity) / speed_of_sound
        
        # Set stability conditions
        stability.set_flight_conditions(mach)
        stability.set_propellant_mass(fuel_mass)
        
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
        
        # Add flight information
        info_text = (f"Time: {flight_time:.1f}s\n"
                    f"Altitude: {altitude:.0f}m\n"
                    f"Velocity: {velocity:.0f}m/s\n"
                    f"Mach: {mach:.2f}\n"
                    f"Propellant: {fuel_mass:.1f}kg")
        
        axes[i].text(0.02, 0.95, info_text,
                    transform=axes[i].transAxes, verticalalignment='top',
                    bbox=dict(facecolor='white', alpha=0.7, boxstyle='round'))
        
        # Add stability information
        stability_info = (f"Stability: {stability.stability_calibers:.2f} calibers\n"
                         f"Status: {stability.get_stability_status()}")
                         
        if stability.stability_calibers < 0:
            info_color = 'red'
        elif stability.stability_calibers < config["stability"]["min_caliber_stability"]:
            info_color = 'orange'
        elif stability.stability_calibers > config["stability"]["max_caliber_stability"]:
            info_color = 'orange'
        else:
            info_color = 'green'
            
        axes[i].text(0.98, 0.95, stability_info,
                    transform=axes[i].transAxes, horizontalalignment='right',
                    verticalalignment='top', color=info_color,
                    bbox=dict(facecolor='white', alpha=0.7, boxstyle='round'))
        
        # Set title and format
        axes[i].set_title(f"Flight stage: {point['name']} (t={flight_time:.1f}s)")
        axes[i].set_xlim(-0.1, stability.length * 1.1)
        axes[i].set_ylim(-stability.diameter, stability.diameter)
        axes[i].set_aspect('equal')
        
        if i == len(analysis_points) - 1:
            axes[i].set_xlabel('Distance from Nose Tip (m)')
        
        axes[i].legend(loc='lower right')
    plt.tight_layout()   
    plot_time = time.time() - plot_start
    print(f"Stability analysis plotting completed in {plot_time:.3f} seconds")
    return fig

def report(limit_reached):
    report_start = time.time()
    
    if len(r) < 2:  # Make sure we have data
        print("No simulation data available for report.")
        return
    
    component_masses = {}
    if component_manager:
        component_data = component_manager.get_component_data()
        for name, data in component_data.items():
            if "mass" in data:
                component_masses[name] = data["mass"]
    
    altitudes = np.array([i.altitude for i in r])
    speeds = np.array([i.speed for i in r])
    dynamic_pressures = np.array([i.dynamic_pressure for i in r])
    nose_cone_temps = np.array([i.nose_cone_temp for i in r])
    
    max_dynamic_pressure = np.max(dynamic_pressures)
    print(f"\nMaximum dynamic pressure encountered during flight: {max_dynamic_pressure:.1f} Pa")
    print(f"Dynamic pressure used for fin sizing (fixed): {config["rocket"]["max_q"]:.1f} Pa")
        
    print('\nWith the following constants:')
    for key, value in vars(rc).items():
        if key == "dry_weight" and component_masses:
            print(f"   {key}: {value} kg (from component data)")
            print("   Component breakdown:")
            for comp_name, comp_mass in component_masses.items():
                if "propellant" not in comp_name.lower():
                    print(f"      - {comp_name}: {comp_mass} kg")
        else:
            print(f"   {key}: {value}")
    
    for key, value in vars(ec).items():
        print(f"   {key}: {value}")

    print('\nIntial conditions:')
    for key, value in vars(r[0]).items():
        if key == "fuel_mass":
            propellant_found = False
            for comp_name in component_masses:
                if "propellant" in comp_name.lower():
                    print(f"   {key}: {value} kg (from team propulsion data)")
                    propellant_found = True
                    break
            if not propellant_found:
                print(f"   {key}: {value} kg")
        else:
            print(f"   {key}: {value}")

    max_speed_index = np.argmax(speeds)
    max_speed = speeds[max_speed_index]
    max_speed_altitude = altitudes[max_speed_index]
    
    print('\nAltitude reached:')
    print('   ',"{:.3f}".format(np.max(altitudes)), 'meter')

    if limit_reached is True:
        print('     -> Altitude limit was reached which may cause inaccurate results')

    print('\nMax nose cone temperature:')
    max_nose_temp = np.max(nose_cone_temps)
    print('   ',"{:.2f}".format(max_nose_temp), 'K = ' ,"{:.2f}".format(max_nose_temp-273.15) , '\u00B0C')

    print('\nMax_q:')
    print('   ',"{:.3f}".format(max_dynamic_pressure), 'Pa')
    
    print('\nMaximum velocity reached at:')
    print('   ',"{:.3f}".format(max_speed_altitude), 'meters altitude')
    print('    with a speed of', "{:.3f}".format(max_speed), 'm/s')
    
    if fin_tracker:
        if hasattr(fin_tracker, 'absolute_max_temperature') and fin_tracker.absolute_max_temperature is not None:
            max_fin_temp = fin_tracker.absolute_max_temperature
            max_temp_info = fin_tracker.absolute_max_temperature_info
        else:
            max_fin_temp = fin_tracker.get_max_temperature()
            if hasattr(fin_tracker, 'max_temp_history'):
                max_idx = fin_tracker.max_temp_history.index(max(fin_tracker.max_temp_history))
                max_temp_info = {
                    "time": fin_tracker.time_points[max_idx],
                    "altitude": fin_tracker.altitude_history[max_idx],
                    "velocity": fin_tracker.velocity_history[max_idx],
                    "mach": fin_tracker.mach_history[max_idx]
                }
            else:
                max_temp_info = None
                
        if max_fin_temp:
            fin_material = fin_tracker.fin.material_name
            max_service_temp = fin_tracker.fin.max_service_temp
            temp_margin = max_service_temp - max_fin_temp
            
            print('\nFin Temperature Analysis:')
            print(f'   Material: {fin_material}')
            print(f'   Maximum Fin Temperature: {max_fin_temp:.2f} K = {max_fin_temp-273.15:.2f} °C')
            print(f'   Material Max Service Temperature: {max_service_temp:.2f} K = {max_service_temp-273.15:.2f} °C')
            print(f'   Temperature Margin: {temp_margin:.2f} K')
            
            if temp_margin < 0:
                print(f'   WARNING: Fin temperature exceeds material service limit by {abs(temp_margin):.2f} K!')
                print(f'   Temperature exceeds limit by {(abs(temp_margin)/max_service_temp*100):.1f}% of service temperature')
            else:
                print(f'   Safety Status: Temperature within material limits ({temp_margin/max_service_temp*100:.1f}% margin)')
                
            if max_temp_info:
                print('\n   Maximum fin temperature occurred at:')
                print(f'   - Time: {max_temp_info["time"]:.2f} s')
                print(f'   - Altitude: {max_temp_info["altitude"]:.2f} m')
                print(f'   - Velocity: {max_temp_info["velocity"]:.2f} m/s')
                print(f'   - Mach: {max_temp_info["mach"]:.2f}')
    
    print('\nStability Analysis:')
    
    stability = RocketStability()
    stability.set_fin_properties(fin_tracker.fin)
    burnout_idx = min(len(r)-1, int(r[0].fuel_mass / rc.fuel_flow_rate / config["simulation"]["dt"]))
    apogee_idx = np.argmax(altitudes)
    
    analysis_points = [
        {"name": "Launch", "idx": 0},
        {"name": "Burnout", "idx": burnout_idx},
        {"name": "Apogee", "idx": apogee_idx}
    ]
    
    print(f"{'Flight Stage':<15} {'Time (s)':<10} {'Stability (cal)':<15} {'Status':<20}")
    print('-' * 60)
    
    for point in analysis_points:
        idx = point["idx"]
        flight_time = time_points[idx]
        altitude = r[idx].altitude
        velocity = r[idx].speed
        fuel_mass = r[idx].fuel_mass

        atm_props = get_cached_atmosphere(altitude)
        speed_of_sound = atm_props[4]
        mach = abs(velocity) / speed_of_sound
        

        stability.set_flight_conditions(mach)
        stability.set_propellant_mass(fuel_mass)
        stability.calculate_center_of_mass()
        stability.calculate_center_of_pressure()
        stability.calculate_stability()
        
        print(f"{point['name']:<15} {flight_time:<10.1f} {stability.stability_calibers:<15.2f} {stability.get_stability_status():<20}\n")
    
    
    report_time = time.time() - report_start
    print(f"Report generation completed in {report_time:.3f} seconds")

def clear_simulation_caches():
    global _atmosphere_cache
    _atmosphere_cache.clear()
    
    if fin_tracker and hasattr(fin_tracker, 'thermal_analyzer'):
        if hasattr(fin_tracker.thermal_analyzer, 'clear_caches'):
            fin_tracker.thermal_analyzer.clear_caches()
    
    if fin_tracker and hasattr(fin_tracker.fin, 'clear_caches'):
        fin_tracker.fin.clear_caches()

class FlightSimulator:
    pass


if __name__ == "__main__":
    standalone_start = time.time()
    main()
    standalone_time = time.time() - standalone_start
    print(f"Standalone execution completed in {standalone_time:.3f} seconds")