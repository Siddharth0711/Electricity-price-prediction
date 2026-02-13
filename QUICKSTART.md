# Quick Start Guide

## Weather-Driven MCP Forecasting System

### Prerequisites
- Python 3.9 or higher
- Virtual environment (recommended)

### Installation

```bash
# Navigate to FRESH START directory
cd "FRESH START"

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Complete Pipeline

The easiest way to get started is to run the full end-to-end pipeline:

```bash
# Run from FRESH START directory
python src/main.py --mode full
```

This will:
1. ✅ Generate 2 years of synthetic data (weather, energy, demand, MCP)
2. ✅ Preprocess and clean the data
3. ✅ Engineer features (weather→renewable mapping, supply mix, etc.)
4. ✅ Train multiple ML models (XGBoost, LightGBM, CatBoost, Random Forest)
5. ✅ Generate 24-hour MCP forecasts
6. ✅ Create trading insights (buy/sell signals, bidding recommendations)

**Expected output locations:**
- `data/processed/market_weather_energy_data.csv` - Synthetic dataset
- `models/*.pkl` - Trained models
- `outputs/mcp_forecasts.csv` - Price forecasts
- `outputs/trading_signals.csv` - Buy/sell signals
- `outputs/bidding_recommendations.csv` - Bidding strategies
- `outputs/trading_report.txt` - Comprehensive trading report

### Running Individual Stages

#### 1. Data Collection Only
```bash
python src/main.py --mode data --start-date 2023-01-01 --end-date 2024-12-31
```

#### 2. Model Training Only
```bash
python src/main.py --mode train
```

#### 3. Forecasting Only (requires trained model)
```bash
python src/main.py --mode forecast --horizon 24
```

#### 4. Trading Insights Only (requires forecasts)
```bash
python src/main.py --mode insights
```

### Understanding the Data Pipeline

#### Weather Features → Renewable Generation
The system models how weather affects renewable energy:

- **Solar**: `irradiance × efficiency × temperature_coefficient × cloud_factor`
- **Wind**: Power curve based on cut-in (3.5 m/s), rated (12 m/s), cut-out (25 m/s)
- **Hydro**: Base load + rainfall accumulation boost

#### Supply Mix → Marginal Cost
Merit order dispatch determines which generators run:

1. **Renewable** (lowest cost, weather-dependent)
2. **Nuclear** (base load, ~90% capacity)
3. **Coal** (load following, 40-100% capacity)
4. **Gas** (peak load, most expensive)

**MCP is set by the marginal generator** (most expensive unit needed)

#### Forecasting → Trading Insights

**Signal Generation:**
- **BUY**: Forecast < Current - 5%
- **SELL**: Forecast > Current + 5%
- **HOLD**: Otherwise

**Position Sizing:**
- Strong signal (>5% diff): 100% of max position
- Medium signal (2-5%): 60% of max position
- Weak signal (<2%): 30% of max position

### Configuration

All parameters can be customized in `config/` directory:

- **data_sources.yaml**: Energy capacities, weather ranges, market parameters
- **model_config.yaml**: ML hyperparameters, feature engineering settings
- **trading_config.yaml**: Bidding strategies, risk limits, portfolio constraints

### Example: Custom Forecast Horizon

```bash
# Generate 48-hour forecast
python src/main.py --mode forecast --horizon 48
```

### Example: Aggressive Trading Strategy

Edit `config/trading_config.yaml`:
```yaml
bidding:
  strategy: aggressive  # Change from 'risk_adjusted'
```

Then run:
```bash
python src/main.py --mode insights
```

### Key Metrics to Track

**Model Performance:**
- RMSE < 10% of mean MCP ✅
- Directional Accuracy > 70% ✅
- R² > 0.80 ✅

**Trading Performance:**
- Sharpe Ratio > 1.5 🎯
- Win Rate > 60% 🎯
- Max Drawdown < 15% 🎯

### Troubleshooting

**ImportError: No module named 'src'**
```bash
# Make sure you're in the "FRESH START" directory
cd "FRESH START"
python src/main.py --mode full
```

**FileNotFoundError: data/processed/.csv not found**
```bash
# Run data collection first
python src/main.py --mode data
```

**Model not found error during forecast**
```bash
# Train a model first
python src/main.py --mode train
# Then forecast
python src/main.py --mode forecast
```

### Next Steps

1. **Explore the data**: Check `data/processed/market_weather_energy_data.csv`
2. **Review model performance**: Check `outputs/model_results.csv`
3. **Analyze trading insights**: Open `outputs/trading_report.txt`
4. **Customize configurations**: Modify files in `config/` directory
5. **Integrate real data**: Replace synthetic data collector with API calls

### Support

For questions or issues:
1. Check `README.md` for detailed architecture
2. Review implementation plan in `implementation_plan.md`
3. Inspect individual module docstrings in `src/`

---

**Built with ❤️ for energy trading analytics**
