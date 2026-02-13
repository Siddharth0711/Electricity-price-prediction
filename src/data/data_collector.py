"""
Data Collection Module
Generates synthetic weather, energy generation, and market data for MCP forecasting.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yaml
import json
from pathlib import Path


class DataCollector:
    """Collects and generates synthetic data for training and testing."""
    
    def __init__(self, config_path="config/data_sources.yaml"):
        """Initialize data collector with configuration."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.renewable_config = self.config['renewable_sources']
        self.non_renewable_config = self.config['non_renewable_sources']
        self.weather_config = self.config['weather_features']
        
    def generate_synthetic_data(self, start_date, end_date, freq='H'):
        """
        Generate synthetic dataset with weather, generation, and MCP data.
        
        Args:
            start_date: Start date for data generation
            end_date: End date for data generation
            freq: Frequency ('H' for hourly, 'D' for daily)
            
        Returns:
            DataFrame with all features and target (MCP)
        """
        # Create timestamp index
        timestamps = pd.date_range(start=start_date, end=end_date, freq=freq)
        n = len(timestamps)
        
        # Generate weather data
        weather_data = self._generate_weather_data(timestamps)
        
        # Generate renewable generation based on weather
        renewable_gen = self._generate_renewable_generation(weather_data)
        
        # Generate demand pattern
        demand = self._generate_demand(timestamps, weather_data)
        
        # Calculate non-renewable generation needed
        non_renewable_gen = self._generate_non_renewable_generation(
            demand, renewable_gen
        )
        
        # Calculate MCP based on supply-demand dynamics
        mcp = self._calculate_mcp(renewable_gen, non_renewable_gen, demand, timestamps)
        
        # Combine all data
        data = pd.concat([
            weather_data,
            renewable_gen,
            non_renewable_gen,
            pd.DataFrame({'demand_mw': demand, 'mcp_inr_per_mwh': mcp}, index=timestamps)
        ], axis=1)
        
        data.index.name = 'timestamp'
        return data
    
    def _generate_weather_data(self, timestamps):
        """Generate realistic weather patterns."""
        n = len(timestamps)
        
        # Extract time features for seasonal patterns
        hours = timestamps.hour
        day_of_year = timestamps.dayofyear
        
        # Temperature: seasonal + daily variation
        temp_mean = 25 + 10 * np.sin(2 * np.pi * day_of_year / 365)
        temp_daily = -5 * np.cos(2 * np.pi * hours / 24)
        temperature = temp_mean + temp_daily + np.random.normal(0, 3, n)
        
        # Solar irradiance: zero at night, peak at noon
        irradiance_base = np.maximum(0, 1000 * np.sin(np.pi * (hours - 6) / 12))
        cloud_cover = np.random.uniform(0, 100, n)
        solar_irradiance = irradiance_base * (1 - cloud_cover / 150) + np.random.normal(0, 50, n)
        solar_irradiance = np.maximum(0, solar_irradiance)
        
        # Wind speed: random with some persistence
        wind_speed = np.zeros(n)
        wind_speed[0] = np.random.uniform(3, 15)
        for i in range(1, n):
            wind_speed[i] = wind_speed[i-1] * 0.8 + np.random.uniform(0, 8)
        wind_speed = np.clip(wind_speed, 0, 30)
        
        # Wind direction
        wind_direction = np.random.uniform(0, 360, n)
        
        # Rainfall: sparse events
        rainfall = np.zeros(n)
        rain_events = np.random.choice(n, size=int(n * 0.1), replace=False)
        rainfall[rain_events] = np.random.exponential(5, len(rain_events))
        
        # Humidity
        humidity = np.random.uniform(40, 90, n)
        
        weather_df = pd.DataFrame({
            'temperature_celsius': temperature,
            'solar_irradiance_w_m2': solar_irradiance,
            'wind_speed_m_s': wind_speed,
            'wind_direction_degrees': wind_direction,
            'rainfall_mm_hr': rainfall,
            'cloud_cover_percent': cloud_cover,
            'humidity_percent': humidity
        }, index=timestamps)
        
        return weather_df
    
    def _generate_renewable_generation(self, weather_data):
        """Calculate renewable generation from weather data."""
        # Solar generation
        irradiance = weather_data['solar_irradiance_w_m2']
        temp = weather_data['temperature_celsius']
        solar_capacity = self.renewable_config['solar']['capacity_mw']
        efficiency = np.mean(self.renewable_config['solar']['efficiency_range'])
        
        # Temperature derate: performance decreases above 25C
        temp_coeff = 1 - 0.004 * (temp - 25)
        solar_gen = (irradiance / 1000) * solar_capacity * efficiency * temp_coeff
        solar_gen = np.maximum(0, solar_gen)
        
        # Wind generation
        wind_speed = weather_data['wind_speed_m_s']
        wind_capacity = self.renewable_config['wind']['capacity_mw']
        cut_in = self.renewable_config['wind']['cut_in_speed']
        rated = self.renewable_config['wind']['rated_speed']
        cut_out = self.renewable_config['wind']['cut_out_speed']
        
        wind_gen = np.where(
            wind_speed < cut_in, 0,
            np.where(
                wind_speed < rated,
                wind_capacity * ((wind_speed - cut_in) / (rated - cut_in)) ** 3,
                np.where(wind_speed < cut_out, wind_capacity, 0)
            )
        )
        
        # Hydro: baseline + rainfall contribution
        hydro_capacity = self.renewable_config['hydro']['capacity_mw']
        rainfall = weather_data['rainfall_mm_hr']
        hydro_baseline = hydro_capacity * 0.6  # 60% base generation
        hydro_rainfall_boost = rainfall.rolling(24, min_periods=1).sum() * 10
        hydro_gen = np.minimum(hydro_baseline + hydro_rainfall_boost, hydro_capacity)
        
        # Biomass: constant
        biomass_capacity = self.renewable_config['biomass']['capacity_mw']
        biomass_gen = np.full(len(weather_data), biomass_capacity * 0.8)
        
        renewable_df = pd.DataFrame({
            'solar_gen_mw': solar_gen,
            'wind_gen_mw': wind_gen,
            'hydro_gen_mw': hydro_gen,
            'biomass_gen_mw': biomass_gen,
            'total_renewable_mw': solar_gen + wind_gen + hydro_gen + biomass_gen
        }, index=weather_data.index)
        
        return renewable_df
    
    def _generate_demand(self, timestamps, weather_data):
        """Generate demand pattern based on time and weather."""
        hours = timestamps.hour
        day_of_week = timestamps.dayofweek
        temp = weather_data['temperature_celsius'].values
        
        # Base demand pattern: higher during day, lower at night
        base_demand = 12000 + 5000 * np.sin(2 * np.pi * (hours - 6) / 24)
        
        # Weekend reduction
        weekend_factor = np.where(day_of_week >= 5, 0.85, 1.0)
        
        # Temperature impact: cooling demand in summer, heating in winter
        temp_impact = 100 * (np.abs(temp - 22))
        
        # Random variation
        noise = np.random.normal(0, 500, len(timestamps))
        
        demand = base_demand * weekend_factor + temp_impact + noise
        demand = np.maximum(demand, 5000)  # Minimum demand
        
        return demand
    
    def _generate_non_renewable_generation(self, demand, renewable_gen):
        """Calculate non-renewable generation needed to meet demand."""
        total_renewable = renewable_gen['total_renewable_mw'].values
        shortfall = demand - total_renewable
        
        # Nuclear: base load
        nuclear_capacity = self.non_renewable_config['nuclear']['capacity_mw']
        nuclear_gen = np.full(len(demand), nuclear_capacity * 0.9)
        
        remaining = shortfall - nuclear_gen
        
        # Coal: main load follower
        coal_capacity = self.non_renewable_config['coal']['capacity_mw']
        coal_min = coal_capacity * self.non_renewable_config['coal']['min_output']
        coal_gen = np.clip(remaining * 0.6, coal_min, coal_capacity)
        
        remaining = remaining - coal_gen
        
        # Gas: peak load and fast response
        gas_capacity = self.non_renewable_config['thermal_gas']['capacity_mw']
        gas_gen = np.clip(remaining, 0, gas_capacity)
        
        non_renewable_df = pd.DataFrame({
            'coal_gen_mw': coal_gen,
            'gas_gen_mw': gas_gen,
            'nuclear_gen_mw': nuclear_gen,
            'total_non_renewable_mw': coal_gen + gas_gen + nuclear_gen
        }, index=renewable_gen.index)
        
        return non_renewable_df
    
    def _calculate_mcp(self, renewable_gen, non_renewable_gen, demand, timestamps):
        """
        Calculate MCP based on merit order dispatch.
        MCP is set by the marginal generator (most expensive source needed).
        """
        total_renewable = renewable_gen['total_renewable_mw'].values
        coal = non_renewable_gen['coal_gen_mw'].values
        gas = non_renewable_gen['gas_gen_mw'].values
        nuclear = non_renewable_gen['nuclear_gen_mw'].values
        
        # Marginal costs
        cost_renewable = 0  # Zero marginal cost
        cost_nuclear = self.non_renewable_config['nuclear']['marginal_cost_per_mwh']
        cost_coal = self.non_renewable_config['coal']['marginal_cost_per_mwh']
        cost_gas = self.non_renewable_config['thermal_gas']['marginal_cost_per_mwh']
        
        # Determine marginal generator
        mcp = np.zeros(len(demand))
        
        for i in range(len(demand)):
            # Merit order: renewable -> nuclear -> coal -> gas
            if gas[i] > 0:
                # Gas is the marginal generator
                mcp[i] = cost_gas
            elif coal[i] > coal[i] * 0.5:  # Coal above 50% capacity
                mcp[i] = cost_coal
            elif nuclear[i] > 0:
                mcp[i] = cost_nuclear
            else:
                mcp[i] = cost_renewable + 20  # Small premium for renewable-only
        
        # Add demand-supply tension factor
        supply = total_renewable + coal + gas + nuclear
        tension = (demand - supply) / demand
        tension_premium = np.maximum(0, tension * 50)
        
        # Add time-of-day premium (peak hours)
        hours = timestamps.hour
        peak_premium = np.where((hours >= 18) & (hours <= 22), 15, 0)
        
        # Random market volatility
        volatility = np.random.normal(0, 5, len(demand))
        
        mcp = mcp + tension_premium + peak_premium + volatility
        mcp = np.maximum(mcp, 20)  # Floor price
        
        return mcp
    
    def save_data(self, data, filepath):
        """Save generated data to CSV."""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        data.to_csv(filepath)
        print(f"Data saved to {filepath}")


if __name__ == "__main__":
    # Generate 2 years of hourly data
    collector = DataCollector()
    
    print("Generating synthetic data...")
    data = collector.generate_synthetic_data(
        start_date='2023-01-01',
        end_date='2024-12-31',
        freq='H'
    )
    
    print(f"Generated {len(data)} samples")
    print(f"Features: {list(data.columns)}")
    print(f"\nData summary:")
    print(data.describe())
    
    # Save to processed data folder
    collector.save_data(data, 'data/processed/market_weather_energy_data.csv')
    
    print("\nData collection complete!")
