"""
Data Preprocessor Module
Handles data cleaning, validation, and transformation.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
import os


class DataPreprocessor:
    """Preprocesses raw data for model training."""
    
    def __init__(self, schema_dir="data/schemas"):
        """Initialize with data schemas."""
        self.schema_dir = Path(schema_dir)
        
    def load_and_validate(self, filepath):
        """Load data and perform basic validation."""
        data = pd.read_csv(filepath, parse_dates=['timestamp'], index_col='timestamp')
        
        print(f"Loaded {len(data)} records from {filepath}")
        print(f"Date range: {data.index.min()} to {data.index.max()}")
        
        # Check for missing values
        missing = data.isnull().sum()
        if missing.any():
            print(f"\nMissing values found:")
            print(missing[missing > 0])
        
        # Check for duplicates
        duplicates = data.index.duplicated().sum()
        if duplicates > 0:
            print(f"\nRemoving {duplicates} duplicate timestamps")
            data = data[~data.index.duplicated(keep='first')]
        
        return data

    def load_and_validate_real_data(self, market_path, weather_path):
        """Load and merge real-world market and weather data at 15-min granularity."""
        # 1. Load Market Data
        market = pd.read_csv(market_path)
        print(f"Loaded {len(market)} market records")
        
        # Parse IEX Date and Block (1-96) into single timestamp
        # Each block is 15 minutes. Block 1 = 00:00, Block 2 = 00:15...
        market['timestamp'] = pd.to_datetime(market['Date'], format='%d-%m-%Y') + \
                             pd.to_timedelta((market['Block'] - 1) * 15, unit='m')
        market = market.set_index('timestamp').drop(['Date', 'Block'], axis=1)
        
        # 2. Load Weather Data (Hourly)
        weather = pd.read_csv(weather_path)
        print(f"Loaded {len(weather)} hourly weather records")
        weather['timestamp'] = pd.to_datetime(weather['time'])
        weather = weather.set_index('timestamp').drop(['time'], axis=1)
        
        # 3. Upsample Weather to 15-min
        print("Upsampling weather data to 15-minute blocks...")
        weather = weather.resample('15min').interpolate(method='time')
        
        # 4. Merge
        data = pd.concat([market, weather], axis=1, join='inner')
        print(f"Merged data: {len(data)} records across {len(data.columns)} columns")
        
        return data
    
    def handle_missing_values(self, data, method='interpolate'):
        """Handle missing values in the dataset."""
        if method == 'interpolate':
            data = data.interpolate(method='time', limit_direction='both')
        elif method == 'forward_fill':
            data = data.fillna(method='ffill').fillna(method='bfill')
        elif method == 'drop':
            data = data.dropna()
        
        return data
    
    def detect_and_handle_outliers(self, data, columns=None, method='clip', threshold=3):
        """
        Detect and handle outliers using z-score or IQR method.
        
        Args:
            data: DataFrame
            columns: List of columns to check (None = all numeric columns)
            method: 'clip', 'remove', or 'cap'
            threshold: Z-score threshold (default 3)
        """
        if columns is None:
            columns = data.select_dtypes(include=[np.number]).columns
        
        data_clean = data.copy()
        outlier_counts = {}
        
        for col in columns:
            # Z-score method
            z_scores = np.abs((data[col] - data[col].mean()) / data[col].std())
            outliers = z_scores > threshold
            outlier_counts[col] = outliers.sum()
            
            if outliers.any():
                if method == 'clip':
                    # Clip to mean ± threshold * std
                    lower = data[col].mean() - threshold * data[col].std()
                    upper = data[col].mean() + threshold * data[col].std()
                    data_clean[col] = data[col].clip(lower, upper)
                elif method == 'remove':
                    data_clean = data_clean[~outliers]
        
        print(f"\nOutlier detection (z-score > {threshold}):")
        for col, count in outlier_counts.items():
            if count > 0:
                print(f"  {col}: {count} outliers")
        
        return data_clean
    
    def create_time_features(self, data):
        """Create time-based features from timestamp index."""
        data = data.copy()
        
        data['hour'] = data.index.hour
        data['day_of_week'] = data.index.dayofweek
        data['day_of_month'] = data.index.day
        data['month'] = data.index.month
        data['quarter'] = data.index.quarter
        data['year'] = data.index.year
        data['is_weekend'] = (data.index.dayofweek >= 5).astype(int)
        data['is_peak_hour'] = ((data.index.hour >= 18) & (data.index.hour <= 22)).astype(int)
        
        # Cyclical encoding for periodic features
        data['hour_sin'] = np.sin(2 * np.pi * data['hour'] / 24)
        data['hour_cos'] = np.cos(2 * np.pi * data['hour'] / 24)
        data['day_sin'] = np.sin(2 * np.pi * data['day_of_week'] / 7)
        data['day_cos'] = np.cos(2 * np.pi * data['day_of_week'] / 7)
        data['month_sin'] = np.sin(2 * np.pi * data['month'] / 12)
        data['month_cos'] = np.cos(2 * np.pi * data['month'] / 12)
        
        return data
    
    def create_lag_features(self, data, columns, lags=[1, 3, 6, 12, 24]):
        """Create lagged features for time series."""
        data = data.copy()
        
        for col in columns:
            for lag in lags:
                data[f'{col}_lag_{lag}'] = data[col].shift(lag)
        
        return data
    
    def create_rolling_features(self, data, columns, windows=[3, 6, 12, 24]):
        """Create rolling statistics features."""
        data = data.copy()
        
        for col in columns:
            for window in windows:
                data[f'{col}_rolling_mean_{window}'] = data[col].rolling(window).mean()
                data[f'{col}_rolling_std_{window}'] = data[col].rolling(window).std()
                data[f'{col}_rolling_min_{window}'] = data[col].rolling(window).min()
                data[f'{col}_rolling_max_{window}'] = data[col].rolling(window).max()
        
        return data
    
    def normalize_features(self, data, exclude_cols=None, method='standard'):
        """
        Normalize features.
        
        Args:
            data: DataFrame
            exclude_cols: Columns to exclude from normalization
            method: 'standard' (z-score) or 'minmax'
        """
        data = data.copy()
        
        if exclude_cols is None:
            exclude_cols = []
        
        numeric_cols = data.select_dtypes(include=[np.number]).columns
        cols_to_normalize = [c for c in numeric_cols if c not in exclude_cols]
        
        if method == 'standard':
            for col in cols_to_normalize:
                mean = data[col].mean()
                std = data[col].std()
                data[f'{col}_normalized'] = (data[col] - mean) / std
        elif method == 'minmax':
            for col in cols_to_normalize:
                min_val = data[col].min()
                max_val = data[col].max()
                data[f'{col}_normalized'] = (data[col] - min_val) / (max_val - min_val)
        
        return data
    
    def split_train_val_test(self, data, train_ratio=0.7, val_ratio=0.15):
        """
        Split data into train, validation, and test sets.
        Preserves temporal order for time series.
        """
        n = len(data)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))
        
        train = data.iloc[:train_end]
        val = data.iloc[train_end:val_end]
        test = data.iloc[val_end:]
        
        print(f"\nData split:")
        print(f"  Train: {len(train)} samples ({train.index.min()} to {train.index.max()})")
        print(f"  Val:   {len(val)} samples ({val.index.min()} to {val.index.max()})")
        print(f"  Test:  {len(test)} samples ({test.index.min()} to {test.index.max()})")
        
        return train, val, test
    
    def save_processed_data(self, data, filepath):
        """Save processed data."""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        data.to_csv(filepath)
        print(f"Processed data saved to {filepath}")


if __name__ == "__main__":
    # Example preprocessing pipeline with real data
    preprocessor = DataPreprocessor()
    
    # Update these paths based on the local list_dir output
    market_path = 'data/raw/market_real_20260213_1233.csv'
    weather_path = 'data/raw/weather_real_20260213_1233.csv'
    
    print("Loading and merging real data...")
    if os.path.exists(market_path) and os.path.exists(weather_path):
        data = preprocessor.load_and_validate_real_data(market_path, weather_path)
        
        print("\nHandling missing values...")
        data = preprocessor.handle_missing_values(data)
        
        print("\nDetecting outliers...")
        data = preprocessor.detect_and_handle_outliers(data, threshold=4)
        
        print("\nCreating time features...")
        data = preprocessor.create_time_features(data)
        
        print("\nSplitting data...")
        train, val, test = preprocessor.split_train_val_test(data)
        
        # Save splits
        preprocessor.save_processed_data(train, 'data/processed/train_real.csv')
        preprocessor.save_processed_data(val, 'data/processed/val_real.csv')
        preprocessor.save_processed_data(test, 'data/processed/test_real.csv')
        preprocessor.save_processed_data(data, 'data/processed/full_real_preprocessed.csv')
        
        print("\nPreprocessing complete!")
    else:
        print(f"Error: Raw data files not found at {market_path} or {weather_path}")
