"""
Model Trainer
Trains and evaluates MCP forecasting models.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import joblib
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import xgboost as xgb
import lightgbm as lgb
from catboost import CatBoostRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
import sys
import os

sys.path.append(str(Path(__file__).parent.parent))
from features.feature_builder import FeatureBuilder


class MCPModelTrainer:
    """Trains MCP forecasting models."""
    
    def __init__(self, config_path="config/model_config.yaml"):
        """Initialize trainer with configuration."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.models = {}
        self.results = {}
        
    def train_baseline_models(self, X_train, y_train, X_val, y_val):
        """Train baseline models for comparison."""
        print("\n=== Training Baseline Models ===")
        
        # Linear Regression
        print("Training Linear Regression...")
        lr = LinearRegression()
        lr.fit(X_train, y_train)
        self.models['linear_regression'] = lr
        self.results['linear_regression'] = self._evaluate_model(lr, X_val, y_val)
        
        print(f"  Linear Regression - RMSE: {self.results['linear_regression']['rmse']:.2f}")
        
    def train_advanced_models(self, X_train, y_train, X_val, y_val):
        """Train advanced ML models."""
        print("\n=== Training Advanced Models ===")
        
        # XGBoost
        print("Training XGBoost...")
        xgb_config = self.config['advanced_models']['xgboost']
        xgb_model = xgb.XGBRegressor(
            n_estimators=xgb_config['n_estimators'],
            max_depth=xgb_config['max_depth'],
            learning_rate=xgb_config['learning_rate'],
            subsample=xgb_config['subsample'],
            colsample_bytree=xgb_config['colsample_bytree'],
            gamma=xgb_config['gamma'],
            random_state=42
        )
        xgb_model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        self.models['xgboost'] = xgb_model
        self.results['xgboost'] = self._evaluate_model(xgb_model, X_val, y_val)
        print(f"  XGBoost - RMSE: {self.results['xgboost']['rmse']:.2f}")
        
        # LightGBM
        print("Training LightGBM...")
        lgb_config = self.config['advanced_models']['lightgbm']
        lgb_model = lgb.LGBMRegressor(
            n_estimators=lgb_config['n_estimators'],
            max_depth=lgb_config['max_depth'],
            learning_rate=lgb_config['learning_rate'],
            num_leaves=lgb_config['num_leaves'],
            subsample=lgb_config['subsample'],
            colsample_bytree=lgb_config['colsample_bytree'],
            random_state=42,
            verbose=-1
        )
        lgb_model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(lgb_config['early_stopping_rounds'], verbose=False)]
        )
        self.models['lightgbm'] = lgb_model
        self.results['lightgbm'] = self._evaluate_model(lgb_model, X_val, y_val)
        print(f"  LightGBM - RMSE: {self.results['lightgbm']['rmse']:.2f}")
        
        # CatBoost
        print("Training CatBoost...")
        cat_config = self.config['advanced_models']['catboost']
        cat_model = CatBoostRegressor(
            iterations=cat_config['iterations'],
            depth=cat_config['depth'],
            learning_rate=cat_config['learning_rate'],
            l2_leaf_reg=cat_config['l2_leaf_reg'],
            random_state=42,
            verbose=False
        )
        cat_model.fit(
            X_train, y_train,
            eval_set=(X_val, y_val),
            early_stopping_rounds=cat_config['early_stopping_rounds'],
            verbose=False
        )
        self.models['catboost'] = cat_model
        self.results['catboost'] = self._evaluate_model(cat_model, X_val, y_val)
        print(f"  CatBoost - RMSE: {self.results['catboost']['rmse']:.2f}")
        
        # Random Forest
        print("Training Random Forest...")
        rf_config = self.config['advanced_models']['random_forest']
        rf_model = RandomForestRegressor(
            n_estimators=rf_config['n_estimators'],
            max_depth=rf_config['max_depth'],
            min_samples_split=rf_config['min_samples_split'],
            max_features=rf_config['max_features'],
            random_state=42,
            n_jobs=-1
        )
        rf_model.fit(X_train, y_train)
        self.models['random_forest'] = rf_model
        self.results['random_forest'] = self._evaluate_model(rf_model, X_val, y_val)
        print(f"  Random Forest - RMSE: {self.results['random_forest']['rmse']:.2f}")
        
    def _evaluate_model(self, model, X, y):
        """Evaluate model performance."""
        y_pred = model.predict(X)
        
        rmse = np.sqrt(mean_squared_error(y, y_pred))
        mae = mean_absolute_error(y, y_pred)
        r2 = r2_score(y, y_pred)
        mape = np.mean(np.abs((y - y_pred) / y)) * 100
        
        # Directional accuracy
        y_diff = y.diff()
        pred_diff = pd.Series(y_pred, index=y.index).diff()
        directional_acc = ((y_diff > 0) == (pred_diff > 0)).sum() / len(y_diff.dropna())
        
        return {
            'rmse': rmse,
            'mae': mae,
            'r2': r2,
            'mape': mape,
            'directional_accuracy': directional_acc
        }
    
    def get_best_model(self):
        """Get the best performing model based on RMSE."""
        if not self.results:
            raise ValueError("No models have been trained yet")
        
        best_model_name = min(self.results, key=lambda k: self.results[k]['rmse'])
        return best_model_name, self.models[best_model_name]
    
    def save_model(self, model_name, model, filepath):
        """Save trained model."""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, filepath)
        print(f"Model saved to {filepath}")
    
    def save_results(self, filepath):
        """Save training results."""
        results_df = pd.DataFrame(self.results).T
        results_df.to_csv(filepath)
        print(f"Results saved to {filepath}")
    
    def get_feature_importance(self, model_name, feature_names, top_n=20):
        """Get feature importance for tree-based models."""
        model = self.models.get(model_name)
        if model is None:
            raise ValueError(f"Model '{model_name}' not found")
        
        if hasattr(model, 'feature_importances_'):
            importance = model.feature_importances_
            importance_df = pd.DataFrame({
                'feature': feature_names,
                'importance': importance
            }).sort_values('importance', ascending=False)
            
            return importance_df.head(top_n)
        else:
            print(f"Model '{model_name}' does not have feature importances")
            return None


if __name__ == "__main__":
    # Load engineered features from real-world data
    print("Loading engineered features...")
    data_path = 'data/processed/real_engineered_features.csv'
    if os.path.exists(data_path):
        data = pd.read_csv(data_path, parse_dates=['timestamp'], index_col='timestamp')
        
        # Build features (using pre-engineered columns)
        builder = FeatureBuilder()
        X, y = builder.prepare_for_training(data, target_col='MCP')
        
        # Split data
        train_size = int(len(X) * 0.7)
        val_size = int(len(X) * 0.15)
        
        X_train = X.iloc[:train_size]
        y_train = y.iloc[:train_size]
        X_val = X.iloc[train_size:train_size + val_size]
        y_val = y.iloc[train_size:train_size + val_size]
        X_test = X.iloc[train_size + val_size:]
        y_test = y.iloc[train_size + val_size:]
    
    print(f"\nData splits:")
    print(f"  Train: {len(X_train)} samples")
    print(f"  Val:   {len(X_val)} samples")
    print(f"  Test:  {len(X_test)} samples")
    
    # Train models
    trainer = MCPModelTrainer()
    trainer.train_baseline_models(X_train, y_train, X_val, y_val)
    trainer.train_advanced_models(X_train, y_train, X_val, y_val)
    
    # Get best model
    best_name, best_model = trainer.get_best_model()
    print(f"\n=== Best Model: {best_name} ===")
    print(f"Validation Metrics:")
    for metric, value in trainer.results[best_name].items():
        print(f"  {metric}: {value:.4f}")
    
    # Test set evaluation
    print(f"\nTest Set Evaluation:")
    test_results = trainer._evaluate_model(best_model, X_test, y_test)
    for metric, value in test_results.items():
        print(f"  {metric}: {value:.4f}")
    
    # Feature importance
    print(f"\nTop 20 Important Features:")
    importance = trainer.get_feature_importance(best_name, X.columns, top_n=20)
    if importance is not None:
        print(importance.to_string(index=False))
    
    # Save models and results
    trainer.save_model(best_name, best_model, f'models/{best_name}_best.pkl')
    trainer.save_results('outputs/model_results.csv')
    
    print("\n=== Training Complete ===")
