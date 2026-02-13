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

# Custom CSS
st.markdown("""<style>.main { background-color: #0f172a; } .metric-card { background-color: #ffffff; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); min-height: 140px; display: flex; flex-direction: column; justify-content: center; position: relative; } .metric-label { color: #64748b; font-size: 11px; font-weight: 700; text-transform: uppercase; margin-bottom: 8px; } .metric-value { color: #1e293b; font-size: 32px; font-weight: 800; } .strategy-container { border-radius: 12px; padding: 24px; text-align: center; min-height: 140px; display: flex; flex-direction: column; justify-content: center; }</style>""", unsafe_allow_html=True)

def custom_card(label, value, delta=None, delta_up=False, subtext=None, help_text=None):
    st.markdown(f"""<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div style="font-size: 11px; color: #64748b; margin-top: 8px;">{subtext if subtext else ""}</div></div>""", unsafe_allow_html=True)

@st.cache_data(ttl=86400)
def geocode_location(query):
    try:
        geolocator = Nominatim(user_agent="mcp_strategy_terminal_v8")
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
    # Defensive Scraper Instance
    scraper = get_iex_instance()
    mcp = st.session_state.get('live_mcp', 2840.5) 
    mcv = st.session_state.get('live_mcv', 6278.5)
    m_date = st.session_state.get('m_date', '14-02-2026')
    m_block = st.session_state.get('m_block', 'Syncing IST...')

    if scraper:
        try:
            # Multi-Method Defensive Probe
            sync_func = getattr(scraper, 'get_latest_market_data', None) or getattr(scraper, 'get_latest_mcp', None)
            if sync_func:
                res = sync_func()
                if res and isinstance(res, tuple):
                    if len(res) == 4: mcp, mcv, m_block, m_date = res
                    elif len(res) == 2: mcp, m_date = res
                if mcp: 
                    st.session_state.live_mcp = float(mcp)
                    st.session_state.live_mcv = float(mcv)
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

# Forecast Logic
def get_national_forecast(price, demand):
    blocks = np.arange(1, 97)
    scale = max(1.0, price / 150.0)
    forecast = (price * 0.98 + 5 * scale * np.sin(2 * np.pi * blocks / 96)) + (demand/30000)*15
    return blocks, np.maximum(forecast, 15.0), forecast[0]

blocks, forecast_data, next_price = get_national_forecast(st.session_state.live_mcp, p_bids)

# --- UI ---
st.title("⚡ IEX Market Strategy Dashboard")
st.markdown(f"#### Day-Ahead Market (DAM) Planning | Serve: {st.session_state.display_city}")

st.markdown("### 📈 Live Market Clearing Components")
col1, col2, col3, col4 = st.columns(4)
with col1: custom_card("Uniform MCP", f"₹{st.session_state.live_mcp:.2f}", subtext=f"Block: {st.session_state.m_block}")
with col2: custom_card("Market Volume (MCV)", f"{st.session_state.live_mcv:,.0f} MW", subtext=f"Block: {st.session_state.m_block}")
with col3:
    diff = next_price - st.session_state.live_mcp
    custom_card("T+1 Price Forecast", f"₹{next_price:.2f}", subtext="Target: Next 15-min")
with col4:
    sig, col = ("BUY BID", "#10b981") if diff < -2.0 else (("SELL BID", "#f59e0b") if diff > 2.0 else ("HOLD", "#ef4444"))
    st.markdown(f"""<div class="strategy-container" style="background-color: {col};"><div style="color: white; font-size: 24px; font-weight: 800;">{sig}</div></div>""", unsafe_allow_html=True)

st.markdown("---")
fig = go.Figure()
time_labels = [(datetime(2026, 1, 1) + timedelta(minutes=15 * (int(b)-1))).strftime('%H:%M') for b in blocks]
fig.add_trace(go.Scatter(x=blocks, y=forecast_data, mode='lines', line=dict(color='#3b82f6', width=4)))
fig.update_layout(height=400, template="plotly_white", margin=dict(l=50, r=50, t=30, b=50), xaxis=dict(tickmode='array', tickvals=blocks[::8], ticktext=time_labels[::8]))
st.plotly_chart(fig, use_container_width=True)

with st.expander("🎓 **IEX Bidding Strategy Lab**"):
    st.markdown("""| Feature | **Single Bid** | **Block Bid** |\\n| :-- | :-- | :-- |\\n| Time | 15-min blocks | Continuous set |\\n| Exec | Partial allowed | All-or-None |""")

st.caption(f"Environment: IEX-Production | Sync: {st.session_state.sync_time} IST")
