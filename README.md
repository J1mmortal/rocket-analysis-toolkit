# Rocket Analysis Toolkit – README

This project provides an end‑to‑end analysis pipeline for a high‑power (single stage) rocket, driven entirely from an interactive command‑line menu. The code combines team‑provided component data, fin geometry and material selection, flight simulation, thermal analysis, stability analysis, and trajectory optimization into a single workflow controlled via one input command.

---

## 1. Getting Started

Clone the repository and ensure Python and required scientific libraries (NumPy, Matplotlib, Pandas) are installed. The main entry point is `main.py`, which also manages configuration and interactive usage through `config.json`.

Basic usage (recommended):

'''bash
rocket_toolkit
'''

This starts the interactive menu and is the only interface a user needs for running simulations and managing settings; all other command‑line flags exist for advanced or scripted usage.

---

## 2. Configuration and Folder Layout

The central configuration file is:

- `config.json` – stores paths, rocket parameters, engine data, simulation settings, materials, presets, and visualization/stability options.

Key paths (under `"paths"` in `config.json`):

- `"teamdata"` – folder where team JSON files (aero/fuselage/nozzle groups) are stored; default `./Teamdata` is created automatically if missing.  
- `"output"` – folder where generated PDFs, animations, and reports are written; default `.output` is created on demand.

Team‑data files (in `Teamdata/`):

- `aero_group.json` – aerodynamic team components (e.g. nose cone).  
- `fuselage_group.json` – fuselage/propellant components.  
- `nozzle_group.json` – nozzle and engine components.

These JSON files are created as templates by the interactive menu and then edited by each team to enter their component masses, longitudinal positions, and descriptions.

---

## 3. Interactive Menu (`-i`)

Starting the toolkit with `python main.py -i` launches `mainmenu()`, a loop that exposes all major capabilities without needing any additional flags.

Menu options (simplified):

1. Run flight simulation with default fin material  
2. Run flight simulation with user‑selected fin material  
3. Material comparison (fast)  
4. Material comparison (detailed)  
5. Stability analysis – all stages  
6. Stability analysis – specific stage (launch/burnout/apogee/landing)  
7. Trajectory optimization to 100 km  
8. Manage team component data  
9. Configure settings, materials, and apply rocket presets  
0. Exit

Each menu choice prints timing information and writes any generated reports to the configured output folder. The expectation is that users:

- Enter via `rocket_toolkit`  
- Use “Manage team component data” to set up and load team inputs  
- Use “Configure settings” and “Apply rocket preset” to define a baseline rocket  
- Then run simulations, comparisons, stability, and trajectory tools from the same menu.

---

## 4. Configuration, Materials, Presets, and Team Data

### 4.1 Config Settings

The interactive “Configure settings” submenu (`settings_and_materials_menu`) lets the user:

- Edit selected keys from `config.json` (paths, initial conditions, engine parameters, rocket geometry, and selected simulation/stability thresholds).  
- Add new fin materials to the materials database stored inside `config.json`.  
- Apply rocket presets that overwrite rocket‑related configuration values and component definitions.

Only specific keys are editable from the menu; others are read‑only and shown for information.

### 4.2 Materials and Fin Model

Fin materials are defined in a materials database read by `RocketFin` via `MaterialsDatabase`, which is configured using `config.json`. Important fin material properties include:

- Thermal conductivity  
- Density  
- Specific heat  
- Maximum service temperature  
- Yield strength  
- Thermal expansion coefficient  
- Emissivity

The “Add new material” option prompts for these properties and stores them under `config["materials"]`, making them available to all fin and thermal analyses. The default material for simulations is set in `config["finanalysis"]["finmaterial"]`, and can be updated by the material comparison workflow when the user confirms.

`RocketFin` computes fin dimensions (height, width, area, and mass) based on:

- Delta‑V requirement, mass breakdown, and structural margins  
- Dynamic pressure `maxq` from `config["rocket"]["maxq"]`  
- Fuselage radius, number of fins, wall thickness, angle of attack, and fin sweep/angle  
- Team‑provided mass data when available

The result is a set of fin dimensions and mass consistent with the mission profile and structural constraints, cached per material to speed subsequent runs.

### 4.3 Presets vs Team Data

The toolkit combines two concepts:

- **Rocket presets** – predefined rocket configurations stored in `config.json` under `"presets"`, containing rocket geometry, engine and simulation settings, and optional component mass layout.  
- **Team data** – actual component masses and positions provided by teams in the `Teamdata` JSON files, loaded via `ComponentData`.

Interaction between them:

- Applying a rocket preset overwrites rocket‑related configuration (geometry, engine parameters, mass properties, components) in `config.json`.  
- Loading team data (`ComponentData.updatefromteamfiles`) reads `aero_group.json`, `fuselage_group.json`, and `nozzle_group.json`, inserts those components into `ComponentData.components`, and then `updateconfig()` merges them back into `config["components"]`, updating dry mass, propellant mass, and wet mass.  
- When both exist, team data takes precedence for mass and position of components it defines; preset values are the baseline used when no team data is available.

**Expectation for users:**

- Rocket presets define a consistent baseline for geometry and performance.  
- Team data refines this with real component masses and positions from design teams.  
- Most downstream analyses (flight, fin sizing, stability, trajectory) will use team data when present, falling back to preset‑based config when team files are missing or incomplete.

---

## 5. Team Data Management

Menu option 8 (“Manage team component data”) opens a dedicated management loop.

This submenu lets users:

1. Create template files for teams  
2. Load team data from files  
3. Show team‑data component summary  
4. Show merged config component summary  
5. Return to main menu

Implementation details:

- `ComponentData.createalltemplates()` creates default JSON files for aero, fuselage, and nozzle teams with example components, masses, positions, and descriptions.  
- Teams edit these JSON files to reflect the final rocket design.  
- `ComponentData.updatefromteamfiles()` loads them, filters out zero‑mass and fin entries (fins are handled by `RocketFin`), and stores components in memory.  
- `ComponentData.updateconfig(config)` then writes these components and derived mass properties back into `config.json`, computing dry mass, propellant mass, and wet mass totals.  
- Component summary functions print mass breakdowns by component and total masses, clearly separating propellant from structural masses.

**Expectation for users:**

- Use “Create template files for teams” early in the project and distribute them.  
- Require teams to keep positions in meters along the rocket and masses in kilograms.  
- After editing, run “Load team data from files” before any final simulation or stability analysis, so results reflect real component data.

---

## 6. Flight Simulation and Fin Thermal Model

### 6.1 Flight Simulation

The flight simulation engine uses:

- Initial conditions from `config["simulation"]` (initial velocity/altitude/dynamic pressure)  
- Engine performance (`isp_sea`, `isp_vac`, fuel flow rate) from `config["engine"]`  
- Rocket geometry and drag coefficient from `config["rocket"]`  
- Mass properties from `config` (updated by presets and team data)

When running a single‑material analysis, the sequence is:

1. Initialize or update `RocketFin` with the chosen material, compute fin dimensions, and compute fin MMOI.  
2. Create a `FinTemperatureTracker` linked to the rocket fin and hand it to the flight simulator.  
3. Initialize and run the simulation, which updates time series of velocity, altitude, Mach, dynamic pressure, nose‑cone temperature, and fin thermal state.  
4. Store complete histories for later plotting and PDF export.

### 6.2 Fin Thermal Analysis and Temperature Tracking

`FinTemperatureTracker` tracks:

- Fin surface temperature distributions over time  
- Time, altitude, velocity, Mach histories  
- Maximum temperature history and critical timepoints (e.g. time of absolute maximum temperature and maximum velocity).

`ThermalAnalysis` (used by `thermal_data.py`) computes fin temperature fields on a 2D mesh, enabling:

- 3D surface plots of temperature over fin planform  
- 2D contour plots highlighting regions above material service temperature  
- Annotations of maximum temperature location and thermal margins relative to `maxservicetemp`.

For single‑material runs, the toolkit can optionally generate an MP4 animation showing fin temperature evolution; if the maximum fin temperature exceeds material limits, a warning is printed with the temperature margin at that critical point.

---

## 7. Material Comparison

Material comparison can be run in fast or detailed mode via the interactive menu (options 3 and 4).

### 7.1 Comparison Workflow

The comparison workflow:

1. Uses `RocketFin.calculateallmaterialdimensions()` to compute fin dimensions and masses for all available materials.  
2. For each material, performs a thermal analysis at specified velocities and altitudes (typically taken from the current fin conditions), computing maximum fin temperature.  
3. Computes the temperature margin = service limit − maximum fin temperature and marks materials as “within limits” or not.  
4. Aggregates results into a table containing material name, fin height/width, maximum temperature, service temperature, margin, and mass.  
5. Produces high‑level console output listing each material with its maximum temperature, margin, mass, and pass/fail status.  
6. Generates a comparison PDF (bar charts of maximum temperature vs service limit, mass vs safety rating, and fin dimensions by material) saved in the output folder.

### 7.2 Fast vs Detailed Modes

- **Fast mode**:  
  - Coarser thermal mesh (`comparisonmeshsize`)  
  - Optimized for speed; yields approximate margins suitable for quick design space exploration.  
  - Used when fast comparison is requested from the menu.

- **Detailed mode**:  
  - Finer mesh and full calculations; more computationally expensive but more accurate.  
  - Recommended before committing to a material choice.

After comparison:

- If at least one material stays within thermal limits, the code identifies the “best” candidate (max margin, then lower mass) and offers to set it as the default fin material in `config.json`.  
- If none satisfies limits, the toolkit chooses the “least problematic” material (highest margin among failing ones) and again offers to update the default.  
- The tool warns explicitly when this selection is based on fast mode, advising a detailed comparison before finalizing material choice.

**Expectation for users:**

- Use fast mode early and often to explore candidate materials.  
- Always run a detailed comparison on the recommended material (or short‑listed materials) before final design freeze.  
- Interpret “Within Limits” strictly: materials that fail should not be used for real hardware without design changes or additional mitigation.

---

## 8. Stability Analysis

The stability module computes center of mass (CoM), center of pressure (CoP), and stability margin for the configured rocket.

Key aspects:

- Uses component data and config to construct a component mass model including nose cone, fuselage, nozzle, engine, fins, propellant, and recovery system.  
- Fin properties (height, width, number, position, mass) are taken from the current `RocketFin` object.  
- CoP is computed using aerodynamic approximations for nose cone, cylindrical body, fins, and optional boattail, adjusted by flight angle of attack.  
- Stability margin and calibers are derived from CoP − CoM over rocket diameter, and classified as unstable, marginally stable, stable, or overstable using user‑configurable bounds from `config`.

Interactive options:

- “Stability analysis – all stages” runs a full flight simulation to obtain trajectory data and then produces a stability‑vs‑time plot over the entire flight, plus an initial conditions page in the PDF.  
- “Stability analysis – specific flight stage” approximates stability at launch, burnout, apogee, or landing using characteristic Mach numbers and propellant loads.

Visualization:

- 1D diagrams showing CoM and CoP along a line from nose tip.  
- 2D diagrams showing the rocket outline, fin planform, component CG markers, and stability margin arrow, with color‑coded stability status.  
- PDFs saved in the output folder for both “all stages” and single‑stage analyses.

**Expectation for users:**

- Use all‑stage stability early to check that the rocket remains within a desired stability window over the entire trajectory.  
- Investigate specific stages to understand worst‑case margins (e.g. at maximum velocity or near burnout).  
- Pay attention to calibers and classification; design decisions (fin size/location, mass distribution) should target a reasonable stability range and avoid both negative margins and excessive over‑stability.

---

## 9. Trajectory Optimization

The trajectory optimization tool uses simulation results to suggest modifications that help reach a target apogee (default 100 km).

Process:

1. Run a baseline flight simulation with the current configuration and default fin material in fast mode.  
2. Instantiate `TrajectoryOptimizer` with the target altitude and analyze the simulated trajectory and mass history.  
3. Generate textual suggestions grouped into categories such as mass reduction, aerodynamic improvements, propellant optimization, staging, and trajectory shaping.  
4. Create a PDF report containing plots of trajectory metrics and a summary of suggested design changes, plus an initial‑conditions page.

The menu then optionally allows the user to inspect specific categories (mass, aerodynamics, propellant) and read detailed recommendations, including estimated impact on apogee.

**Expectation for users:**

- Treat optimization suggestions as guidance rather than strict prescriptions; the tool assumes simplified models and may not capture all constraints.  
- Iterate: modify design (presets, team data, fin material/dimensions), rerun optimization, and compare apogee and stability changes.

---

## 10. Reports and Outputs

Most analyses generate PDFs in the configured output folder:

- **Flight simulation PDF**:  
  - Speed vs time, altitude vs time, dynamic pressure/temperature plots.  
  - Fin thermal histories and key snapshots at maximum temperature and maximum velocity.  
  - An “initial conditions and parameters” section summarizing configuration, material properties, component masses and positions, geometry, engine parameters, and environmental constants.

- **Material comparison PDF**:  
  - Bar charts for maximum temperature vs service limit for each material.  
  - Mass vs safety rating with color coding and hatching for failing materials.  
  - Fin height/width plots by material.  
  - Conditions summary page.

- **Stability analysis PDFs**:  
  - Stability diagrams, CoM/CoP/Calibers output, and configuration summary pages.

- **Trajectory optimization PDF**:  
  - Trajectory plots and a narrative report summarizing analysis and suggestions.

Animations:

- Optional MP4 fin temperature animations when detailed single‑material analysis is run with animation enabled in `config["finanalysis"]["createtemperatureanimation"]`.

---

## 11. Expected Model Behavior

Users should expect the following from this toolkit:

- **Config‑driven behavior** – All major physical parameters, paths, and visualizations are controlled through `config.json`, which is editable via the interactive menu for defined keys.  
- **Tight coupling of subsystems** –  
  - Fin geometry uses rocket mass and `maxq`.  
  - Flight simulation uses fin properties, engine data, and mass distribution.  
  - Thermal analysis uses flight conditions and fin material properties.  
  - Stability uses geometry, fin properties, and mass distribution.  
  - Trajectory optimization uses flight results and mass history.  
- **Deterministic reports** – Given fixed config, team data, and material choice, repeated runs produce consistent results; differences arise only from configuration or input changes.  
- **Approximation and engineering judgement** – Aerodynamic and thermal models are engineering approximations suitable for design‑level trade studies, not final certification; users should apply engineering judgement and more detailed tools for critical designs.

By using only:

'''bash
python main.py -I
'''

a user can:

- Configure rocket and simulation settings  
- Define and edit materials  
- Apply presets  
- Manage team input files  
- Run flight, thermal, stability, material comparison, and trajectory optimization analyses  
- Generate all supporting reports and visualizations from a single interactive interface.
