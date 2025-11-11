import isacalc as isa

class AtmosphereModel:
    def __init__(self):
        self.std_atm = isa.Atmosphere()
    
    def get_atmosphere_properties(self, altitude):
        atmosphere = self.std_atm.calculate(altitude)
        air_temp = atmosphere[1]  # K
        air_pressure = atmosphere[2]  # Pa
        air_density = atmosphere[3]  # kg/m^3
        speed_of_sound = atmosphere[4]  # m/s
        air_viscosity = atmosphere[5]  # Pas
        
        return {
            "temperature": air_temp,
            "pressure": air_pressure,
            "density": air_density,
            "viscosity": air_viscosity,
            "speed_of_sound": speed_of_sound
        }