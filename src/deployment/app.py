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
import importlib
from streamlit_autorefresh import st_autorefresh
from geopy.geocoders import Nominatim

# Standardize path for local and cloud imports
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if root_path not in sys.path:
    sys.path.append(root_path)

# Unified Scraper Import with Reload Support
def get_iex_instance(force_reload=False):
    global IEXScraper
    try:
        from src.data.iex_scraper import IEXScraper
        if force_reload:
            import src.data.iex_scraper
            importlib.reload(src.data.iex_scraper)
            from src.data.iex_scraper import IEXScraper
        return IEXScraper()
    except Exception:
        try:
            from data.iex_scraper import IEXScraper
            return IEXScraper()
        except Exception:
            return None

# Set Page Config
st.set_page_config(page_title="IEX Market Strategy Terminal", page_icon="⚡", layout="wide")

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

# Helper function for Metric Cards
def custom_card(label, value, delta=None, delta_up=False, subtext=None, help_text=None):
    delta_html = ""
    if delta:
        color = "#ef4444" if delta_up else "#10b981"
        symbol = "▲" if delta_up else "▼"
        delta_html = f"<div class='metric-delta' style='color: {color};'>{symbol} {delta}</div>"
    
    help_html = f"<div class='metric-help' data-tooltip='{help_text}'>?</div>" if help_text else ""
    subtext_html = f"<div class='metric-subtext'>{subtext}</div>" if subtext else ""
    
    st.markdown(f"""
        <div class="metric-card">
            {help_html}
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {delta_html}
            {subtext_html}
        </div>
    """, unsafe_allow_html=True)

# Hub Data Base
SOLAR_HUBS = {"Bhadla, RJ": {"lat": 27.53, "lon": 72.35}, "Pavagada, KA": {"lat": 14.28, "lon": 77.29}, "Kurnool, AP": {"lat": 15.54, "lon": 78.27}}
WIND_HUBS = {"Muppandal, TN": {"lat": 8.25, "lon": 77.53}, "Jaisalmer, RJ": {"lat": 26.91, "lon": 70.91}}

@st.cache_data(ttl=86400)
def geocode_location(query):
    try:
        geolocator = Nominatim(user_agent="mcp_strategy_terminal_v9")
        location = geolocator.geocode(f"{query}, India", timeout=10, addressdetails=True)
        if location:
            addr = location.raw.get('address', {})
            city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('suburb') or query.split(',')[0]
            state = addr.get('state', 'Unknown')
            return location.latitude, location.longitude, f"{city}, {state}"
    except Exception: pass
    return None

# --- SIDEBAR & SYNC ---
st.sidebar.header("🕹️ IEX Market Controls")
st_autorefresh(interval=60 * 1000, key="iex_auto_refresh")

if st.sidebar.button("🔄 Force App Hard-Reset"):
    st.cache_data.clear()
    st.session_state.clear()
    get_iex_instance(force_reload=True)
    st.rerun()

st.sidebar.subheader("📍 Customer Strategy Site")
city_query = st.sidebar.text_input("Site Location (City/Town)", value="Hyderabad")
if city_query:
    geo_result = geocode_location(city_query)
    if geo_result:
        lat, lon, dn = geo_result
        st.session_state.local_lat, st.session_state.local_lon, st.session_state.display_city = lat, lon, dn
    else:
        st.session_state.local_lat, st.session_state.local_lon = 17.38, 78.48
        st.session_state.display_city = "Hyderabad, Telangana"

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 IEX DAM Live Synchronization")

with st.spinner("Syncing IEX Market Dynamics..."):
    scraper = get_iex_instance()
    mcp = st.session_state.get('live_mcp', 2840.5) 
    mcv = st.session_state.get('live_mcv', 6278.5)
    m_date = st.session_state.get('m_date', '14-02-2026')
    m_block = st.session_state.get('m_block', 'Syncing IST...')

    if scraper:
        try:
            sync_func = getattr(scraper, 'get_latest_market_data', None) or getattr(scraper, 'get_latest_mcp', None)
            if sync_func:
                res = sync_func()
                if res and isinstance(res, tuple):
                    if len(res) == 4: mcp, mcv, m_block, m_date = res
                    elif len(res) == 2: mcp, m_date = res
                if mcp: 
                    st.session_state.live_mcp, st.session_state.live_mcv = float(mcp), float(mcv)
                    st.session_state.m_date, st.session_state.m_block = str(m_date), str(m_block)
            else:
                st.sidebar.error("Critical: Sync methods missing in runtime.")
        except Exception as e:
            st.sidebar.error(f"Sync Error: {str(e)}")
    
    st.session_state.sync_time = (datetime.now() + timedelta(hours=5, minutes=30)).strftime("%H:%M:%S")

st.sidebar.info(f"Market Date: {st.session_state.m_date}")
st.sidebar.caption(f"Last IST Sync: {st.session_state.sync_time}")

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Market Parameters")
p_bids = st.sidebar.slider("Purchase Bids (MW Demand)", 5000, 30000, 18000)

# Forecast Logic with Renewable Impact
def get_national_forecast(price, demand):
    blocks = np.arange(1, 97)
    scale = max(1.0, price / 150.0)
    # Simulated renewable impact (Solar DIP at night, Peak at noon)
    solar_impact = 10 * np.sin(np.pi * blocks / 96) # Higher impact during day
    forecast = (price * 0.98 + 5 * scale * np.sin(2 * np.pi * blocks / 96)) + (demand/30000)*15 - solar_impact
    return blocks, np.maximum(forecast, 15.0), forecast[0]

blocks, forecast_data, next_price = get_national_forecast(st.session_state.live_mcp, p_bids)

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
    if diff < -2.0: sig, col, htip = "BUY BID", "#10b981", "Model suggests buying."
    elif diff > 2.0: sig, col, htip = "SELL BID", "#f59e0b", "Predicted price spike."
    else: sig, col, htip = "HOLD", "#ef4444", "Market stable."
    st.markdown(f"""<div class="strategy-container" style="background-color: {col};"><div style="color: rgba(255,255,255,0.8); font-size: 10px; font-weight: 700; text-transform: uppercase;">Strategic Plan</div><div style="color: white; font-size: 24px; font-weight: 800; margin-top: 4px;">{sig}</div><div style="color: rgba(255,255,255,0.9); font-size: 10px; margin-top: 4px;">{htip}</div></div>""", unsafe_allow_html=True)

st.markdown("---")
st.subheader("📊 National Trajectory - 96 Time Blocks (15-min Intervals)")
fig = go.Figure()
time_labels = [(datetime(2026, 1, 1) + timedelta(minutes=15 * (int(b)-1))).strftime('%H:%M') for b in blocks]
fig.add_trace(go.Scatter(x=blocks, y=forecast_data, mode='lines', name='National Forecast', line=dict(color='#3b82f6', width=4)))
# Restore IEX Base Price Line
fig.add_hline(y=st.session_state.live_mcp, line_dash="dash", line_color="#f59e0b", annotation_text="IEX Base Price")
fig.update_layout(height=400, template="plotly_white", margin=dict(l=50, r=50, t=30, b=50), xaxis=dict(tickmode='array', tickvals=blocks[::8], ticktext=time_labels[::8]))
st.plotly_chart(fig, use_container_width=True)

with st.expander("🎓 **IEX Bidding Strategy Lab**: Single vs. Block Bids"):
    st.markdown("""
| Feature | **Single Bid (Portfolio)** | **Block Bid (All-or-None)** |
| :--- | :--- | :--- |
| **Time Period** | Individual 15-min blocks | Continuous set of blocks |
| **Execution** | Partial execution allowed | Full quantity or nothing |
| **Logic** | Linear interpolation between points | Selected if Avg MCP >= Bid Price |
""")

st.caption(f"Environment: IEX-Production | Market: Unconstrained DAM | Sync: {st.session_state.sync_time} IST")
