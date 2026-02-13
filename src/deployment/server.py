from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

app = FastAPI(title="MCP Forecasting API", version="1.0.0")

class ForecastRequest(BaseModel):
    # Minimal features for demo, in production this would be the full engineered vector
    demand_mw: float
    solar_potential_mw: float
    wind_potential_mw: float
    hour: int
    is_peak_hour: int

# Global model variable
model = None

@app.on_event("startup")
def load_model():
    global model
    model_path = Path("models/linear_regression_best.pkl")
    if model_path.exists():
        model = joblib.load(model_path)
        print(f"Model loaded from {model_path}")
    else:
        print(f"Warning: Model not found at {model_path}")

@app.get("/")
def read_root():
    return {"message": "MCP Forecasting API is active"}

@app.post("/predict")
def predict(request: ForecastRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    # Simple prediction demo
    # In production, we'd use the FeatureBuilder to ensure all 146 features are present
    # Here we mock the input vector for demonstration
    input_data = np.zeros((1, 146)) 
    
    # Mock some basic feature columns (index mapping would be precise in production)
    # This is a placeholder to show API functionality
    prediction = model.predict(input_data)[0]
    
    return {
        "mcp_forecast": float(prediction),
        "unit": "INR/MWh",
        "timestamp": pd.Timestamp.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
