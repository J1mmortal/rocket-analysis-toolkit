# Rocket Analysis Toolkit
## Overview

This toolkit provides comprehensive analysis capabilities for rocket design, including:

1. **Flight Simulation** - Simulate rocket trajectory and flight dynamics
2. **Thermal Analysis** - Calculate fin temperatures during flight
3. **Stability Analysis** - Evaluate and visualize rocket stability
4. **Material Comparison** - Compare different fin materials for weight and thermal performance
5. **Trajectory Optimization** - Analyze trajectory and provide optimization suggestions for reaching target altitude
6. **Manage Team Data** - Load, check and modify the mass and location data of the components
7. **Plot Display Control** - Toggle between PDF-only output and interactive plot display

## Quick Start Commands

### Basic Flight Simulation
```
python run_analysis.py
```
This runs a flight simulation with default settings and displays trajectory plots, thermal profiles, and stability visualization.

### Interactive Menu
```
python run_analysis.py -i
```
Opens an interactive menu with all analysis options. Recommended for first-time users.

### Material Comparison
```
python run_analysis.py -c
```
Compares all available fin materials for thermal performance and weight optimization.

### Stability Analysis
```
python run_analysis.py -s
```
Generates stability diagrams at key flight stages (launch, max-Q, burnout, apogee, landing).

### Team Data Management
```
python run_analysis.py -t
```
Manage component data from different design teams.

## Command Options

| Option | Description | Output |
|--------|-------------|--------|
| `-m MATERIAL` | Specify fin material | Flight plots with specified material |
| `-c` | Run material comparison | Material comparison graphs and tables |
| `-f` | Run in fast mode | Same outputs but faster calculation |
| `-i` | Interactive menu mode | Menu-driven interface |
| `-s` | Run stability analysis | Series of stability diagrams |
| `--stage=STAGE` | Flight stage for stability analysis | Stability diagram for specific stage |
| `-t` | Manage team component data | Team data templates and summaries |
| `--show-plots` | Force display plots on screen | Override config to show plots |
| `--hide-plots` | Force hide plots on screen | Override config to hide plots |

### Flight Stage Options for `--stage`
- `launch` - Initial launch conditions
- `burnout` - End of propellant burn
- `apogee` - Maximum altitude
- `landing` - Final descent

### Example Combinations
```
python run_analysis.py -m "Titanium Ti-6Al-4V" -f  # Fast simulation with titanium
python run_analysis.py -s --stage=burnout          # Stability at burnout only
python run_analysis.py -c -f                       # Fast material comparison
python run_analysis.py --show-plots                # Enable plot display on screen
python run_analysis.py --hide-plots -c             # Hide plots, only save PDF
```

## Plot Display Control

The toolkit now features intelligent plot display control:

### **Default Behavior** (Recommended)
- **Plots**: Hidden by default (no screen pop-ups)  
- **PDFs**: Always generated with comprehensive analysis
- **MP4**: Available when enabled in config

### **Configuration Control**
Set in `config.py`:
```python
show_plots = False  # Default: no screen pop-ups
show_plots = True   # Enable screen display
```

### **Command Line Override**
```bash
python run_analysis.py --show-plots    # Force show plots on screen
python run_analysis.py --hide-plots    # Force hide plots on screen
```

### **Interactive Menu Toggle**
- Option 9 in the interactive menu toggles plot display
- Setting persists for the entire session
- PDFs are always generated regardless of plot display setting

### **When to Use Plot Display**
- **OFF (Default)**: Clean automated analysis, batch processing
- **ON**: Development, debugging, detailed inspection of individual plots

## Output Files and Naming Convention

All analysis outputs are saved to the `output` directory with standardized PDF reports and optional MP4 animations:

### PDF Report Naming Convention

| Analysis Type | Filename Format | Description |
|---------------|----------------|-------------|
| **Flight Simulation** | `FS_[material].pdf` | Complete flight analysis with specified material |
| **Material Comparison (Fast)** | `MC_fast.pdf` | Quick material comparison with optimized settings |
| **Material Comparison (Detailed)** | `MC_detailed.pdf` | Comprehensive material comparison |
| **Stability Analysis (All Stages)** | `SA_all_stages.pdf` | Stability throughout entire flight |
| **Stability Analysis (Single Stage)** | `SA_[stage].pdf` | Stability at specific flight stage |
| **Trajectory Optimization** | `TO_analysis.pdf` | Trajectory optimization analysis and suggestions |

### Material Abbreviations in Filenames
- `Aluminum_6061_T6` - Aluminum 6061-T6
- `Alumina` - Alumina ceramic
- `Titanium_Ti_6Al_4V` - Titanium Ti-6Al-4V
- `Stainless_Steel_304` - Stainless Steel 304
- `Inconel_718` - Inconel 718
- `Beryllium` - Beryllium
- `Carbon_carbon_matrix_composite` - Carbon-carbon composite

### Flight Stage Abbreviations
- `launch` - Launch conditions
- `burnout` - Engine burnout
- `apogee` - Maximum altitude
- `landing` - Landing phase

### PDF Content by Analysis Type

#### Flight Simulation PDFs (`FS_*.pdf`)
1. **Page 1**: Speed vs Time, Altitude vs Time
2. **Page 2**: Fin Temperature History (with material details)
3. **Page 3**: Flight conditions at maximum temperature point
4. **Page 4**: Temperature distribution at maximum temperature
5. **Page 5**: Temperature distribution at maximum velocity

#### Material Comparison PDFs (`MC_*.pdf`)
1. **Page 1**: Temperature comparison by material, Mass comparison with safety ratings
2. **Page 2**: Material properties relationship with temperature safety ratings
3. **Page 3**: Fin dimensions overlay showing size differences per material

#### Stability Analysis PDFs (`SA_*.pdf`)
- **All stages**: Multi-panel stability diagram throughout flight
- **Single stage**: Detailed stability diagram for specified flight phase

#### Trajectory Optimization PDFs (`TO_*.pdf`)
1. **Single page**: Comprehensive analysis including:
   - Altitude and velocity profiles
   - Mass distribution breakdown
   - Energy analysis
   - Altitude deficit visualization
   - Top optimization suggestions summary

### Animation Files (Optional)
- `fin_temp_[material].mp4` - Temperature animation during flight (if enabled in config)

## Configuration Guide

The toolkit can be configured without modifying code by adjusting parameters in `config.py`.

### Key Configuration Parameters

#### Rocket Geometry
```python
rocket_length = 2.5        # Total rocket length (m)
rocket_diameter = 0.5      # Rocket diameter (m)
nose_cone_length = 0.3     # Nose cone length (m)
nose_cone_shape = "ogive"  # "conical", "ogive", or "elliptical"
```

#### Component Masses and Positions
```python
# Format: mass (kg) and position from nose tip (m)
nose_cone_mass = 0.85
nose_cone_cg_position = 0.15

# Add other components similarly
```

#### Fin Parameters
```python
fin_height = 0.2           # Fin height (m)
fin_width = 0.25           # Fin width (m)
fin_sweep = 0.15           # Fin sweep distance (m)
num_fins = 4               # Number of fins
fin_material = "Titanium Ti-6Al-4V"  # Default material
```

#### Animation Settings
```python
create_temperature_animation = False  # Set to True to enable MP4 animations
animation_frames = 120               # Number of frames for animation
```

#### Plot Display Control
```python
show_plots = False                   # Control screen plot display (PDFs always generated)
pdf_output_enabled = True            # Enable PDF report generation  
pdf_dpi = 300                       # Resolution for PDF figures
```

#### Stability Criteria
```python
min_caliber_stability = 1.0  # Minimum calibers for stability
max_caliber_stability = 6.0  # Maximum calibers (too high = overstable)
```

#### Simulation Parameters
```python
dt = 0.01                  # Time step (s)
afterTopReached = 5000     # Additional cycles after apogee
```

## Setting Up Team Data Integration

To integrate data from multiple design teams:

1. **Create templates**:
   ```
   python run_analysis.py -t
   ```
   Then select option 1. This creates template files in the `Team_data` directory.

2. **Distribute templates** to respective teams:
   - `aero_group.json` - For aerodynamics team
   - `fuselage_group.json` - For fuselage/structures team  
   - `nozzle_group.json` - For nozzle/engine team

3. **Load updated team data**:
   ```
   python run_analysis.py -t
   ```
   Then select option 2 to load team data files.

## Understanding the Output Reports

### Flight Simulation Reports
- **Comprehensive thermal analysis** showing fin temperature evolution
- **Critical flight events** marked and analyzed
- **Material safety margins** clearly indicated
- **Temperature distributions** at key flight phases

### Material Comparison Reports  
- **Temperature performance** ranking across all materials
- **Mass optimization** with thermal safety color coding
- **Material properties** correlation analysis
- **Dimensional scaling** showing how fin size varies by material

### Stability Analysis Reports
- **Center of mass/pressure** evolution throughout flight
- **Stability margins** in calibers with safety assessment
- **Component contribution** visualization
- **Flight phase analysis** with detailed breakdowns

### Trajectory Optimization Reports
- **Performance gap analysis** against 100km target
- **Optimization suggestions** prioritized by impact
- **Mass and energy breakdowns** for design insights
- **Implementation guidance** for suggested improvements

## Dependencies

- NumPy
- Matplotlib
- ISA Atmosphere calculator (`isacalc`)
- Pandas (for material comparison)

## File Organization

```
project/
├── output/                    # All PDF reports and animations
│   ├── FS_*.pdf              # Flight simulation reports
│   ├── MC_*.pdf              # Material comparison reports  
│   ├── SA_*.pdf              # Stability analysis reports
│   ├── TO_*.pdf              # Trajectory optimization reports
│   └── *.mp4                 # Temperature animations (optional)
├── Team_data/                # Team component data files
│   ├── aero_group.json
│   ├── fuselage_group.json
│   └── nozzle_group.json
├── run_analysis.py           # Main analysis interface
├── main.py                   # Core simulation engine
├── config.py                 # Configuration parameters
└── [other analysis modules]
```

## AI Usage Clarification

AI has been used to make otherwise cumbersome tasks a lot more doable making it easier/faster to build a big system of codes. The AI Bot that was used is Claude 3.7 Sonnet and has been proven very helpful when it comes to larger codes like these. Below I will clarify what code was written by AI:
- **fin_animation.py** - everything
- **rocket_stability.py** - everything  
- **rocket_fin_tracker.py** - everything
- **fin_temp_distribution.py** - all the plotting stuff
- **material_comparison.py** - all the plotting stuff
- **thermal_calc.py** - gave it the theory and it spat out the code (had to guide very meticulously tho since it wasn't very accurate in the beginning)

and for some other codes i used it to rebuild them to a class system and for some synchronisation issues