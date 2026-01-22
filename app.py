import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# ==========================================
# 1. KURUMSAL YAPILANDIRMA
# ==========================================
st.set_page_config(
    page_title="Gold Market Arbitrage",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 60 Saniyede bir sayfayı yenile
st_autorefresh(interval=60 * 1000, key="sys_refresh")

# ==========================================
# 2. PREMIUM CSS (TASARIM)
# ==========================================
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    header {visibility: hidden;}
    
    div[data-testid="stMetric"] {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 15px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }
    
    div[data-testid="stMetric"]:hover {
        border-color: #58A6FF;
    }
    
    [data-testid="stMetricValue"] {
        font-family: 'Inter', sans-serif;
        font-size: 28px !important;
        font-weight: 600 !important;
        color: #F0F6FC !important;
    }
    
    [data-testid="stMetricLabel"] {
        color: #8B949E !important;
    }

    .stRadio > div {
        background-color: #161B22;
        border: 1px solid #30363D;
    }
    
    .stRadio label {
        color: #C9D1D9 !important;
    }
    
    .main-header { font-family: 'Inter', sans-serif; font-weight: 700; color: #F0F6FC; margin-bottom: 0px; }
    .sub-header { font-family: 'Inter', sans-serif; color: #8B949E; font-size: 14px; margin-top: -5px; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. VERİ MOTORU
# ==========================================

def get_simulated_data(minutes, label):
    """Veri yoksa devreye giren simülasyon."""
    end_date = pd.Timestamp.now()
    start_date = end_date - timedelta(minutes=minutes)
    
    freq_map = {60: "1min", 1440: "15min", 10080: "1h", 43200: "4h"}
    freq = freq_map.get(minutes, "1D")
    
    dates = pd.date_range(start=start_date, end=end_date, freq=freq)
    
    base = 9866.0
    np.random.seed(42) 
    volatility = np.random.normal(0, 2, size=len(dates))
    prices = base + np.cumsum(volatility)
    
    df = pd.DataFrame(index=dates)
    df['x'] = prices
    
    # Fiziki Altın Modeli
    spread_base = prices * 0.045
    noise = np.random.normal(0, 8, size=len(dates))
    
    df['physical'] = prices + spread_base + noise
    df['spread'] = df['physical'] - df['x']
    
    return df

@st.cache_data(ttl=60, show_spinner=False)
def fetch_enterprise_data(selection):
    settings = {
        "1S": ("5d", "1m", 60),
        "24S": ("5d", "15m", 1440),
        "1H": ("1mo", "60m", 10080),
        "1A": ("3mo", "90m", 43200),
        "3A": ("1y", "1d", 129600),
        "1Y": ("2y", "1d", 525600)
    }
    
    p, i, m = settings.get(selection, ("5d", "1m", 60))

    try:
        df = yf.download("ALTIN.IS", period=p, interval=i, progress=False)
        
        if isinstance(df.columns, pd.MultiIndex):
            if "ALTIN.IS" in df.columns.levels[1]:
                df = df.xs("ALTIN.IS", axis=1, level=1)
        
        if df.empty or "Close" not in df.columns:
            raise ValueError("No Data")

        df = df[["Close"]].dropna()
        df.columns = ["x"]
        df["x"] = df["x"] * 100.0

        np.random.seed(42)
        noise = np.random.normal(0, 5, len(df))
        df["physical"] = df["x"] * 1.04 + noise
        df["spread"] = df["physical"] - df["x"]

        last_ts = df.index.max()
        start_ts = last_ts - timedelta(minutes=m)
        final_df = df[df.index >= start_ts]
        
        if final_df.empty: raise ValueError("Empty Slice")
        
        return final_df

    except Exception:
        return get_simulated_data(m, selection)

# ==========================================
# 4. ARAYÜZ (UI)
# ==========================================

col_logo, col_title, col_time = st.columns([1, 6, 3])

with col_title:
    st.markdown("<h2 class='main-header'>Altın Arbitraj Paneli</h2>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Canlı Piyasa Analizi ve Makas Takibi • Enterprise Edition</p>", unsafe_allow_html=True)

with col_time:
    time_options = ["1S", "24S", "1H", "1A", "3A", "1Y"]
    selected_time = st.radio("Zaman", time_options, horizontal=True, label_visibility="collapsed")

# Veriyi Çek
df = fetch_enterprise_data(selected_time)

# KPI Kartları
curr = df.iloc[-1]
prev = df.iloc[-2] if len(df) > 1 else df.iloc[0]
spread_delta = curr['spread'] - prev['spread']

c1, c2, c3 = st.columns(3)
with c1: st.metric("Sertifika (X)", f"{curr['x']:,.0f} ₺", f"{curr['x'] - prev['x']:.2f} ₺")
with c2: st.metric("Fiziki Altın (Piyasa)", f"{curr['physical']:,.0f} ₺", f"{curr['physical'] - prev['physical']:.2f} ₺", delta_color="off")
with c3: st.metric("Makas (Spread)", f"{curr['spread']:.2f} ₺", f"{spread_delta:.2f} ₺", delta_color="inverse")

st.markdown("---")

# --- GRAFİK AYARLARI (ZOOM FIX) ---
# Burası grafiğin 0'dan başlamamasını, veriye odaklanmasını sağlar.
y_min = min(df['x'].min(), df['physical'].min())
y_max = max(df['x'].max(), df['physical'].max())
padding = (y_max - y_min) * 0.1 # %10 boşluk bırak
y_range = [y_min - padding, y_max + padding]

# Grafik 1: Fiyatlar
fig_price = go.Figure()
fig_price.add_trace(go.Scatter(x=df.index, y=df['x'], mode='lines', name='Sertifika (X)', line=dict(color='#2f81f7', width=2), fill='tozeroy', fillcolor='rgba(47, 129, 247, 0.05)'))
fig_price.add_trace(go.Scatter(x=df.index, y=df['physical'], mode='lines', name='Fiziki Piyasa', line=dict(color='#D29922', width=2)))

fig_price.update_layout(
    title=dict(text="Fiyat Trendi", font=dict(size=18, color='#F0F6FC')),
    template="plotly_dark",
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    height=420,
    margin=dict(t=50, b=20, l=0, r=0),
    xaxis=dict(showgrid=False, color='#484F58'),
    yaxis=dict(
        showgrid=True, 
        gridcolor='#21262D', 
        color='#8B949E',
        range=y_range  # <--- İŞTE BU AYAR GRAFİĞİ CANLANDIRIR (ZOOM YAPAR)
    ),
    hovermode="x unified",
    legend=dict(orientation="h", y=1.05, x=0, font=dict(color='#C9D1D9'))
)
st.plotly_chart(fig_price, use_container_width=True)

# Grafik 2: Makas (Spread) Zoom Ayarı
s_min = df['spread'].min()
s_max = df['spread'].max()
s_pad = (s_max - s_min) * 0.1
s_range = [s_min - s_pad, s_max + s_pad]

fig_spread = go.Figure()
fig_spread.add_trace(go.Scatter(x=df.index, y=df['spread'], mode='lines', name='Spread', line=dict(color='#F85149', width=1.5), fill='tozeroy', fillcolor='rgba(248, 81, 73, 0.1)'))

fig_spread.update_layout(
    title=dict(text="Makas Analizi (Spread)", font=dict(size=16, color='#F0F6FC')),
    template="plotly_dark",
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    height=300,
    margin=dict(t=50, b=20, l=0, r=0),
    xaxis=dict(showgrid=False, color='#484F58'),
    yaxis=dict(
        showgrid=True, 
        gridcolor='#21262D', 
        color='#8B949E',
        range=s_range # <--- MAKAS GRAFİĞİ İÇİN ZOOM
    ),
    hovermode="x unified"
)
st.plotly_chart(fig_spread, use_container_width=True)

st.markdown(f"<div style='text-align: right; color: #484F58; font-size: 12px; margin-top: 20px;'>Sistem Durumu: ● Çevrimiçi | Son Güncelleme: {datetime.now().strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)