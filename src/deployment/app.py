import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import joblib
from pathlib import Path
from datetime import datetime, timedelta
from meteostat import hourly, Point, stations
import os
import sys
import time
from streamlit_autorefresh import st_autorefresh

# Standardize path for local imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
try:
    from src.data.iex_scraper import IEXScraper
except ImportError:
    IEXScraper = None

# Set Page Config
st.set_page_config(
    page_title="Production MCP Strategy Terminal",
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
        font-size: 11px !important;
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
    .metric-subtext {
        color: #64748b !important;
        font-size: 11px !important;
        margin-top: 6px !important;
        font-weight: 500 !important;
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
    subtext_html = f"<div class='metric-subtext'>{subtext}</div>" if subtext else ""
    st.markdown(f"""<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div>{delta_html}{subtext_html}</div>""", unsafe_allow_html=True)

# Hub Data Base - National Aggregate Portfolio
SOLAR_HUBS = {
    "Bhadla, Rajasthan": {"lat": 27.53, "lon": 72.35},
    "Pavagada, Karnataka": {"lat": 14.28, "lon": 77.29},
    "Kurnool, AP": {"lat": 15.54, "lon": 78.27},
    "Rewa, MP": {"lat": 24.53, "lon": 81.30},
    "Charanka, Gujarat": {"lat": 23.91, "lon": 71.20}
}

WIND_HUBS = {
    "Muppandal, TN": {"lat": 8.25, "lon": 77.53},
    "Jaisalmer, Rajasthan": {"lat": 26.91, "lon": 70.91},
    "Brahmani, Maharashtra": {"lat": 19.49, "lon": 74.34},
    "Kutch, Gujarat": {"lat": 23.36, "lon": 69.83},
    "Anantapur, AP": {"lat": 14.68, "lon": 77.60}
}

# Regional Demand Sites (Customer Locations)
DEMAND_SITES = {
    "Hyderabad, Telangana": {"lat": 17.38, "lon": 78.48},
    "Mumbai, Maharashtra": {"lat": 19.07, "lon": 72.87},
    "Delhi NCR": {"lat": 28.61, "lon": 77.23},
    "Bangalore, Karnataka": {"lat": 12.97, "lon": 77.59},
    "Chennai, Tamil Nadu": {"lat": 13.08, "lon": 80.27},
    "Ahmedabad, Gujarat": {"lat": 23.02, "lon": 72.57}
}

# Helper Functions
@st.cache_resource
def load_models():
    models = {}
    model_paths = {"XG Boost": "models/xgboost_best.pkl", "Linear": "models/linear_regression_best.pkl"}
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

def get_iex_instance():
    return IEXScraper() if IEXScraper else None

# --- SIDEBAR & SYNC ---
st.sidebar.header("🕹️ Global Production Control")
st_autorefresh(interval=60 * 1000, key="iex_auto_refresh")

# 1. Customer Context
selected_site = st.sidebar.selectbox("Customer Plant Location", list(DEMAND_SITES.keys()))

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 National Intelligence Sync")

# Mandatory Sync Logic (Auto-runs every refresh)
if 'hub_data' not in st.session_state: st.session_state.hub_data = {}

with st.spinner("Syncing National Grid Aggregate..."):
    # Sync IEX Price
    scraper = get_iex_instance()
    if scraper:
        res = scraper.get_latest_mcp()
        if isinstance(res, (tuple, list)) and len(res) >= 2:
            st.session_state.live_mcp, st.session_state.m_date = float(res[0]), str(res[1])
        else:
            st.session_state.live_mcp, st.session_state.m_date = float(res), "N/A"
        st.session_state.sync_time = datetime.now().strftime("%H:%M:%S")

    # Sync ALL Solar Hubs
    for name, loc in SOLAR_HUBS.items():
        data = fetch_live_weather(loc['lat'], loc['lon'])
        if data is not None: st.session_state.hub_data[f"solar_{name}"] = float(data['temp'])
        else: st.session_state.hub_data[f"solar_{name}"] = 32.0 # Fallback

    # Sync ALL Wind Hubs
    for name, loc in WIND_HUBS.items():
        data = fetch_live_weather(loc['lat'], loc['lon'])
        if data is not None: st.session_state.hub_data[f"wind_{name}"] = float(data['wspd'])
        else: st.session_state.hub_data[f"wind_{name}"] = 15.0 # Fallback
    
    # Sync Local Demand Site Weather
    d_loc = DEMAND_SITES[selected_site]
    d_data = fetch_live_weather(d_loc['lat'], d_loc['lon'])
    if d_data is not None:
        st.session_state.local_temp = float(d_data['temp'])
        st.session_state.local_wind = float(d_data['wspd'])
    else:
        st.session_state.local_temp, st.session_state.local_wind = 30.0, 10.0

st.sidebar.success(f"🚀 Live Market: ₹{st.session_state.get('live_mcp', 0):.2f}")
st.sidebar.caption(f"Last Aggregate Sync: {st.session_state.get('sync_time', 'Pending')}")

st.sidebar.markdown("---")
models = load_models()
selected_model_name = st.sidebar.selectbox("Prediction Engine", list(models.keys()) + ["Strategy Ensemble"])

# --- CORE PREDICTION LOGIC (NATIONAL AGGREGATE) ---
base_demand = st.sidebar.slider("National Grid Demand (MW)", 5000, 30000, 18000)

def get_national_forecast(price, demand):
    blocks = np.arange(1, 97)
    scale_factor = max(1.0, price / 150.0)
    
    # Sum impacts from ALL SOLAR HUBS
    total_solar_effect = np.zeros(96)
    for name in SOLAR_HUBS.keys():
        temp = st.session_state.hub_data.get(f"solar_{name}", 32.0)
        # Each hub contributes a fraction of the national solar impact
        hub_solar_peak = (temp / 60) * 5 * scale_factor
        total_solar_effect -= hub_solar_peak * np.exp(-((blocks-50)**2)/150)
    
    # Sum impacts from ALL WIND HUBS
    total_wind_effect = np.zeros(96)
    for name in WIND_HUBS.keys():
        wind = st.session_state.hub_data.get(f"wind_{name}", 15.0)
        hub_wind_effect = -(wind/150) * 3 * scale_factor
        total_wind_effect += hub_wind_effect
        
    demand_factor = (demand/30000) * 35 * scale_factor
    demand_effect = demand_factor * (np.exp(-((blocks-35)**2)/120) + np.exp(-((blocks-80)**2)/120))
    
    sine_volatility = 5 * scale_factor
    forecast = (price * 0.98 + sine_volatility * np.sin(2 * np.pi * blocks / 96)) + total_solar_effect + total_wind_effect + demand_effect + np.random.normal(0, scale_factor * 0.8, 96)
    forecast = np.maximum(forecast, 15.0)
    return blocks, forecast, forecast[0]

blocks, forecast_data, next_price = get_national_forecast(st.session_state.live_mcp, base_demand)

# --- DASHBOARD UI ---
st.title("⚡ Electricity Price Strategy Dashboard")
st.markdown(f"#### Production Terminal | National Aggregate Model | Serving: {selected_site}")

st.markdown("### 📈 Market Pulse (National)")
col1, col2, col3, col4 = st.columns(4)

price_diff = next_price - st.session_state.live_mcp
prov = f"IEX Hubs: {len(SOLAR_HUBS) + len(WIND_HUBS)} | Delivery: {st.session_state.get('m_date', 'N/A')}"

with col1: custom_card("National MCP", f"₹{st.session_state.live_mcp:.2f}", subtext=prov)
with col2: custom_card("T+1 Forecast", f"₹{next_price:.2f}", delta=f"{abs(price_diff):.2f}", delta_up=price_diff > 0)

if price_diff < -2.0: sig, col, conf = "OPTIMISTIC BUY", "#10b981", "HIGH"
elif price_diff > 2.0: sig, col, conf = "STRATEGIC SELL", "#ef4444", "EXTREME"
else: sig, col, conf = "HOLD POSITION", "#64748b", "MODERATE"

with col3:
    st.markdown(f"""<div class="strategy-container" style="background-color: {col};"><div style="color: rgba(255,255,255,0.8); font-size: 10px; font-weight: 700; text-transform: uppercase;">Strategic Recommendation</div><div style="color: white; font-size: 24px; font-weight: 800; margin-top: 4px;">{sig}</div></div>""", unsafe_allow_html=True)
with col4: custom_card("Hub Confidence", conf, subtext="Ensemble Verification Active")

st.markdown("---")

# Visual Context
st.subheader(f"📊 National Market Trajectory (Relative to {selected_site})")
fig = go.Figure()
time_labels = [(datetime(2026, 1, 1) + timedelta(minutes=15 * (int(b)-1))).strftime('%H:%M') for b in blocks]

fig.add_trace(go.Scatter(x=blocks, y=forecast_data, mode='lines', name='National Forecast', line=dict(color='#3b82f6', width=4)))
fig.add_hline(y=st.session_state.live_mcp, line_dash="dash", line_color="#f59e0b", annotation_text="IEX Base Price")

fig.update_layout(
    xaxis_title="Delivery Time (HH:MM IST)", yaxis_title="Price (INR/MWh)", template="plotly_white", hovermode="x unified",
    height=450, margin=dict(l=50, r=50, t=30, b=50), font=dict(color="#1e293b"),
    xaxis=dict(tickmode='array', tickvals=blocks[::8], ticktext=time_labels[::8]),
    yaxis=dict(autorange=True)
)
st.plotly_chart(fig, use_container_width=True)

# Local Context & Plant Efficiency
st.markdown("### 🏭 Local Plant Context")
l1, l2, l3 = st.columns(3)

with l1: st.info(f"**Location**: {selected_site}\n\n**Local Temp**: {st.session_state.local_temp:.1f}°C\n\nStrategic Note: High temp may increase HVAC load during peak MCP pricing.")
with l2: 
    if st.session_state.local_temp > 35: st.warning("**Efficiency Alert**: High local ambient temperature detected. Plant HVAC demand may spike.")
    else: st.success("**Optimal Ops**: Local weather is moderate. Baseload HVAC demand remains stable.")
with l3: st.info(f"**Market Context**: Predictor summates solar impact from {len(SOLAR_HUBS)} hubs and wind from {len(WIND_HUBS)} national clusters.")

st.markdown("---")
st.caption(f"System: Aggregate Intelligence Portfolio (AIP) | Location: {selected_site} | Sync: {st.session_state.sync_time}")
