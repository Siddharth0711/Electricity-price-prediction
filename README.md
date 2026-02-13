# Weather-Driven Electricity Price Forecasting

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 🎯 Project Objective

Design an end-to-end analytics solution to forecast **Market Clearing Prices (MCP)** using weather-driven machine learning models and translate forecasts into actionable trading insights.

## 🌟 Key Features

- **Multi-Source Energy Modeling**: Accounts for renewable (solar, hydro, wind, biomass) and non-renewable (coal, thermal, gas) sources
- **Weather-Driven Forecasting**: Captures how weather impacts renewable generation → supply mix → MCP
- **Supply-Demand Dynamics**: Models the interaction between weather-driven supply and demand patterns
- **Trading Insights Engine**: Translates price forecasts into bidding strategies, hedging recommendations, and portfolio optimization

## 📊 Architecture

```
Weather Data → Renewable Generation → Supply Mix → Marginal Cost → MCP Forecast → Trading Signals
              ↓                        ↓
         Demand Forecast         Non-Renewable Generation
```

## 🚀 Quick Start

### Installation

```bash
# Clone or navigate to project directory
cd "FRESH START"

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run End-to-End Pipeline

```bash
# 1. Generate synthetic data
python src/data/data_collector.py

# 2. Train models
python src/models/model_trainer.py

# 3. Generate forecasts
python src/main.py --mode forecast --horizon 24

# 4. View trading insights
python src/visualization/dashboards.py
```

## 📁 Project Structure

```
FRESH START/
├── config/                    # Configuration files
│   ├── data_sources.yaml      # Energy sources & weather features
│   ├── model_config.yaml      # Model hyperparameters
│   └── trading_config.yaml    # Trading strategy parameters
├── data/
│   ├── raw/                   # Raw data files
│   ├── processed/             # Cleaned datasets
│   └── schemas/               # Data schemas (JSON)
├── src/
│   ├── data/                  # Data collection & preprocessing
│   ├── features/              # Feature engineering modules
│   ├── models/                # ML models (baseline & advanced)
│   ├── trading/               # Trading insights & backtesting
│   └── visualization/         # Dashboards & reports
├── notebooks/                 # Jupyter notebooks for EDA
├── tests/                     # Unit & integration tests
├── outputs/                   # Forecast reports & visualizations
└── models/                    # Saved model artifacts
```

## 🔧 Modules

### Data Pipeline
- **data_collector.py**: Ingests weather, energy, and market data
- **preprocessor.py**: Cleans and validates data

### Feature Engineering
- **weather_renewable_mapper.py**: Maps weather to renewable generation
- **supply_mix_calculator.py**: Computes renewable vs non-renewable mix
- **demand_forecaster.py**: Forecasts electricity demand

### ML Models
- **baseline_models.py**: Linear regression, ARIMA
- **advanced_models.py**: XGBoost, LightGBM, LSTM

### Trading Insights
- **forecast_to_insights.py**: Converts forecasts to trading signals
- **bidding_strategy.py**: Optimal bid price calculation
- **portfolio_optimizer.py**: Multi-period optimization

## 📈 Model Performance Targets

- **RMSE**: < 10% of mean MCP
- **Directional Accuracy**: > 70%
- **Sharpe Ratio**: > 1.0 (backtesting)

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Run specific test suite
pytest tests/unit/test_models.py
pytest tests/integration/test_end_to_end_pipeline.py
```

## 📊 Visualization

Launch the interactive dashboard to explore forecasts and trading insights:

```bash
python src/visualization/dashboards.py
# Open browser at http://localhost:8050
```

## 🤝 Contributing

This project follows the CRISP-ML(Q) methodology for ML lifecycle management.

## 📄 License

MIT License - see LICENSE file for details

---

**Built with ❤️ for energy trading analytics**
