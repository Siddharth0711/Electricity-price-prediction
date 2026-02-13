"""
Supply Mix Calculator
Calculates the renewable vs non-renewable mix and marginal cost.
"""

import pandas as pd
import numpy as np
import yaml


class SupplyMixCalculator:
    """Calculates energy supply mix and marginal costs."""
    
    def __init__(self, config_path="config/data_sources.yaml"):
        """Initialize with configuration."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.non_renewable = self.config['non_renewable_sources']
    
    def calculate_supply_mix(self, renewable_gen, demand):
        """
        Calculate the supply mix and cost structure.
        
        Args:
            renewable_gen: DataFrame with renewable generation columns
            demand: Series or array with demand values
            
        Returns:
            DataFrame with supply mix features
        """
        df = pd.DataFrame(index=renewable_gen.index)
        
        # Get total renewable generation
        if 'total_renewable_mw' in renewable_gen.columns:
            total_renewable = renewable_gen['total_renewable_mw']
        else:
            renewable_cols = [c for c in renewable_gen.columns if '_mw' in c]
            total_renewable = renewable_gen[renewable_cols].sum(axis=1)
        
        # Calculate shortfall (demand minus renewables)
        shortfall = demand - total_renewable
        df['renewable_shortfall_mw'] = np.maximum(0, shortfall)
        
        # Calculate renewable penetration
        df['renewable_penetration_pct'] = (total_renewable / demand) * 100
        
        # Estimate non-renewable dispatch using merit order
        non_ren_dispatch = self._calculate_non_renewable_dispatch(shortfall)
        
        df['nuclear_dispatch_mw'] = non_ren_dispatch['nuclear']
        df['coal_dispatch_mw'] = non_ren_dispatch['coal']
        df['gas_dispatch_mw'] = non_ren_dispatch['gas']
        df['total_non_renewable_mw'] = (
            non_ren_dispatch['nuclear'] + 
            non_ren_dispatch['coal'] + 
            non_ren_dispatch['gas']
        )
        
        # Calculate marginal cost
        df['marginal_cost_inr_mwh'] = self._calculate_marginal_cost(non_ren_dispatch)
        
        # Supply-demand metrics
        total_supply = total_renewable + df['total_non_renewable_mw']
        df['supply_demand_ratio'] = total_supply / demand
        df['reserve_margin_pct'] = ((total_supply - demand) / demand) * 100
        
        # Non-renewable mix ratios
        total_non_ren = df['total_non_renewable_mw']
        df['coal_mix_ratio'] = df['coal_dispatch_mw'] / (total_non_ren + 1)
        df['gas_mix_ratio'] = df['gas_dispatch_mw'] / (total_non_ren + 1)
        df['nuclear_mix_ratio'] = df['nuclear_dispatch_mw'] / (total_non_ren + 1)
        
        # Scarcity indicators
        df['is_supply_tight'] = (df['reserve_margin_pct'] < 5).astype(int)
        df['is_gas_marginal'] = (df['gas_dispatch_mw'] > 0).astype(int)
        
        return df
    
    def _calculate_non_renewable_dispatch(self, shortfall):
        """
        Calculate non-renewable dispatch using merit order.
        Merit order: Nuclear (base) -> Coal (mid) -> Gas (peak)
        """
        # Get capacities and constraints
        nuclear_cap = self.non_renewable['nuclear']['capacity_mw']
        nuclear_min = self.non_renewable['nuclear']['min_output']
        
        coal_cap = self.non_renewable['coal']['capacity_mw']
        coal_min = self.non_renewable['coal']['min_output']
        
        gas_cap = self.non_renewable['thermal_gas']['capacity_mw']
        
        # Nuclear: base load (constant)
        nuclear = np.full(len(shortfall), nuclear_cap * 0.9)
        
        remaining = shortfall - nuclear
        remaining = np.maximum(0, remaining)
        
        # Coal: load following
        coal_min_gen = coal_cap * coal_min
        coal = np.where(
            remaining > coal_min_gen,
            np.minimum(remaining, coal_cap),
            coal_min_gen  # Keep at minimum even if not needed
        )
        
        remaining = remaining - coal
        remaining = np.maximum(0, remaining)
        
        # Gas: peak load and fast response
        gas = np.minimum(remaining, gas_cap)
        
        return {
            'nuclear': nuclear,
            'coal': coal,
            'gas': gas
        }
    
    def _calculate_marginal_cost(self, dispatch):
        """
        Calculate marginal cost based on the marginal generator.
        The marginal cost is set by the most expensive unit dispatched.
        """
        # Get marginal costs
        nuclear_cost = self.non_renewable['nuclear']['marginal_cost_per_mwh']
        coal_cost = self.non_renewable['coal']['marginal_cost_per_mwh']
        gas_cost = self.non_renewable['thermal_gas']['marginal_cost_per_mwh']
        
        coal = dispatch['coal']
        gas = dispatch['gas']
        
        coal_cap = self.non_renewable['coal']['capacity_mw']
        
        # Determine marginal generator
        marginal_cost = np.where(
            gas > 0,
            gas_cost,  # Gas is marginal
            np.where(
                coal > coal_cap * 0.7,
                coal_cost,  # Coal is marginal (above 70% utilization)
                nuclear_cost  # Nuclear is marginal
            )
        )
        
        return marginal_cost
    
    def create_supply_mix_features(self, data):
        """
        Create all supply mix related features from real-world data columns.
        """
        # Extract renewable generation columns (based on WeatherRenewableMapper outputs)
        renewable_cols = [c for c in data.columns if 'potential_mw' in c]
        renewable_gen = data[renewable_cols]
        
        # Get demand (mapped from market data)
        demand = data['demand_mw'] if 'demand_mw' in data.columns else data.get('demand', 4000)
        
        # Calculate supply mix
        supply_mix = self.calculate_supply_mix(renewable_gen, demand)
        
        # Add lag features for supply mix dynamics
        supply_mix['marginal_cost_lag_1'] = supply_mix['marginal_cost_inr_mwh'].shift(1)
        supply_mix['marginal_cost_lag_3'] = supply_mix['marginal_cost_inr_mwh'].shift(3)
        supply_mix['renewable_pen_change'] = supply_mix['renewable_penetration_pct'].diff()
        
        return supply_mix


if __name__ == "__main__":
    # Test supply mix calculator
    calculator = SupplyMixCalculator()
    
    print("Loading data...")
    data = pd.read_csv('data/processed/market_weather_energy_data.csv',
                      parse_dates=['timestamp'], index_col='timestamp')
    
    print("Calculating supply mix...")
    supply_mix = calculator.create_supply_mix_features(data)
    
    print(f"\nSupply mix features created:")
    print(list(supply_mix.columns))
    
    print(f"\nSupply mix summary:")
    print(supply_mix.describe())
    
    print(f"\nSample data:")
    print(supply_mix.head())
