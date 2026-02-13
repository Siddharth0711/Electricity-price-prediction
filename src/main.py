"""
Main Pipeline
End-to-end orchestration for MCP forecasting and trading insights.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import argparse
import sys
import joblib
from datetime import datetime, timedelta

sys.path.append(str(Path(__file__).parent))

from data.data_collector import DataCollector
from data.preprocessor import DataPreprocessor
from features.feature_builder import FeatureBuilder
from models.model_trainer import MCPModelTrainer
from trading.forecast_to_insights import TradingInsightsGenerator


class MCPForecastingPipeline:
    """End-to-end pipeline for MCP forecasting and trading insights."""
    
    def __init__(self):
        """Initialize pipeline components."""
        self.data_collector = DataCollector()
        self.preprocessor = DataPreprocessor()
        self.feature_builder = FeatureBuilder()
        self.trainer = MCPModelTrainer()
        self.insights_generator = TradingInsightsGenerator()
        
        self.model = None
        self.feature_columns = None
    
    def run_data_collection(self, start_date, end_date, output_file='data/processed/market_weather_energy_data.csv'):
        """Step 1: Collect/generate data."""
        print("\n" + "="*60)
        print("STEP 1: DATA COLLECTION")
        print("="*60)
        
        data = self.data_collector.generate_synthetic_data(start_date, end_date, freq='H')
        self.data_collector.save_data(data, output_file)
        
        return data
    
    def run_preprocessing(self, input_file='data/processed/market_weather_energy_data.csv'):
        """Step 2: Preprocess data."""
        print("\n" + "="*60)
        print("STEP 2: DATA PREPROCESSING")
        print("="*60)
        
        data = self.preprocessor.load_and_validate(input_file)
        data = self.preprocessor.handle_missing_values(data)
        data = self.preprocessor.detect_and_handle_outliers(data, threshold=4)
        
        return data
    
    def run_feature_engineering(self, data):
        """Step 3: Build features."""
        print("\n" + "="*60)
        print("STEP 3: FEATURE ENGINEERING")
        print("="*60)
        
        features = self.feature_builder.build_features(data)
        X, y = self.feature_builder.prepare_for_training(features)
        
        return X, y
    
    def run_model_training(self, X, y, save_best=True):
        """Step 4: Train models."""
        print("\n" + "="*60)
        print("STEP 4: MODEL TRAINING")
        print("="*60)
        
        # Split data
        train_size = int(len(X) * 0.7)
        val_size = int(len(X) * 0.15)
        
        X_train = X.iloc[:train_size]
        y_train = y.iloc[:train_size]
        X_val = X.iloc[train_size:train_size + val_size]
        y_val = y.iloc[train_size:train_size + val_size]
        X_test = X.iloc[train_size + val_size:]
        y_test = y.iloc[train_size + val_size:]
        
        # Train models
        self.trainer.train_baseline_models(X_train, y_train, X_val, y_val)
        self.trainer.train_advanced_models(X_train, y_train, X_val, y_val)
        
        # Get best model
        best_name, best_model = self.trainer.get_best_model()
        print(f"\nBest Model: {best_name}")
        
        # Test evaluation
        test_results = self.trainer._evaluate_model(best_model, X_test, y_test)
        print(f"\nTest Set Performance:")
        for metric, value in test_results.items():
            print(f"  {metric}: {value:.4f}")
        
        # Save model
        if save_best:
            self.trainer.save_model(best_name, best_model, f'models/{best_name}_best.pkl')
            self.trainer.save_results('outputs/model_results.csv')
        
        self.model = best_model
        self.feature_columns = X.columns
        
        return best_model, test_results
    
    def run_forecasting(self, horizon=24, model_path=None):
        """Step 5: Generate forecasts."""
        print("\n" + "="*60)
        print(f"STEP 5: FORECASTING (Horizon: {horizon} hours)")
        print("="*60)
        
        # Load model if path provided
        if model_path and self.model is None:
            self.model = joblib.load(model_path)
            print(f"Loaded model from {model_path}")
        
        if self.model is None:
            raise ValueError("No model available. Train a model first or provide model_path.")
        
        # Load latest data
        data = pd.read_csv('data/processed/market_weather_energy_data.csv',
                          parse_dates=['timestamp'], index_col='timestamp')
        
        # Build features
        features = self.feature_builder.build_features(data)
        X, y = self.feature_builder.prepare_for_training(features)
        
        # Get last 'horizon' hours for forecasting
        X_forecast = X.iloc[-horizon:]
        y_actual = y.iloc[-horizon:]
        
        # Generate forecasts
        forecasts = self.model.predict(X_forecast)
        
        forecast_df = pd.DataFrame({
            'timestamp': X_forecast.index,
            'forecast_mcp': forecasts,
            'actual_mcp': y_actual.values
        }).set_index('timestamp')
        
        # Save forecasts
        forecast_df.to_csv('outputs/mcp_forecasts.csv')
        print(f"\nForecasts saved to outputs/mcp_forecasts.csv")
        
        return forecast_df
    
    def run_trading_insights(self, forecast_df):
        """Step 6: Generate trading insights."""
        print("\n" + "="*60)
        print("STEP 6: TRADING INSIGHTS")
        print("="*60)
        
        # Generate signals
        signals = self.insights_generator.generate_trading_signals(
            forecast_df['forecast_mcp'],
            forecast_df['actual_mcp']
        )
        
        # Generate bidding recommendations
        recommendations = self.insights_generator.generate_bidding_recommendations(
            forecast_df['forecast_mcp']
        )
        
        # Create report
        report = self.insights_generator.create_trading_report(signals, recommendations)
        
        # Save outputs
        signals.to_csv('outputs/trading_signals.csv')
        recommendations.to_csv('outputs/bidding_recommendations.csv')
        
        with open('outputs/trading_report.txt', 'w') as f:
            f.write(report)
        
        print(report)
        
        return signals, recommendations
    
    def run_full_pipeline(self, start_date='2023-01-01', end_date='2024-12-31', forecast_horizon=24):
        """Run the complete end-to-end pipeline."""
        print("\n" + "="*80)
        print(" "*20 + "MCP FORECASTING PIPELINE")
        print("="*80)
        
        # Step 1: Data Collection
        data = self.run_data_collection(start_date, end_date)
        
        # Step 2: Preprocessing
        data = self.run_preprocessing()
        
        # Step 3: Feature Engineering
        X, y = self.run_feature_engineering(data)
        
        # Step 4: Model Training
        model, results = self.run_model_training(X, y)
        
        # Step 5: Forecasting
        forecasts = self.run_forecasting(horizon=forecast_horizon)
        
        # Step 6: Trading Insights
        signals, recommendations = self.run_trading_insights(forecasts)
        
        print("\n" + "="*80)
        print(" "*20 + "PIPELINE COMPLETE!")
        print("="*80)
        print("\nOutputs saved to:")
        print("  - models/")
        print("  - outputs/")
        
        return {
            'model': model,
            'forecasts': forecasts,
            'signals': signals,
            'recommendations': recommendations
        }


def main():
    """Main entry point with CLI."""
    parser = argparse.ArgumentParser(description='MCP Forecasting Pipeline')
    parser.add_argument('--mode', type=str, default='full',
                       choices=['full', 'data', 'train', 'forecast', 'insights'],
                       help='Pipeline mode to run')
    parser.add_argument('--start-date', type=str, default='2023-01-01',
                       help='Start date for data collection (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default='2024-12-31',
                       help='End date for data collection (YYYY-MM-DD)')
    parser.add_argument('--horizon', type=int, default=24,
                       help='Forecast horizon in hours')
    parser.add_argument('--model-path', type=str, default=None,
                       help='Path to pre-trained model')
    
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = MCPForecastingPipeline()
    
    # Run based on mode
    if args.mode == 'full':
        pipeline.run_full_pipeline(args.start_date, args.end_date, args.horizon)
    
    elif args.mode == 'data':
        pipeline.run_data_collection(args.start_date, args.end_date)
    
    elif args.mode == 'train':
        data = pipeline.run_preprocessing()
        X, y = pipeline.run_feature_engineering(data)
        pipeline.run_model_training(X, y)
    
    elif args.mode == 'forecast':
        forecasts = pipeline.run_forecasting(horizon=args.horizon, model_path=args.model_path)
        print(f"\nGenerated {len(forecasts)} forecasts")
    
    elif args.mode == 'insights':
        # Load forecasts and generate insights
        forecasts = pd.read_csv('outputs/mcp_forecasts.csv', 
                               parse_dates=['timestamp'], index_col='timestamp')
        pipeline.run_trading_insights(forecasts)


if __name__ == "__main__":
    main()
