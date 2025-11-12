import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from src.rocket_toolkit import config
from src.rocket_toolkit.geometry.component_manager import ComponentData
from src.rocket_toolkit.geometry.rocket_fin import RocketFin
import isacalc as isa

class TrajectoryOptimizer:
    def __init__(self, target_altitude=100000):
        self.target_altitude = target_altitude  # meters
        self.std_atm = isa.Atmosphere()
        self.component_manager = ComponentData()
        self.component_manager.update_from_team_files()
        self.trajectory_data = None
        self.max_altitude = None
        self.altitude_deficit = None
        self.analysis_results = {}
        self.suggestions = []
        
    def analyze_trajectory(self, r, rc, time_points):
        """
        Args:
            r: List of rocket_variables from simulation
            rc: rocket_constants object
            time_points: List of time points
        """
        self.trajectory_data = {
            'states': r,
            'constants': rc,
            'time': time_points
        }
        
        altitudes = [state.altitude for state in r]
        velocities = [state.speed for state in r]
        fuel_masses = [state.fuel_mass for state in r]
        dynamic_pressures = [state.dynamic_pressure for state in r]
        
        self.max_altitude = max(altitudes)
        self.altitude_deficit = self.target_altitude - self.max_altitude
        
        max_vel_idx = velocities.index(max(velocities))
        burnout_idx = next((i for i, mass in enumerate(fuel_masses) if mass == 0), len(fuel_masses)-1)
        max_q_idx = dynamic_pressures.index(max(dynamic_pressures))
        apogee_idx = altitudes.index(self.max_altitude)
        
        self.analysis_results = {
            'max_altitude': self.max_altitude,
            'altitude_deficit': self.altitude_deficit,
            'max_velocity': velocities[max_vel_idx],
            'max_velocity_altitude': altitudes[max_vel_idx],
            'burnout_velocity': velocities[burnout_idx],
            'burnout_altitude': altitudes[burnout_idx],
            'burnout_time': time_points[burnout_idx],
            'max_q': max(dynamic_pressures),
            'max_q_altitude': altitudes[max_q_idx],
            'apogee_time': time_points[apogee_idx],
            'total_impulse': rc.fuel_flow_rate * rc.isp_sea * 9.81 * time_points[burnout_idx],
            'mass_ratio': (rc.dry_weight + r[0].fuel_mass) / rc.dry_weight,
            'delta_v_achieved': self._calculate_delta_v(r, rc, burnout_idx),
            'gravity_losses': self._calculate_gravity_losses(r, time_points, burnout_idx),
            'drag_losses': self._calculate_drag_losses(r, rc, time_points, burnout_idx)
        }
        
        return self.analysis_results
    
    def _calculate_delta_v(self, r, rc, burnout_idx):
        initial_mass = rc.dry_weight + r[0].fuel_mass
        final_mass = rc.dry_weight
        avg_isp = (rc.isp_sea + rc.isp_vac) / 2
        
        delta_v_ideal = avg_isp * 9.81 * np.log(initial_mass / final_mass)
        return delta_v_ideal
    
    def _calculate_gravity_losses(self, r, time_points, burnout_idx):
        g = 9.81
        gravity_loss = 0
        
        for i in range(1, min(burnout_idx, len(r))):
            dt = time_points[i] - time_points[i-1]
            vertical_component = 1.0
            gravity_loss += g * vertical_component * dt
            
        return gravity_loss
    
    def _calculate_drag_losses(self, r, rc, time_points, burnout_idx):
        drag_loss = 0
        
        for i in range(1, min(burnout_idx, len(r))):
            dt = time_points[i] - time_points[i-1]
            velocity = r[i].speed
            
            altitude = r[i].altitude
            atm = self.std_atm.calculate(altitude)
            rho = atm[3]
            
            A = np.pi * rc.rocket_radius ** 2
            Cd = rc.drag_coefficient
            drag_force = 0.5 * rho * Cd * A * velocity * abs(velocity)
            current_mass = rc.dry_weight + r[i].fuel_mass
            if current_mass > 0:
                drag_loss += abs(drag_force) / current_mass * dt
                
        return drag_loss
    
    def generate_suggestions(self):
        self.suggestions = []
        
        if self.altitude_deficit <= 0:
            self.suggestions.append({
                'priority': 0,
                'category': 'Success',
                'suggestion': f'Target altitude of {self.target_altitude/1000:.0f} km already achieved!',
                'impact': f'Current max altitude: {self.max_altitude/1000:.1f} km'
            })
            return self.suggestions
        
        components = self.component_manager.get_component_data()
        self._analyze_mass_reduction(components)
        self._analyze_aerodynamics()
        self._analyze_propellant_optimization(components)
        self._analyze_staging_potential()
        self._analyze_trajectory_optimization()
        
        self.suggestions.sort(key=lambda x: x['priority'])
        return self.suggestions
    
    def _analyze_mass_reduction(self, components):
        """Analyze potential mass reduction opportunities"""
        dry_mass = sum(comp['mass'] for name, comp in components.items() 
                      if 'propellant' not in name.lower())

        mass_reduction_factor = 0.015
        heavy_components = [(name, data['mass']) for name, data in components.items() 
                          if data['mass'] > dry_mass * 0.05 and 'propellant' not in name.lower()]
        heavy_components.sort(key=lambda x: x[1], reverse=True)
        
        for comp_name, mass in heavy_components:
            reduction_potential = mass * 0.15
            altitude_gain = (reduction_potential / dry_mass) * mass_reduction_factor * self.max_altitude
            
            if altitude_gain > 1000:
                self.suggestions.append({
                    'priority': 1,
                    'category': 'Mass Reduction',
                    'suggestion': f'Optimize {comp_name} design for weight reduction',
                    'impact': f'Potential mass saving: {reduction_potential:.1f} kg → ~{altitude_gain/1000:.1f} km altitude gain',
                    'implementation': 'Consider: Composite materials, hollow structures, topology optimization'
                })
        
        if dry_mass > 50:
            total_reduction = dry_mass * 0.1
            altitude_gain = 0.1 * mass_reduction_factor * self.max_altitude
            
            self.suggestions.append({
                'priority': 2,
                'category': 'Structural Optimization',
                'suggestion': 'Implement comprehensive lightweighting program',
                'impact': f'Target: {total_reduction:.1f} kg total reduction → ~{altitude_gain/1000:.1f} km gain',
                'implementation': 'Use carbon fiber composites, aluminum-lithium alloys, optimized wall thicknesses'
            })
    
    def _analyze_aerodynamics(self):
        max_q = self.analysis_results['max_q']
        drag_losses = self.analysis_results['drag_losses']
        drag_reduction_scenarios = [
            (0.05, "Polish surface finish, gap sealing"),
            (0.10, "Optimized nose cone shape (Von Karman or Haack series)"),
            (0.15, "Base drag reduction (boat tail or base bleed)"),
            (0.20, "Complete aerodynamic redesign with CFD optimization")
        ]
        
        for reduction, description in drag_reduction_scenarios:
            altitude_gain = reduction * drag_losses / self.analysis_results['max_velocity'] * self.max_altitude * 0.3
            
            if altitude_gain > 500:
                self.suggestions.append({
                    'priority': 3,
                    'category': 'Aerodynamics',
                    'suggestion': description,
                    'impact': f'{reduction*100:.0f}% drag reduction → ~{altitude_gain/1000:.1f} km altitude gain',
                    'implementation': f'Current Cd: {config.drag_coefficient:.2f}, Target: {config.drag_coefficient*(1-reduction):.2f}'
                })
    
    def _analyze_propellant_optimization(self, components):
        propellant_mass = next((comp['mass'] for name, comp in components.items() 
                               if 'propellant' in name.lower()), 0)
        
        current_mass_ratio = self.analysis_results['mass_ratio']
        optimal_mass_ratio = 4.0
        
        if current_mass_ratio < optimal_mass_ratio:
            additional_propellant = components.get('fuselage_oxi', {}).get('mass', 0) * 0.1  # 10% tank margin
            new_mass_ratio = (self.trajectory_data['constants'].dry_weight + propellant_mass + additional_propellant) / self.trajectory_data['constants'].dry_weight
            altitude_gain = self.max_altitude * (np.log(new_mass_ratio) - np.log(current_mass_ratio)) / np.log(current_mass_ratio)
            if altitude_gain > 1000:
                self.suggestions.append({
                    'priority': 1,
                    'category': 'Propellant Optimization',
                    'suggestion': 'Increase propellant loading',
                    'impact': f'Add {additional_propellant:.1f} kg propellant → ~{altitude_gain/1000:.1f} km gain',
                    'implementation': 'Verify tank capacity and structural margins'
                })
    
    def _analyze_staging_potential(self):
        if self.altitude_deficit > 20000:
            staging_gain = self.max_altitude * 0.4
            
            self.suggestions.append({
                'priority': 4,
                'category': 'Configuration Change',
                'suggestion': 'Consider two-stage configuration',
                'impact': f'Potential altitude gain: ~{staging_gain/1000:.1f} km',
                'implementation': 'Add small solid booster stage or convert to two-stage design'
            })
    
    def _analyze_trajectory_optimization(self):
        burnout_altitude = self.analysis_results['burnout_altitude']
        burnout_velocity = self.analysis_results['burnout_velocity']
        avg_climb_rate = burnout_altitude / self.analysis_results['burnout_time']
        avg_horizontal_vel = np.sqrt(max(0, burnout_velocity**2 - avg_climb_rate**2))
        
        if avg_horizontal_vel > 0:
            flight_angle = np.degrees(np.arctan(avg_climb_rate / avg_horizontal_vel))
        else:
            flight_angle = 90
        
        optimal_angle = 40  # degrees
        
        if abs(flight_angle - optimal_angle) > 10:
            altitude_gain = self.max_altitude * 0.1
            
            self.suggestions.append({
                'priority': 2,
                'category': 'Trajectory Optimization',
                'suggestion': 'Optimize launch angle and thrust vectoring',
                'impact': f'Current angle: ~{flight_angle:.0f}°, Optimal: {optimal_angle}° → ~{altitude_gain/1000:.1f} km gain',
                'implementation': 'Add simple thrust vectoring or optimize launch rail angle'
            })

    def plot_analysis(self):
        if not self.trajectory_data:
            print("No trajectory data available for plotting")
            return
        
        fig = plt.figure(figsize=(15, 10))
        
        ax1 = plt.subplot(2, 3, 1)
        altitudes = [state.altitude for state in self.trajectory_data['states']]
        times = self.trajectory_data['time']
        ax1.plot(times, altitudes, 'b-', linewidth=2)
        ax1.axhline(y=self.target_altitude, color='r', linestyle='--', label=f'Target: {self.target_altitude/1000:.0f} km')
        ax1.axhline(y=self.max_altitude, color='g', linestyle='--', label=f'Achieved: {self.max_altitude/1000:.1f} km')
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('Altitude (m)')
        ax1.set_title('Altitude Profile')
        ax1.legend()
        ax1.grid(True)
        
        ax2 = plt.subplot(2, 3, 2)
        velocities = [state.speed for state in self.trajectory_data['states']]
        ax2.plot(times, velocities, 'g-', linewidth=2)
        burnout_time = self.analysis_results['burnout_time']
        ax2.axvline(x=burnout_time, color='r', linestyle='--', label='Burnout')
        ax2.set_xlabel('Time (s)')
        ax2.set_ylabel('Velocity (m/s)')
        ax2.set_title('Velocity Profile')
        ax2.legend()
        ax2.grid(True)
        
        ax3 = plt.subplot(2, 3, 3)
        components = self.component_manager.get_component_data()
        mass_threshold = sum(comp['mass'] for comp in components.values()) * 0.05
        labels = []
        masses = []
        colors = []
        color_map = {
            'propellant': '#1f77b4',
            'fuselage': '#ff7f0e',
            'engine': '#2ca02c',
            'nozzle': '#d62728',
            'nose': '#9467bd',
            'fins': '#8c564b',
            'recovery': '#e377c2',
            'other': '#7f7f7f'
        }
        
        other_mass = 0
        for name, data in components.items():
            if data['mass'] > mass_threshold:
                labels.append(name)
                masses.append(data['mass'])
                color_found = False
                for key, color in color_map.items():
                    if key in name.lower():
                        colors.append(color)
                        color_found = True
                        break
                if not color_found:
                    colors.append('#7f7f7f')
            else:
                other_mass += data['mass']
        
        if other_mass > 0:
            labels.append('Other')
            masses.append(other_mass)
            colors.append('#7f7f7f')
        
        ax3.pie(masses, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax3.set_title('Mass Distribution')
        
        ax4 = plt.subplot(2, 3, 4)
        kinetic_energy = [0.5 * (self.trajectory_data['constants'].dry_weight + state.fuel_mass) * state.speed**2 
                         for state in self.trajectory_data['states']]
        potential_energy = [(self.trajectory_data['constants'].dry_weight + state.fuel_mass) * 9.81 * state.altitude 
                           for state in self.trajectory_data['states']]
        total_energy = [ke + pe for ke, pe in zip(kinetic_energy, potential_energy)]
        
        ax4.plot(times, np.array(kinetic_energy)/1e6, 'r-', label='Kinetic')
        ax4.plot(times, np.array(potential_energy)/1e6, 'b-', label='Potential')
        ax4.plot(times, np.array(total_energy)/1e6, 'k-', label='Total', linewidth=2)
        ax4.set_xlabel('Time (s)')
        ax4.set_ylabel('Energy (MJ)')
        ax4.set_title('Energy Analysis')
        ax4.legend()
        ax4.grid(True)
        ax5 = plt.subplot(2, 3, 5)
        deficit_percent = (self.altitude_deficit / self.target_altitude) * 100
        achieved_percent = 100 - deficit_percent
        ax5.bar(['Current Design'], [achieved_percent], color='green', label='Achieved')
        ax5.bar(['Current Design'], [deficit_percent], bottom=[achieved_percent], 
                color='red', label='Deficit')
        
        ax5.text(0, achieved_percent/2, f'{self.max_altitude/1000:.1f} km\n({achieved_percent:.1f}%)', 
                ha='center', va='center', fontweight='bold')
        ax5.text(0, achieved_percent + deficit_percent/2, f'{self.altitude_deficit/1000:.1f} km\n({deficit_percent:.1f}%)', 
                ha='center', va='center', fontweight='bold')
        
        ax5.set_ylabel('Altitude (%)')
        ax5.set_title('Target Achievement')
        ax5.set_ylim(0, 100)
        ax5.legend()
        
        ax6 = plt.subplot(2, 3, 6)
        ax6.axis('off')
        summary_text = "TOP OPTIMIZATION SUGGESTIONS:\n\n"
        
        for i, suggestion in enumerate(self.suggestions[:5]):
            summary_text += f"{i+1}. {suggestion['category']}:\n"
            summary_text += f"   {suggestion['suggestion']}\n"
            summary_text += f"   Impact: {suggestion['impact']}\n\n"
        
        ax6.text(0.05, 0.95, summary_text, transform=ax6.transAxes, 
                fontsize=10, verticalalignment='top', fontfamily='monospace')
        
        plt.tight_layout()
        
        return fig
    
    def generate_report(self):
        report = []
        report.append("="*60)
        report.append("TRAJECTORY OPTIMIZATION ANALYSIS REPORT")
        report.append("="*60)
        report.append(f"\nTarget Altitude: {self.target_altitude/1000:.0f} km")
        report.append(f"Achieved Altitude: {self.max_altitude/1000:.1f} km")
        report.append(f"Altitude Deficit: {self.altitude_deficit/1000:.1f} km ({(self.altitude_deficit/self.target_altitude)*100:.1f}%)")
        
        report.append("\n" + "-"*40)
        report.append("CURRENT PERFORMANCE METRICS:")
        report.append("-"*40)
        report.append(f"Max Velocity: {self.analysis_results['max_velocity']:.1f} m/s at {self.analysis_results['max_velocity_altitude']:.0f} m")
        report.append(f"Burnout: {self.analysis_results['burnout_velocity']:.1f} m/s at {self.analysis_results['burnout_altitude']:.0f} m")
        report.append(f"Burnout Time: {self.analysis_results['burnout_time']:.1f} s")
        report.append(f"Max Dynamic Pressure: {self.analysis_results['max_q']:.0f} Pa")
        report.append(f"Mass Ratio: {self.analysis_results['mass_ratio']:.2f}")
        report.append(f"Gravity Losses: {self.analysis_results['gravity_losses']:.0f} m/s")
        report.append(f"Drag Losses: {self.analysis_results['drag_losses']:.0f} m/s")
        
        report.append("\n" + "-"*40)
        report.append("MASS BREAKDOWN:")
        report.append("-"*40)
        
        components = self.component_manager.get_component_data()
        total_mass = sum(comp['mass'] for comp in components.values())
        
        for name, data in sorted(components.items(), key=lambda x: x[1]['mass'], reverse=True):
            percentage = (data['mass'] / total_mass) * 100
            report.append(f"{name:<20} {data['mass']:>8.2f} kg ({percentage:>5.1f}%)")
        
        report.append(f"{'TOTAL':<20} {total_mass:>8.2f} kg")
        report.append("\n" + "="*60)
        report.append("OPTIMIZATION SUGGESTIONS:")
        report.append("="*60)
        categories = {}
        for suggestion in self.suggestions:
            category = suggestion['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(suggestion)
        
        for category, suggestions in categories.items():
            report.append(f"\n{category.upper()}:")
            report.append("-" * len(category))
            
            for i, suggestion in enumerate(suggestions, 1):
                report.append(f"\n{i}. {suggestion['suggestion']}")
                report.append(f"   Expected Impact: {suggestion['impact']}")
                if 'implementation' in suggestion:
                    report.append(f"   Implementation: {suggestion['implementation']}")
        
        report.append("\n" + "="*60)
        report.append("SUMMARY:")
        report.append("="*60)
        
        if self.altitude_deficit <= 0:
            report.append("✓ Target altitude achieved! No optimization required.")
        else:
            total_gain = sum(float(s['impact'].split('→')[-1].split('km')[0].strip().replace('~', '')) 
                           for s in self.suggestions[:3] if '→' in s['impact'] and 'km' in s['impact'])
            
            report.append(f"Combined optimization potential: ~{total_gain:.1f} km")
            
            if total_gain > self.altitude_deficit:
                report.append("✓ Target altitude is achievable with suggested optimizations!")
            else:
                report.append("⚠ Additional measures may be needed to reach target altitude.")
                report.append("  Consider more aggressive optimization or design changes.")
        
        return "\n".join(report)