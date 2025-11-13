
########################
### Unchangable settings
########################

### Earth Constants
gravitational_constant = 6.6743 * 10**-11 # m/s^2
mass_earth = 5.97219 * 10**24 # kg
earth_radius = 6378000 # m

### PDF Output Configuration
pdf_output_enabled = True
pdf_dpi = 300

# Fin analysis output options
create_temperature_animation = False
animation_frames = 120 

# Stability parameters
min_caliber_stability = 1.5  
max_caliber_stability = 4.0 

# Visualization options for stability
show_stability_margin = True
show_component_cgs = True
show_rocket_configuration = "2D"  # Options: "1D", "2D"


#########################
### Settings to play with
#########################

### Engine
isp_sea = 235
isp_vac = 300

### Initial conditions of variables
v0 = 0 # m/s
h0 = 0 # m/s
intial_fuel_mass = 800 # kg
q0 = 0

### Rocket Constants
dry_weight = 800 # kg
fuel_flow_rate = 4.4 # kg/s (while t < t_burn_time)
rocket_radius = 0.175 # m
drag_coefficient = 0.5
max_q = 82800 # Pa (updated in calculations)

### Simulation variables
dt = 0.01
afterTopReached = 10000 #additional cycles

### Fin Analysis Configuration
fin_material = "Titanium Ti-6Al-4V" #default material

### Rocket geometry for stability analysis
rocket_length = 2.5  # m
rocket_diameter = 0.5  # m
nose_cone_length = 0.3  # m
nose_cone_shape = "ogive"  # Options: "conical", "ogive", "elliptical"

nose_cone_mass = 0.7  # kg
nose_cone_cg_position = 0.15  # m from nose tip

fuselage_mass = 1.2  # kg
fuselage_cg_position = 1.2  # m from nose tip

nozzle_mass = 0.6  # kg
nozzle_cg_position = 2.4  # m from nose tip

engine_mass = 0.8  # kg (empty mass)
engine_cg_position = 2.3  # m from nose tip

fin_set_cg_position = 2.1  # m from nose tip

propellant_mass = 800  # kg (initial fuel mass)
propellant_cg_position = 1.9  # m from nose tip

recovery_system_mass = 0.4  # kg
recovery_system_position = 0.9  # m from nose tip