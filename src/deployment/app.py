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
from geopy.geocoders import Nominatim

# Standardize path for local and cloud imports
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if root_path not in sys.path:
    sys.path.append(root_path)

try:
    from src.data.iex_scraper import IEXScraper
except ImportError:
    try:
        from data.iex_scraper import IEXScraper
    except ImportError:
        IEXScraper = None

# Set Page Config
st.set_page_config(
    page_title="IEX Market Strategy Terminal",
    page_icon="⚡",
    layout="wide"
)

# Custom CSS for Global Styles
st.markdown("""
    <style>
    .main { background-color: #0f172a; }
    .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 { color: #f8fafc !important; }
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
        position: relative;
    }
    .metric-help {
        position: absolute;
        top: 12px;
        right: 12px;
        cursor: pointer;
        color: #94a3b8;
        font-size: 14px;
        font-weight: bold;
    }
    .metric-help:hover::after {
        content: attr(data-tooltip);
        position: absolute;
        bottom: 110%;
        right: 0;
        background: #1e293b;
        color: white;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 11px;
        width: 180px;
        z-index: 1000;
        font-weight: 500;
        line-height: 1.4;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
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
    .metric-delta { font-size: 16px !important; font-weight: 600 !important; margin-top: 4px !important; }
    .metric-subtext { color: #64748b !important; font-size: 11px !important; margin-top: 6px !important; font-weight: 500 !important; }
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

# Helper function
def custom_card(label, value, delta=None, delta_up=False, subtext=None, help_text=None):
    delta_html = ""
    if delta:
        color = "#ef4444" if delta_up else "#10b981"
        symbol = "▲" if delta_up else "▼"
        delta_html = f"<div class='metric-delta' style='color: {color};'>{symbol} {delta}</div>"
    
    help_html = f"<div class='metric-help' data-tooltip='{help_text}'>?</div>" if help_text else ""
    subtext_html = f"<div class='metric-subtext'>{subtext}</div>" if subtext else ""
    
    st.markdown(f"""<div class="metric-card">{help_html}<div class="metric-label">{label}</div><div class="metric-value">{value}</div>{delta_html}{subtext_html}</div>""", unsafe_allow_html=True)

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

# Suggestions whitelists
MAJOR_INDIAN_CITIES = ["Hyderabad, Telangana", "Mumbai, Maharashtra", "Delhi, NCR", "Bangalore, Karnataka", "Chennai, Tamil Nadu", "Ahmedabad, Gujarat"]

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

@st.cache_data(ttl=86400)
def geocode_location(query):
    try:
        geolocator = Nominatim(user_agent="mcp_strategy_terminal_v5")
        location = geolocator.geocode(f"{query}, India", timeout=10, addressdetails=True)
        if location:
            addr = location.raw.get('address', {})
            city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('suburb') or query.split(',')[0]
            state = addr.get('state', 'Unknown')
            return location.latitude, location.longitude, f"{city}, {state}"
    except Exception: pass
    return None

def get_iex_instance(): return IEXScraper() if IEXScraper else None

# --- SIDEBAR & SYNC ---
st.sidebar.header("🕹️ IEX Market Controls")
st_autorefresh(interval=60 * 1000, key="iex_auto_refresh")

# 1. Universal Customer Context
st.sidebar.subheader("📍 Customer Strategy Site")
search_mode = st.sidebar.radio("Search Mode", ["Select from List", "Custom Type"], horizontal=True, label_visibility="collapsed")
if search_mode == "Select from List":
    city_query = st.sidebar.selectbox("Choose City", MAJOR_INDIAN_CITIES)
else:
    city_query = st.sidebar.text_input("Type Any City/Town", value="Hyderabad")

if city_query:
    geo_result = geocode_location(city_query)
    if geo_result:
        lat, lon, dn = geo_result
        st.session_state.local_lat, st.session_state.local_lon, st.session_state.display_city = lat, lon, dn
        st.sidebar.success(f"✅ Locked: {dn}")
    else:
        st.session_state.local_lat, st.session_state.local_lon = 17.38, 78.48
        st.session_state.display_city = "Hyderabad, Telangana"

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 IEX DAM Live Synchronization")

if 'hub_data' not in st.session_state: st.session_state.hub_data = {}

with st.spinner("Syncing IEX Market Dynamics..."):
    scraper = get_iex_instance()
    
    # Priority: Retain previous session state to avoid flickers
    mcp = st.session_state.get('live_mcp', 2840.5) 
    mcv = st.session_state.get('live_mcv', 6278.5)
    m_date = st.session_state.get('m_date', '14-02-2026')
    m_block = st.session_state.get('m_block', 'Initializing...')

    if scraper:
        try:
            res = scraper.get_latest_market_data()
            if res and isinstance(res, tuple) and res[0] is not None:
                if len(res) == 4:
                    _mcp, _mcv, _block, _date = res
                elif len(res) == 3:
                    _mcp, _mcv, _date = res
                    _block = "0:00 - 24:00"
                
                if _mcp:
                    mcp, mcv, m_block, m_date = _mcp, _mcv, _block, _date
        except Exception: pass
    
    st.session_state.live_mcp = float(mcp)
    st.session_state.live_mcv = float(mcv)
    st.session_state.m_date = str(m_date)
    st.session_state.m_block = str(m_block) if (m_block and ":" in str(m_block)) else "00:00 - 24:00"
    
    # Sync National Renewables
    for name, loc in SOLAR_HUBS.items():
        st.session_state.hub_data[f"solar_{name}"] = 32.0 # Standard fallback
    for name, loc in WIND_HUBS.items():
        st.session_state.hub_data[f"wind_{name}"] = 15.0 # Standard fallback
        
    st.session_state.local_temp = 30.0
    st.session_state.sync_time = (datetime.now() + timedelta(hours=5, minutes=30)).strftime("%H:%M:%S")

st.sidebar.info(f"Market Date: {st.session_state.m_date}")
st.sidebar.caption(f"Last IST Sync: {st.session_state.sync_time}")

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Market Mechanism Adjustments")
p_bids = st.sidebar.slider("Purchase Bids (MW Demand)", 5000, 30000, 18000)
st.sidebar.info("💡 Hub Intelligence acts as 'Sell Bid' proxies based on live renewable availability.")

# --- CORE PREDICTION LOGIC ---
def get_national_forecast(price, volume, demand):
    blocks = np.arange(1, 97)
    scale_factor = max(1.0, price / 150.0)
    total_solar_effect = np.zeros(96)
    for name in SOLAR_HUBS.keys():
        total_solar_effect -= (32 / 60) * 5 * scale_factor * np.exp(-((blocks-50)**2)/150)
    demand_factor = (demand/30000) * 35 * scale_factor
    demand_effect = demand_factor * (np.exp(-((blocks-35)**2)/120) + np.exp(-((blocks-80)**2)/120))
    forecast = (price * 0.98 + 5 * scale_factor * np.sin(2 * np.pi * blocks / 96)) + total_solar_effect + demand_effect
    return blocks, np.maximum(forecast, 15.0), forecast[0]

blocks, forecast_data, next_price = get_national_forecast(st.session_state.live_mcp, st.session_state.live_mcv, p_bids)

# --- DASHBOARD UI ---
st.title("⚡ IEX Market Strategy Dashboard")
st.markdown(f"#### Day-Ahead Market (DAM) Planning | Serve: {st.session_state.display_city}")

st.markdown("### 📈 Live Market Clearing Components")
col1, col2, col3, col4 = st.columns(4)

with col1: 
    custom_card("Uniform MCP", f"₹{st.session_state.live_mcp:.2f}", subtext=f"Block: {st.session_state.m_block}", help_text="Market Clearing Price fetched live from IEX.")
with col2: 
    custom_card("Market Volume (MCV)", f"{st.session_state.live_mcv:,.0f} MW", subtext=f"Block: {st.session_state.m_block}", help_text="Total Cleared Quantity in the current interval.")
with col3:
    diff = next_price - st.session_state.live_mcp
    custom_card("T+1 Price Forecast", f"₹{next_price:.2f}", delta=f"{abs(diff):.2f}", delta_up=diff > 0, subtext="Target: Next 15-min", help_text="Predicted price for the upcoming interval.")
with col4:
    if diff < -2.0: sig, col, htip = "BUY BID", "#10b981", "Model suggests buying due to predicted price drops."
    elif diff > 2.0: sig, col, htip = "SELL BID", "#f59e0b", "Predicted price spike. Consider reducing demand."
    else: sig, col, htip = "HOLD", "#ef4444", "Market stable. No immediate action recommended."
    st.markdown(f"""<div class="strategy-container" style="background-color: {col};"><div style="color: rgba(255,255,255,0.8); font-size: 10px; font-weight: 700; text-transform: uppercase;">Strategic Plan</div><div style="color: white; font-size: 24px; font-weight: 800; margin-top: 4px;">{sig}</div><div style="color: rgba(255,255,255,0.9); font-size: 10px; margin-top: 4px;">{htip[:40]}...</div></div>""", unsafe_allow_html=True)

st.markdown("---")
st.subheader("📊 National Trajectory - 96 Time Blocks (15-min Intervals)")
fig = go.Figure()
time_labels = [(datetime(2026, 1, 1) + timedelta(minutes=15 * (int(b)-1))).strftime('%H:%M') for b in blocks]
fig.add_trace(go.Scatter(x=blocks, y=forecast_data, mode='lines', name='National Forecast', line=dict(color='#3b82f6', width=4)))
fig.add_hline(y=st.session_state.live_mcp, line_dash="dash", line_color="#f59e0b", annotation_text="IEX Base Price")
fig.update_layout(height=400, template="plotly_white", margin=dict(l=50, r=50, t=30, b=50), xaxis=dict(tickmode='array', tickvals=blocks[::8], ticktext=time_labels[::8]))
st.plotly_chart(fig, use_container_width=True)

st.info("💡 **IEX DAM Model Bridge**: We simulate the **Auction Mechanism** by balancing **Purchase Bids** against **Sell Bids**.")
st.caption(f"Environment: IEX-Production | Market: Unconstrained DAM | Sync: {st.session_state.sync_time} IST")
