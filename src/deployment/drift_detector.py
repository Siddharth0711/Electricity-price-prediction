import pandas as pd
import numpy as np
from scipy.stats import ks_2samp
import json
from pathlib import Path

def detect_drift(reference_data_path, current_data_path, threshold=0.05):
    """
    Detect data drift using the Kolmogorov-Smirnov test.
    Compare distributions of key features between training and production data.
    """
    print(f"Monitoring Model Drift: Comparing {current_data_path} vs {reference_data_path}...")
    
    ref_df = pd.read_csv(reference_data_path)
    cur_df = pd.read_csv(current_data_path)
    
    drift_results = {}
    features_to_monitor = ['MCP', 'demand_mw', 'wind_hub_wspd', 'solar_hub_temp']
    
    for feature in features_to_monitor:
        if feature in ref_df.columns and feature in cur_df.columns:
            # KS Test
            statistic, p_value = ks_2samp(ref_df[feature].dropna(), cur_df[feature].dropna())
            drift_detected = p_value < threshold
            
            drift_results[feature] = {
                "statistic": float(statistic),
                "p_value": float(p_value),
                "drift_detected": bool(drift_detected)
            }
            
            status = "⚠️ DRIFT DETECTED" if drift_detected else "✅ STABLE"
            print(f"  {feature}: {status} (p={p_value:.4f})")

    # Save results
    output_path = Path("outputs/drift_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(drift_results, f, indent=4)
        
    return drift_results

if __name__ == "__main__":
    # Example usage: Compare full dataset vs latest test set
    ref_path = "data/processed/full_real_preprocessed.csv"
    cur_path = "data/processed/test_real.csv"
    
    if Path(ref_path).exists() and Path(cur_path).exists():
        results = detect_drift(ref_path, cur_path)
    else:
        print("Error: Data files for drift detection not found.")
