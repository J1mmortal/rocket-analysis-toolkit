# -*- coding: utf-8 -*-
"""
Created on Wed May  7 15:17:50 2025

@author: jespe
"""

### Engine
isp_sea = 235
isp_vac = 300

### Initial conditions of variables
v0 = 0 #m/s
h0 = 0 #m/s
intial_fuel_mass = 800 #kg
q0 = 0

### Rocket Constants
dry_weight = 800 #kg
fuel_flow_rate = 4.4 #kg/s (while t < t_burn_time)
rocket_radius = 0.175 #m
drag_coefficient = 0.5
max_q = 82800 #Pa - dynamic pressure for fin calculations (will be updated during simulation)

### Earth Constants
gravitational_constant = 6.6743 * 10**-11 #m/s^2
mass_earth = 5.97219 * 10**24 #kg
earth_radius = 6378000 #m

### Simulation variables
dt = 0.01 #dt step size
afterTopReached = 10000 #additional cycles after highest point was reached

### Fin Analysis Configuration
# Default fin material - can be overridden in main.py
fin_material = "Titanium Ti-6Al-4V"

# Fin analysis output options
create_temperature_animation = False  # Set to True to create MP4 animation (computationally expensive)
animation_frames = 120  # Number of frames for animation

### PDF Output Configuration
# All analysis results are now saved as comprehensive PDF reports in the output/ directory
# No individual PNG or TXT files are created - everything is consolidated into PDFs
pdf_output_enabled = True  # Enable PDF report generation
pdf_dpi = 300  # Resolution for PDF figures

### Rocket geometry for stability analysis
rocket_length = 2.5  # m
rocket_diameter = 0.25 * 2  # m (derived from existing radius parameter)
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

# Stability parameters
min_caliber_stability = 1.5  # Minimum calibers of stability required
max_caliber_stability = 4.0  # Maximum calibers of stability (too stable can also cause issues)

# Visualization options for stability
show_stability_margin = True  # Show the stability margin
show_component_cgs = True  # Show individual component CGs
show_rocket_configuration = "2D"  # Options: "1D", "2D", "3D"