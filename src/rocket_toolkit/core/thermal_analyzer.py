import numpy as np
from rocket_toolkit.models.atmosphere_model import AtmosphereModel
from rocket_toolkit.core.thermal_data import FinTemperatureTracker
from rocket_toolkit import config
import time

class ThermalAnalysis:
    def __init__(self, rocket_fin):
        self.fin = rocket_fin
        self.atm_model = AtmosphereModel()
        self.mesh_size = 30
        self.comparison_mesh_size = 15  # Smaller mesh for comparison runs
        self.current_temperature = None
        self.is_comparison_mode = False
        self.max_temperature_reached = None  # Track global maximum temperature
        self.max_temperature_info = None  # Store info about when max temp occurs
        self.frame_temperatures = []  # Store temperatures at specific time points
        
        # Performance optimization caches
        self._atmosphere_cache = {}
        self._heating_params_cache = {}
        self._mesh_cache = {}
        self._material_props_cache = None
        self._last_altitude = None
        self._last_velocity = None
        
        self._sigma = 5.67e-8  # Stefan-Boltzmann constant
        self._gamma = 1.4
        self._Pr = 0.71  # Prandtl number for air
        self._cp = 1005  # J/(kg·K)
        
        self.initialize_temperature_field()
    
    def set_comparison_mode(self, enabled=True):
        old_mode = self.is_comparison_mode
        self.is_comparison_mode = enabled
        
        new_mesh_size = self.comparison_mesh_size if enabled else 30
        if new_mesh_size != self.mesh_size:
            self.mesh_size = new_mesh_size
            # Clear mesh cache when size changes
            self._mesh_cache.clear()
            self.initialize_temperature_field()
    
    def reset_max_temperature(self):
        if self.current_temperature is not None:
            self.max_temperature_reached = self.current_temperature.copy()
            self.max_temperature_info = None
            self.frame_temperatures = []
    
    def _get_cached_atmosphere(self, altitude):
        cache_key = round(altitude / 100) * 100
        
        if cache_key not in self._atmosphere_cache:
            self._atmosphere_cache[cache_key] = self.atm_model.get_atmosphere_properties(cache_key)
            
            if len(self._atmosphere_cache) > 100:
                keys_to_remove = list(self._atmosphere_cache.keys())[:50]
                for key in keys_to_remove:
                    del self._atmosphere_cache[key]
                    
        return self._atmosphere_cache[cache_key]
    
    def _get_material_properties(self):
        if self._material_props_cache is None:
            self._material_props_cache = {
                'k': self.fin.thermal_conductivity,
                'rho': self.fin.density,
                'cp': self.fin.specific_heat,
                'emissivity': self.fin.emissivity,
                'alpha': self.fin.thermal_conductivity / (self.fin.density * self.fin.specific_heat)
            }
        return self._material_props_cache
    
    def initialize_temperature_field(self):
        if self.fin.fin_height is None or self.fin.fin_width is None:
            self.fin.calculate_fin_dimensions(verbose=False)
            
        cache_key = (self.mesh_size, self.fin.fin_height, self.fin.fin_width)
        
        if cache_key in self._mesh_cache:
            cached_data = self._mesh_cache[cache_key]
            self.X = cached_data['X']
            self.Y = cached_data['Y']
            self.fin_mask = cached_data['mask']
            self._dx = cached_data['dx']
            self._dy = cached_data['dy']
        else:
            height_m = self.fin.fin_height / 1000
            width_m = self.fin.fin_width / 1000
            
            nx = ny = self.mesh_size
            x = np.linspace(0, width_m, nx)
            y = np.linspace(0, height_m, ny)
            self.X, self.Y = np.meshgrid(x, y)
            
            self._dx = width_m / (nx - 1)
            self._dy = height_m / (ny - 1)
            
            leading_edge_x = (self.Y / height_m) * width_m
            self.fin_mask = self.X < leading_edge_x
            
            self._mesh_cache[cache_key] = {
                'X': self.X,
                'Y': self.Y,
                'mask': self.fin_mask,
                'dx': self._dx,
                'dy': self._dy
            }
        
        altitude = self.fin.altitude if hasattr(self.fin, 'altitude') and self.fin.altitude is not None else 0
        atm_props = self._get_cached_atmosphere(altitude)
        air_temp = atm_props["temperature"]
        
        self.current_temperature = np.full_like(self.X, air_temp)
        
        self.max_temperature_reached = self.current_temperature.copy()
        self.max_temperature_info = None
        self.frame_temperatures = []
        
        return self.X, self.Y, self.current_temperature
    
    def calculate_aerodynamic_heating(self, atm_props):
        velocity = self.fin.velocity
        altitude = self.fin.altitude
        cache_key = (round(velocity), round(altitude / 100) * 100)
        
        if cache_key in self._heating_params_cache:
            return self._heating_params_cache[cache_key]
        
        air_temp = atm_props["temperature"]
        air_density = atm_props["density"]
        air_viscosity = atm_props["viscosity"]
        speed_of_sound = atm_props["speed_of_sound"]
        
        L_char = self.fin.fin_width / 1000 if self.fin.fin_width is not None else 0.5
        
        mach = velocity / speed_of_sound if speed_of_sound > 0 else 0
        
        if velocity > 0 and air_viscosity > 0:
            Re = air_density * velocity * L_char / air_viscosity
        else:
            Re = 1000
        
        # Recovery factor (pre-calculated for common conditions)
        if Re < 5e5:  # Laminar
            r = self._Pr**(1/3)
        else:  # Turbulent
            r = self._Pr**(1/3)
        
        # For hypersonic flow, recovery factor approaches 1
        if mach > 3:
            r = 0.89 + (1.0 - 0.89) * min((mach - 3) / 3, 1)
        
        T_stagnation = air_temp * (1 + ((self._gamma - 1) / 2) * mach**2)
        
        T_recovery = air_temp + r * (T_stagnation - air_temp)
        
        if mach > 0.1 and velocity > 10:
            R_nose = 0.1  # Effective nose radius
            rho_inf = air_density
            V_inf = velocity
            
            # Simplified Fay-Riddell for stagnation point
            h_stag_FR = 0.94 * np.sqrt(rho_inf * V_inf / R_nose) * self._cp * (T_recovery - air_temp) / V_inf
            
            if Re > 0:
                T_ref = 0.5 * (T_recovery + air_temp) + 0.22 * (T_recovery - air_temp)
                rho_ref = air_density * (air_temp / T_ref)
                mu_ref = air_viscosity * (T_ref / air_temp)**0.76
                Re_ref = rho_ref * velocity * L_char / mu_ref if mu_ref > 0 else Re
                
                # Nusselt number calculation
                if Re_ref < 5e5:  # Laminar
                    Nu = 0.664 * Re_ref**0.5 * self._Pr**(1/3)
                else:  # Turbulent
                    Nu = 0.037 * Re_ref**0.8 * self._Pr**(1/3)
                
                k_air = 0.025 * (T_ref / 273)**0.8
                h_avg = Nu * k_air / L_char
                
                # High Mach number correction
                if mach > 1:
                    mach_factor = 1 + 0.5 * (mach - 1)**0.8
                    h_avg = h_avg * mach_factor
            else:
                h_avg = 100
        else:
            h_avg = 50
        
        # Ensure reasonable bounds
        h_avg = np.clip(h_avg, 50, 10000)
        
        result = {
            "Re": Re,
            "Mach": mach,
            "T_stagnation": T_stagnation,
            "T_recovery": T_recovery,
            "h_avg": h_avg,
            "air_temp": air_temp
        }
        
        self._heating_params_cache[cache_key] = result
        
        if len(self._heating_params_cache) > 50:
            keys_to_remove = list(self._heating_params_cache.keys())[:25]
            for key in keys_to_remove:
                del self._heating_params_cache[key]
        
        return result

    def update_temperature_field(self, dt):
        if self.fin.fin_height is None or self.fin.fin_width is None:
            self.fin.calculate_fin_dimensions(verbose=False)
        
        height_m = self.fin.fin_height / 1000
        width_m = self.fin.fin_width / 1000
        thickness_m = self.fin.wall_thickness / 1000
        
        atm_props = self._get_cached_atmosphere(self.fin.altitude)
        air_temp = atm_props["temperature"]
        
        heat_params = self.calculate_aerodynamic_heating(atm_props)
        T_recovery = heat_params["T_recovery"]
        h_avg = heat_params["h_avg"]
        mach = heat_params["Mach"]
        
        mat_props = self._get_material_properties()
        
        if self.current_temperature is None:
            self.initialize_temperature_field()
        
        T_current = self.current_temperature
        leading_edge_x = (self.Y / height_m) * width_m
        
        width_diff = width_m - leading_edge_x
        width_diff = np.where(width_diff > 1e-10, width_diff, 1e-10)
        x_norm = np.clip((self.X - leading_edge_x) / width_diff, 0, 1)
        
        if mach > 3:
            temp_factor = 0.9 * np.exp(-2 * x_norm) + 0.1
        elif mach > 1:
            temp_factor = 0.8 * np.exp(-2 * x_norm) + 0.2
        else:
            temp_factor = 0.6 * np.exp(-1 * x_norm) + 0.4
        
        h_local = h_avg * temp_factor
        
        q_conv = h_local * (T_recovery - T_current)
        q_rad = mat_props['emissivity'] * self._sigma * (T_current**4 - air_temp**4)
        q_net = q_conv - q_rad
        
        dT_dt = q_net / (mat_props['rho'] * mat_props['cp'] * thickness_m)
        
        max_dT = 100 * dt
        dT = np.clip(dT_dt * dt, -max_dT, max_dT)
        
        new_temperature = T_current + dT
        
        new_temperature = np.where(self.fin_mask, air_temp, new_temperature)
        new_temperature = np.clip(new_temperature, air_temp - 50, T_recovery + 50)
        
        self.current_temperature = new_temperature
        
        valid_points = ~self.fin_mask
        if np.any(valid_points):
            current_max = np.max(new_temperature[valid_points])
        else:
            current_max = air_temp
        
        if not self.is_comparison_mode or len(self.frame_temperatures) % 5 == 0:
            self.frame_temperatures.append({
                "temperature": new_temperature.copy(),
                "max_temp": current_max,
                "mach": mach,
                "altitude": self.fin.altitude,
                "velocity": self.fin.velocity,
                "air_temp": air_temp,
                "recovery_temp": T_recovery
            })
        
        if self.max_temperature_reached is None:
            self.max_temperature_reached = new_temperature.copy()
        else:
            self.max_temperature_reached = np.maximum(self.max_temperature_reached, new_temperature)
        
        if np.any(valid_points):
            global_max = np.max(self.max_temperature_reached[valid_points])
        else:
            global_max = air_temp
        
        if current_max >= global_max * 0.999:
            self.max_temperature_info = {
                "mach": mach,
                "altitude": self.fin.altitude,
                "velocity": self.fin.velocity,
                "air_temp": air_temp,
                "recovery_temp": T_recovery
            }
        
        heat_info = {
            "air_temp": air_temp,
            "recovery_temp": T_recovery,
            "mach": mach,
            "reynolds": heat_params["Re"],
            "h_avg": h_avg,
            "material": self.fin.material_name,
            "max_temp_ever": global_max
        }
        
        return self.X, self.Y, new_temperature, heat_info
    
    def calculate_temperature_profile(self, nx=None, ny=None):
        if nx is not None or ny is not None:
            original_mesh_size = self.mesh_size
            self.mesh_size = nx if nx is not None else self.mesh_size
            
            temp_cache = self._mesh_cache.copy()
            self._mesh_cache.clear()
            
            self.initialize_temperature_field()
            result = self.update_temperature_field(100.0)
            
            self.mesh_size = original_mesh_size
            self._mesh_cache = temp_cache
            self.initialize_temperature_field()
            return result
        
        return self.update_temperature_field(100.0)
    
    def get_max_temperature_ever(self):
        if self.max_temperature_reached is not None:
            valid_points = ~self.fin_mask
            if np.any(valid_points):
                return np.max(self.max_temperature_reached[valid_points])
        return np.max(self.current_temperature) if self.current_temperature is not None else None
    
    def get_max_temperature_info(self):
        return self.max_temperature_info
    
    def get_temperature_frames(self):
        return self.frame_temperatures
    
    def clear_caches(self):
        self._atmosphere_cache.clear()
        self._heating_params_cache.clear()
        self._mesh_cache.clear()
        self._material_props_cache = None