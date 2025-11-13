# Rocket Analysis Toolkit
## Overview

This toolkit provides comprehensive analysis capabilities for rocket design, including:

1. **Flight Simulation** - Simulate rocket trajectory and flight dynamics
2. **Thermal Analysis** - Calculate fin temperatures during flight
3. **Stability Analysis** - Evaluate and visualize rocket stability
4. **Material Comparison** - Compare different fin materials for weight and thermal performance
5. **Trajectory Optimization** - Analyze trajectory and provide optimization suggestions for reaching target altitude
6. **Manage Team Data** - Load, check and modify the mass and location data of the components
7. **Customisable Settings** - Change the settings in a way that fits your rocket by either changing the team data or use presets for exisiting rockets
## Quick Start Commands

### Basic Flight Simulation
```
python src\rocket_toolkit\cli\main.py
```
This runs a flight simulation with default settings and displays trajectory plots, thermal profiles, and stability visualization.

### Interactive Menu
```
python src\rocket_toolkit\cli\main.py -i
```
Opens an interactive menu with all analysis options. Recommended for first-time users.

### Material Comparison
```
python src\rocket_toolkit\cli\main.py -c
```
Compares all available fin materials for thermal performance and weight optimization.

### Stability Analysis
```
python src\rocket_toolkit\cli\main.py -s
```
Generates stability diagrams at key flight stages (launch, max-Q, burnout, apogee, landing).

### Team Data Management
```
python src\rocket_toolkit\cli\main.py -t
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
```

### **Default Behavior** (Recommended)
- **PDFs**: Always generated with comprehensive analysis
- **MP4**: Available when enabled in config

### **Configuration Control**
Set in `config.json`, when adjusted from interactive menu, functionality can be garantueed, but simply editing the config.json is also possible:

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
- More materials can be added through the interactive material

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

The toolkit can be configured without modifying code by adjusting parameters in `config.json`.

### Key Configuration Parameters
**explanation still to be added**

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
still to be done
```

## AI Usage Clarification

AI has been used to speed up some parts of the coding, mostly with helping to quickly understand errors or finding all locations where a certain mistake was made. I have also used it to come up with different coding structures that can make sure the code can be expanded without having to restructure the code a lot. This was important since i am not a data science student but an engineering student and this is not my field of expertise.