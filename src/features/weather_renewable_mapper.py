"""
Weather to Renewable Generation Mapper
Maps weather features to renewable energy generation estimates.
"""

import pandas as pd
import numpy as np
import yaml


class WeatherRenewableMapper:
    """Maps weather conditions to renewable energy generation."""
    
    def __init__(self, config_path="config/data_sources.yaml"):
        """Initialize with energy source configuration."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.solar_config = self.config['renewable_sources']['solar']
        self.wind_config = self.config['renewable_sources']['wind']
        self.hydro_config = self.config['renewable_sources']['hydro']
    
    def calculate_solar_potential(self, irradiance, temperature, cloud_cover):
        """
        Calculate solar generation potential from weather.
        
        Args:
            irradiance: Solar irradiance (W/m²)
            temperature: Temperature (°C)
            cloud_cover: Cloud cover (%)
            
        Returns:
            Solar generation estimate (MW)
        """
        capacity = self.solar_config['capacity_mw']
        efficiency = np.mean(self.solar_config['efficiency_range'])
        
        # Normalized irradiance (1000 W/m² = standard test condition)
        normalized_irradiance = irradiance / 1000.0
        
        # Temperature coefficient: -0.4% per °C above 25°C
        temp_coeff = 1 - 0.004 * (temperature - 25)
        
        # Cloud impact
        cloud_factor = 1 - (cloud_cover / 150)  # Partial reduction
        
        generation = capacity * normalized_irradiance * efficiency * temp_coeff * cloud_factor
        generation = np.maximum(0, np.minimum(generation, capacity))
        
        return generation
    
    def calculate_wind_potential(self, wind_speed):
        """
        Calculate wind generation potential using power curve.
        
        Args:
            wind_speed: Wind speed (m/s)
            
        Returns:
            Wind generation estimate (MW)
        """
        capacity = self.wind_config['capacity_mw']
        cut_in = self.wind_config['cut_in_speed']
        rated = self.wind_config['rated_speed']
        cut_out = self.wind_config['cut_out_speed']
        
        # Wind turbine power curve
        generation = np.where(
            wind_speed < cut_in, 0,
            np.where(
                wind_speed < rated,
                capacity * ((wind_speed - cut_in) / (rated - cut_in)) ** 3,
                np.where(wind_speed < cut_out, capacity, 0)
            )
        )
        
        return generation
    
    def calculate_hydro_potential(self, rainfall, rainfall_history_24h):
        """
        Calculate hydro generation potential.
        
        Args:
            rainfall: Current rainfall (mm/hr)
            rainfall_history_24h: Cumulative rainfall past 24 hours (mm)
            
        Returns:
            Hydro generation estimate (MW)
        """
        capacity = self.hydro_config['capacity_mw']
        
        # Baseline generation (run-of-river)
        baseline = capacity * 0.6
        
        # Rainfall contribution with delay
        rainfall_boost = rainfall_history_24h * 5  # MW per mm
        
        generation = np.minimum(baseline + rainfall_boost, capacity)
        generation = np.maximum(generation, capacity * 0.3)  # Minimum flow
        
        return generation
    
    def create_renewable_features(self, weather_data):
        """
        Create renewable generation features from weather data.
        Maps hub-specific weather data to regional potentials.
        """
        df = weather_data.copy()
        
        # 1. Solar Potential (Rajasthan Hub)
        # Using hub-specific columns if they exist
        irradiance = df['solar_hub_irradiance'] if 'solar_hub_irradiance' in df.columns else np.zeros(len(df))
        # If irradiance not available, use coco as proxy (3=Clear, 0=Cloudy)
        if (irradiance == 0).all() and 'solar_hub_coco' in df.columns:
            # Simple heuristic: Clear=800, Cloudy=200
            irradiance = np.where(df['solar_hub_coco'] <= 2, 800, 200)
            
        df['solar_potential_mw'] = self.calculate_solar_potential(
            irradiance,
            df['solar_hub_temp'] if 'solar_hub_temp' in df.columns else 25,
            df['solar_hub_coco'] * 10 if 'solar_hub_coco' in df.columns else 0 # coco as cloud proxy
        )
        
        # 2. Wind Potential (Tamil Nadu Hub)
        # Meteostat wspd is in km/h, convert to m/s
        wind_speed_kmh = df['wind_hub_wspd'] if 'wind_hub_wspd' in df.columns else 0
        wind_speed_ms = wind_speed_kmh / 3.6
        df['wind_potential_mw'] = self.calculate_wind_potential(wind_speed_ms)
        
        # 3. Hydro Potential (proxy for rainfall)
        rainfall = df['demand_hub_prcp'] if 'demand_hub_prcp' in df.columns else 0
        rainfall_24h = rainfall.rolling(24, min_periods=1).sum()
        df['hydro_potential_mw'] = self.calculate_hydro_potential(rainfall, rainfall_24h)
        
        # Total renewable potential
        df['total_renewable_potential_mw'] = (
            df['solar_potential_mw'] + 
            df['wind_potential_mw'] + 
            df['hydro_potential_mw']
        )
        
        return df


if __name__ == "__main__":
    # Test the mapper
    mapper = WeatherRenewableMapper()
    
    # Load sample weather data
    print("Loading weather data...")
    data = pd.read_csv('data/processed/market_weather_energy_data.csv', 
                      parse_dates=['timestamp'], index_col='timestamp')
    
    print("Mapping weather to renewable generation...")
    renewable_features = mapper.create_renewable_features(data)
    
    print(f"\nCreated features:")
    renewable_cols = [c for c in renewable_features.columns if 'potential' in c or 'mix' in c]
    print(renewable_cols)
    
    print(f"\nSample data:")
    print(renewable_features[renewable_cols].head())
    
    print(f"\nRenewable generation summary:")
    print(renewable_features[renewable_cols].describe())
