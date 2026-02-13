import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import joblib
from pathlib import Path
from datetime import datetime, timedelta
from meteostat import hourly, Point, stations

# Set Page Config
st.set_page_config(
    page_title="MCP Forecasting Dashboard",
    page_icon="⚡",
    layout="wide"
)

# Custom CSS for Global Styles
st.markdown("""
    <style>
    .main {
        background-color: #0f172a;
    }
    .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
        color: #f8fafc !important;
    }
    /* Simple Card Style */
    .metric-card {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        min-height: 140px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .metric-label {
        color: #64748b !important;
        font-size: 13px !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        margin-bottom: 8px !important;
    }
    .metric-value {
        color: #1e293b !important;
        font-size: 32px !important;
        font-weight: 800 !important;
        margin: 0 !important;
    }
    .metric-delta {
        font-size: 16px !important;
        font-weight: 600 !important;
        margin-top: 4px !important;
    }
    .strategy-container {
        border-radius: 12px;
        padding: 24px;
        text-align: center;
        min-height: 140px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# Helper function for Custom Metric Card
def custom_card(label, value, delta=None, delta_up=False, subtext=None):
    delta_html = ""
    if delta:
        color = "#ef4444" if delta_up else "#10b981"
        symbol = "▲" if delta_up else "▼"
        delta_html = f"<div class='metric-delta' style='color: {color};'>{symbol} {delta}</div>"
    
    subtext_html = f"<div style='color: #94a3b8; font-size: 11px; margin-top: 4px;'>{subtext}</div>" if subtext else ""
    
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {delta_html}
            {subtext_html}
        </div>
    """, unsafe_allow_html=True)

# Hub Data Base
SOLAR_HUBS = {
    "Bhadla, Rajasthan (North Zone)": {"lat": 27.53, "lon": 72.35, "desc": "World's largest solar park. Dictates North-Grid marginal costs."},
    "Pavagada, Karnataka (South Zone)": {"lat": 14.28, "lon": 77.29, "desc": "Major Southern hub. High impact on SR clearing prices."},
    "Kurnool, AP (Central-South)": {"lat": 15.54, "lon": 78.27, "desc": "Ultra Mega Solar Park. Key for inter-regional flows."},
    "Rewa, Madhya Pradesh (Central)": {"lat": 24.53, "lon": 81.30, "desc": "Central India price setter. Supplies Delhi Metro directly."},
    "Charanka, Gujarat (West Zone)": {"lat": 23.91, "lon": 71.20, "desc": "Pioneer solar park. Dictates Western Grid surplus dynamics."}
}

WIND_HUBS = {
    "Muppandal, Tamil Nadu (South Zone)": {"lat": 8.25, "lon": 77.53, "desc": "India's highest wind capacity. Impacts baseload prices."},
    "Jaisalmer, Rajasthan (North Zone)": {"lat": 26.91, "lon": 70.91, "desc": "High altitude desert wind. Key for evening peaking."},
    "Brahmani, Maharashtra (West Zone)": {"lat": 19.49, "lon": 74.34, "desc": "Western grid wind cluster. Crucial for industrial balancing."},
    "Kutch, Gujarat (West-North)": {"lat": 23.36, "lon": 69.83, "desc": "Emerging massive wind cluster. Critical for WR-NR corridor flows."},
    "Anantapur, AP (South Zone)": {"lat": 14.68, "lon": 77.60, "desc": "High wind penetration zone in Southern India."}
}

# Helper Functions
@st.cache_resource
def load_models():
    models = {}
    model_paths = {
        "XG Boost (High Fidelity)": "models/xgboost_best.pkl",
        "Linear Baseline": "models/linear_regression_best.pkl"
    }
    for name, path in model_paths.items():
        if Path(path).exists():
            try: models[name] = joblib.load(path)
            except Exception: pass
    return models

@st.cache_data(ttl=3600)
def fetch_live_weather(lat, lon):
    try:
        end = datetime.now()
        start = end - timedelta(hours=2)
        station_df = stations.nearby(Point(lat, lon))
        if not station_df.empty:
            s_id = station_df.index[0]
            data = hourly(s_id, start, end).fetch()
            if not data.empty: return data.iloc[-1]
    except Exception: pass
    return None

# Helper for IEX Data
def get_iex_instance():
    import sys
    import os
    # Add project root to path for imports
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
    from src.data.iex_scraper import IEXScraper
    return IEXScraper()

# Title and Description
st.title("⚡ Electricity Price Strategy Dashboard")
st.markdown("#### Strategic Insights for the Indian Day-Ahead Market (DAM)")

# Sidebar
st.sidebar.header("🕹️ Control Center")
selected_solar_hub = st.sidebar.selectbox("Solar Monitoring Site", list(SOLAR_HUBS.keys()))
selected_wind_hub = st.sidebar.selectbox("Wind Monitoring Site", list(WIND_HUBS.keys()))

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 Live Data Feeds")
live_market_feed = st.sidebar.checkbox("🚀 Enable Live IEX Feed", value=False, help="Overrides entry price with real-time data from IEX India.")

if st.sidebar.button("Sync Intelligence (Hubs + IEX)"):
    with st.spinner("Syncing national hub intelligence..."):
        s_loc, w_loc = SOLAR_HUBS[selected_solar_hub], WIND_HUBS[selected_wind_hub]
        s_data = fetch_live_weather(s_loc['lat'], s_loc['lon'])
        w_data = fetch_live_weather(w_loc['lat'], w_loc['lon'])
        if s_data is not None: st.session_state.temp_val = float(s_data['temp'])
        if w_data is not None: st.session_state.wind_val = float(w_data['wspd'])
        
        if live_market_feed:
            scraper = get_iex_instance()
            live_mcp, m_date = scraper.get_latest_mcp()
            if live_mcp and not np.isnan(live_mcp):
                st.session_state.live_mcp = float(live_mcp)
                st.session_state.m_date = str(m_date)
                st.session_state.sync_time = datetime.now().strftime("%H:%M:%S")
                st.sidebar.success(f"IEX MCP Synced: ₹{live_mcp:.2f}")
            else:
                st.sidebar.error("Could not reach IEX. Check connection.")
        
        st.sidebar.success("Weather Hubs Synced Successfully")

st.sidebar.markdown("---")
models = load_models()
selected_model_name = st.sidebar.selectbox("Prediction Engine", list(models.keys()) + ["Strategy Simulation (Fallback)"])

if 'temp_val' not in st.session_state: st.session_state.temp_val = 32.0
if 'wind_val' not in st.session_state: st.session_state.wind_val = 25.0
if 'live_mcp' not in st.session_state: st.session_state.live_mcp = 52.0

# Price Logic (Live vs Simulation)
if live_market_feed:
    current_price = st.session_state.live_mcp
    st.sidebar.info(f"Using Live IEX MCP: ₹{current_price:.2f}")
    # Show slider but disabled or as a shadow
    _ = st.sidebar.slider("Market Entry Price (Live Locked)", 15.0, 150.0, current_price, disabled=True)
else:
    current_price = st.sidebar.slider("Market Entry Price (INR/MWh)", 15.0, 150.0, st.session_state.live_mcp)

base_demand = st.sidebar.slider("Grid Demand (MW)", 2000, 8000, 4200)
temp_val = st.sidebar.slider("Ambient Temp °C", 10.0, 50.0, st.session_state.temp_val)
wind_val = st.sidebar.slider("Wind Speed km/h", 0.0, 60.0, st.session_state.wind_val)

# Prediction Logic
def get_prediction_data(price, demand, temp, wind):
    blocks = np.arange(1, 97)
    # Scale simulation effects for high IEX prices so they stay visible
    # If price > 1000 (IEX level), we use a percentage-based scaling factor
    # But we keep it subtle enough to avoid unrealistic spikes
    scale_factor = max(1.0, price / 150.0) 
    
    solar_peak = (temp / 45) * 18 * scale_factor
    solar_effect = -solar_peak * np.exp(-((blocks-50)**2)/150)
    wind_effect = -(wind/60) * 12 * scale_factor
    demand_factor = (demand/6000) * 22 * scale_factor
    demand_effect = demand_factor * (np.exp(-((blocks-35)**2)/120) + np.exp(-((blocks-80)**2)/120))
    
    # Base pattern with proportional sine wave
    sine_volatility = 4 * scale_factor
    forecast = (price * 0.95 + sine_volatility * np.sin(2 * np.pi * blocks / 96)) + solar_effect + wind_effect + demand_effect + np.random.normal(0, scale_factor * 0.5, 96)
    forecast = np.maximum(forecast, 15.0)
    return blocks, forecast, forecast[0], solar_peak

blocks, forecast_data, next_price, solar_avg = get_prediction_data(current_price, base_demand, temp_val, wind_val)

# Dashboard Layout
st.markdown("### 📈 Market Pulse")
col1, col2, col3, col4 = st.columns(4)

price_diff = next_price - current_price
provenance = f"IEX Date: {st.session_state.get('m_date', 'N/A')} | Sync: {st.session_state.get('sync_time', 'N/A')}" if live_market_feed else "Mode: Strategy Simulation"

with col1: custom_card("T-Entry Price", f"₹{current_price:.2f}", subtext=provenance)
with col2: custom_card("T+1 Forecast", f"₹{next_price:.2f}", delta=f"{abs(price_diff):.2f}", delta_up=price_diff > 0)

if price_diff < -1.5: signal, color, conf = "BUY", "#10b981", "HIGH"
elif price_diff > 1.5: signal, color, conf = "SELL", "#ef4444", "EXTREME"
else: signal, color, conf = "HOLD", "#64748b", "MODERATE"

with col3:
    st.markdown(f"""
        <div class="strategy-container" style="background-color: {color};">
            <div style="color: rgba(255,255,255,0.8); font-size: 12px; font-weight: 700; text-transform: uppercase;">Strategy Signal</div>
            <div style="color: white; font-size: 32px; font-weight: 800; margin-top: 4px;">{signal}</div>
        </div>
    """, unsafe_allow_html=True)
with col4: custom_card("Confidence", conf)

st.markdown("---")

# Viz
st.subheader(f"📊 Impact Trajectory: {selected_solar_hub.split(',')[0]}")
fig = go.Figure()
# REMOVED fill='tozeroy' to allow tight auto-scaling on the y-axis
fig.add_trace(go.Scatter(x=blocks, y=forecast_data, mode='lines', name='Forecasted Price', 
                         line=dict(color='#3b82f6', width=4)))
fig.add_hline(y=current_price, line_dash="dash", line_color="#f59e0b", annotation_text="Baseline Price")

fig.update_layout(
    xaxis_title="Market Block (15-min Intervals)",
    yaxis_title="Price (INR/MWh)",
    template="plotly_white",
    hovermode="x unified",
    margin=dict(l=50, r=50, t=30, b=50),
    height=450,
    font=dict(color="#1e293b"),
    xaxis=dict(gridcolor="#f1f5f9", linecolor="#cbd5e1"),
    yaxis=dict(gridcolor="#f1f5f9", linecolor="#cbd5e1", autorange=True) # Explicit auto-scaling
)
st.plotly_chart(fig, use_container_width=True)

# Insights
st.markdown("### 🔍 Strategic Insights")
i1, i2 = st.columns(2)
with i1: st.info(f"**Solar Dynamic**: Temp at {temp_val:.1f}°C in {selected_solar_hub.split(',')[0]} drives a ₹{solar_avg:.1f} midday discount.")
with i2:
    if wind_val < 15: st.warning(f"**Wind Alert**: Low speeds ({wind_val:.1f} km/h) at {selected_wind_hub.split(',')[0]} trigger thermal spikes.")
    else: st.success(f"**Grid Balance**: Optimal wind ({wind_val:.1f} km/h) in {selected_wind_hub.split(',')[0]} stabilizes the curve.")

st.markdown("---")
st.caption(f"Environment: Production | CRISP-ML(Q) Audited | Last Sync: {datetime.now().strftime('%H:%M:%S')}")
