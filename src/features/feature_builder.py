"""
Feature Builder
Orchestrates all feature engineering pipelines.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import os

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from features.weather_renewable_mapper import WeatherRenewableMapper
from features.supply_mix_calculator import SupplyMixCalculator
from data.preprocessor import DataPreprocessor


class FeatureBuilder:
    """Builds complete feature set for MCP forecasting."""
    
    def __init__(self, config_dir="config"):
        """Initialize feature engineering components."""
        self.weather_mapper = WeatherRenewableMapper()
        self.supply_calculator = SupplyMixCalculator()
        self.preprocessor = DataPreprocessor()
    
    def build_features(self, data, create_lags=True, create_rolling=True):
        """
        Build complete feature set from real-world data columns.
        """
        print("Starting feature engineering from real-world data...")
        
        # 1. Time features
        print("  Creating time features...")
        data = self.preprocessor.create_time_features(data)
        
        # 2. Weather-renewable mapping (Hub-based)
        print("  Mapping hub weather to renewable generation...")
        renewable_features = self.weather_mapper.create_renewable_features(data)
        
        # 3. Supply mix calculations (Merit order)
        print("  Calculating regional supply mix...")
        # Concatenate to ensure supply calculator sees renewable features
        data_with_renewables = pd.concat([data, renewable_features[[c for c in renewable_features.columns if c not in data.columns]]], axis=1)
        supply_mix_features = self.supply_calculator.create_supply_mix_features(data_with_renewables)
        
        # Combine all features
        feature_data = pd.concat([
            data_with_renewables,
            supply_mix_features
        ], axis=1)
        
        # 4. Lag features for key market variables
        if create_lags:
            print("  Creating lag features...")
            lag_columns = [
                'MCP',
                'demand_mw',
                'total_renewable_potential_mw',
                'marginal_cost_inr_mwh',
                'renewable_penetration_pct'
            ]
            lag_columns = [c for c in lag_columns if c in feature_data.columns]
            feature_data = self.preprocessor.create_lag_features(
                feature_data, lag_columns, lags=[1, 3, 6, 12, 24]
            )
        
        # 5. Rolling statistics for regional weather
        if create_rolling:
            print("  Creating rolling features...")
            rolling_columns = [
                'demand_mw',
                'total_renewable_potential_mw',
                'solar_hub_temp',
                'wind_hub_wspd'
            ]
            rolling_columns = [c for c in rolling_columns if c in feature_data.columns]
            feature_data = self.preprocessor.create_rolling_features(
                feature_data, rolling_columns, windows=[3, 6, 12, 24]
            )
        
        # 6. Interaction features
        print("  Creating interaction features...")
        feature_data = self._create_interaction_features(feature_data)
        
        print(f"Feature engineering complete! Total features: {len(feature_data.columns)}")
        
        return feature_data
    
    def _create_interaction_features(self, data):
        """Create interaction features between key variables."""
        df = data.copy()
        
        # Demand x renewable penetration
        if 'demand_mw' in df.columns and 'renewable_penetration_pct' in df.columns:
            df['demand_renewable_interaction'] = (
                df['demand_mw'] * df['renewable_penetration_pct'] / 100
            )
        
        # Peak hour x renewable penetration
        if 'is_peak_hour' in df.columns and 'renewable_penetration_pct' in df.columns:
            df['peak_renewable_interaction'] = (
                df['is_peak_hour'] * df['renewable_penetration_pct']
            )
        
        # Temperature x demand (cooling/heating)
        if 'temperature_celsius' in df.columns and 'demand_mw' in df.columns:
            df['temp_demand_interaction'] = (
                df['temperature_celsius'] * df['demand_mw'] / 1000
            )
        
        # Supply tightness x peak hour
        if 'reserve_margin_pct' in df.columns and 'is_peak_hour' in df.columns:
            df['tight_peak_interaction'] = (
                (100 - df['reserve_margin_pct']) * df['is_peak_hour']
            )
        
        return df
    
    def prepare_for_training(self, data, target_col='mcp_inr_per_mwh', 
                           drop_cols=None, handle_nan='drop'):
        """
        Prepare feature matrix and target for model training.
        
        Args:
            data: DataFrame with features
            target_col: Name of target column
            drop_cols: Additional columns to drop
            handle_nan: 'drop' or 'fill'
            
        Returns:
            X (features), y (target)
        """
        df = data.copy()
        
        # Define columns to exclude from features
        exclude_cols = [target_col, 'timestamp']
        if drop_cols:
            exclude_cols.extend(drop_cols)
        
        # Separate target
        if target_col in df.columns:
            y = df[target_col]
            X = df.drop(columns=exclude_cols, errors='ignore')
        else:
            raise ValueError(f"Target column '{target_col}' not found in data")
        
        # Handle missing values
        if handle_nan == 'drop':
            valid_idx = X.dropna().index.intersection(y.dropna().index)
            X = X.loc[valid_idx]
            y = y.loc[valid_idx]
            print(f"Dropped {len(df) - len(X)} rows with NaN values")
        elif handle_nan == 'fill':
            X = X.fillna(method='ffill').fillna(method='bfill')
            y = y.fillna(method='ffill').fillna(method='bfill')
        
        print(f"Final dataset: {len(X)} samples, {len(X.columns)} features")
        
        return X, y
    
    def get_feature_importance_groups(self):
        """Return feature groups for importance analysis."""
        return {
            'weather': ['temperature', 'solar_irradiance', 'wind_speed', 'rainfall', 'cloud_cover'],
            'time': ['hour', 'day_of_week', 'month', 'is_weekend', 'is_peak_hour'],
            'renewable': ['solar_gen', 'wind_gen', 'hydro_gen', 'biomass_gen', 'renewable_penetration'],
            'supply_mix': ['coal_dispatch', 'gas_dispatch', 'marginal_cost', 'reserve_margin'],
            'demand': ['demand_mw', 'supply_demand_ratio'],
            'lags': ['_lag_'],
            'rolling': ['_rolling_']
        }


if __name__ == "__main__":
    # Test feature builder with real data
    builder = FeatureBuilder()
    
    print("Loading preprocessed real data...")
    raw_path = 'data/processed/full_real_preprocessed.csv'
    if os.path.exists(raw_path):
        data = pd.read_csv(raw_path, parse_dates=['timestamp'], index_col='timestamp')
        
        print(f"Loaded data shape: {data.shape}")
        
        print("\nBuilding real-world features...")
        features = builder.build_features(data)
        
        print(f"\nEngineered features shape: {features.shape}")
        
        print("\nPreparing for training (Target: MCP)...")
        X, y = builder.prepare_for_training(features, target_col='MCP')
        
        # Save engineered features
        output_path = 'data/processed/real_engineered_features.csv'
        features.to_csv(output_path)
        print(f"\nSaved real engineered features to: {output_path}")
    else:
        print(f"Error: File not found {raw_path}")
