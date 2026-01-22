import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# ==========================================
# 1. AYARLAR
# ==========================================
st.set_page_config(
    page_title="Gold Market Arbitrage",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 60 Saniyede bir yenile
st_autorefresh(interval=60 * 1000, key="sys_refresh")

# ==========================================
# 2. TASARIM (CSS)
# ==========================================
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    header {visibility: hidden;}
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
    
    div[data-testid="stMetric"] {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 10px 15px;
    }
    [data-testid="stMetricValue"] {
        font-family: 'Inter', sans-serif;
        font-size: 24px !important;
        color: #F0F6FC !important;
    }
    [data-testid="stMetricLabel"] { color: #8B949E !important; font-size: 13px !important; }
    .main-header { font-family: 'Inter', sans-serif; font-weight: 700; color: #F0F6FC; font-size: 22px; margin-bottom: 0px; }
    .sub-header { font-family: 'Inter', sans-serif; color: #8B949E; font-size: 12px; margin-top: -5px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. GERÇEK VERİ MOTORU (7/24 ÇALIŞAN VERSİYON)
# ==========================================

@st.cache_data(ttl=60, show_spinner=False)
def get_real_market_data(period_selection):
    # Yahoo Finance Sembolleri
    tickers = "GC=F TRY=X ALTIN.IS"
    
    period_map = {"1S": "5d", "24S": "5d", "1H": "1mo", "1A": "3mo", "3A": "1y", "1Y": "2y"}
    interval_map = {"1S": "15m", "24S": "30m", "1H": "60m", "1A": "1d", "3A": "1d", "1Y": "1d"}
    
    p = period_map.get(period_selection, "5d")
    i = interval_map.get(period_selection, "15m")

    try:
        # Verileri indir
        data = yf.download(tickers, period=p, interval=i, group_by='ticker', progress=False)

        # Sütunları ayıkla
        df_ons = data['GC=F']['Close'] if 'GC=F' in data else pd.Series()
        df_usd = data['TRY=X']['Close'] if 'TRY=X' in data else pd.Series()
        df_sertifika = data['ALTIN.IS']['Close'] if 'ALTIN.IS' in data else pd.Series()

        # --- KRİTİK DÜZELTME: VERİLERİ BİRLEŞTİR VE DOLDUR ---
        df = pd.DataFrame({
            'Ons': df_ons,
            'Dolar': df_usd,
            'Sertifika_Ham': df_sertifika
        })

        # Gece veya hafta sonu veri eksikse, en son bilinen fiyatı kullan (Forward Fill)
        # Bu sayede gece 3'te bile grafik boş kalmaz.
        df = df.ffill().dropna()

        if df.empty:
            return pd.DataFrame()

        # HESAPLAMALAR
        # 1. Has Altın TL (Teorik)
        df['Fiziki'] = (df['Ons'] * df['Dolar']) / 31.1035
        
        # 2. Sertifika (Gram Dönüşümü)
        # BIST verisi bazen kuruş bazen TL gelir, bunu düzelt:
        last_val = df['Sertifika_Ham'].iloc[-1]
        if last_val < 500: 
            df['Sertifika'] = df['Sertifika_Ham'] * 100
        else:
            df['Sertifika'] = df['Sertifika_Ham']

        df['Makas'] = df['Fiziki'] - df['Sertifika']
        
        # Seçilen zaman dilimine göre kes (Slice)
        if period_selection == "1S":
            df = df.tail(96) # Son 24 saat (15dk * 4 * 24)
        elif period_selection == "24S":
            df = df.tail(48) 

        return df

    except Exception as e:
        print(f"Hata: {e}")
        return pd.DataFrame()

# ==========================================
# 4. ARAYÜZ
# ==========================================

col_logo, col_title, col_time = st.columns([0.1, 6, 3])

with col_title:
    st.markdown("<h2 class='main-header'>Altın Arbitraj Paneli</h2>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Canlı Global Ons & BIST Verisi • Real-Time Data</p>", unsafe_allow_html=True)

with col_time:
    time_options = ["1S", "24S", "1H", "1A", "3A", "1Y"]
    selected_time = st.radio("Zaman", time_options, horizontal=True, label_visibility="collapsed")

# Veriyi Çek
df = get_real_market_data(selected_time)

if not df.empty:
    curr = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else df.iloc[0]

    # KPI Kartları
    c1, c2, c3 = st.columns(3)
    with c1: 
        st.metric("Sertifika (BIST)", f"{curr['Sertifika']:,.2f} ₺", f"{curr['Sertifika'] - prev['Sertifika']:.2f} ₺")
    with c2: 
        st.metric("Has Altın (Global Hesap)", f"{curr['Fiziki']:,.2f} ₺", f"{curr['Fiziki'] - prev['Fiziki']:.2f} ₺", delta_color="off")
    with c3: 
        st.metric("Teorik Makas", f"{curr['Makas']:.2f} ₺", f"{curr['Makas'] - prev['Makas']:.2f} ₺", delta_color="inverse")

    st.markdown("---")

    # Grafik Ayarları (Auto Zoom)
    y_min = min(df['Sertifika'].min(), df['Fiziki'].min())
    y_max = max(df['Sertifika'].max(), df['Fiziki'].max())
    padding = (y_max - y_min) * 0.1
    y_range = [y_min - padding, y_max + padding]

    # Grafik 1: Fiyatlar
    fig_price = go.Figure()
    fig_price.add_trace(go.Scatter(x=df.index, y=df['Sertifika'], mode='lines', name='BIST Sertifika', line=dict(color='#2f81f7', width=2)))
    fig_price.add_trace(go.Scatter(x=df.index, y=df['Fiziki'], mode='lines', name='Global Has Altın', line=dict(color='#D29922', width=2)))

    fig_price.update_layout(
        title=dict(text="Fiyat Karşılaştırması", font=dict(size=14, color='#F0F6FC')),
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=320,
        margin=dict(t=30, b=10, l=0, r=0),
        xaxis=dict(showgrid=False, color='#484F58'),
        yaxis=dict(showgrid=True, gridcolor='#21262D', color='#8B949E', range=y_range),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1, x=0, font=dict(color='#C9D1D9', size=10))
    )
    st.plotly_chart(fig_price, use_container_width=True)

    # Grafik 2: Makas
    fig_spread = go.Figure()
    fig_spread.add_trace(go.Scatter(x=df.index, y=df['Makas'], mode='lines', name='Spread', line=dict(color='#F85149', width=1.5), fill='tozeroy', fillcolor='rgba(248, 81, 73, 0.1)'))

    fig_spread.update_layout(
        title=dict(text="Arbitraj Marjı (Spread)", font=dict(size=14, color='#F0F6FC')),
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=200,
        margin=dict(t=30, b=10, l=0, r=0),
        xaxis=dict(showgrid=False, color='#484F58'),
        yaxis=dict(showgrid=True, gridcolor='#21262D', color='#8B949E'),
        hovermode="x unified"
    )
    st.plotly_chart(fig_spread, use_container_width=True)

else:
    # Veri yine boş gelirse diye yedek mesaj
    st.info("Piyasa verileri yükleniyor... Eğer bu mesaj gitmiyorsa piyasalar kapalı olabilir (02:00 - 09:00 arası veri akışı yavaştır).")
    
st.markdown(f"<div style='text-align: right; color: #484F58; font-size: 11px; margin-top: 10px;'>Kaynak: Yahoo Finance (Live) | Hesaplama: (Ons x Dolar)/31.1</div>", unsafe_allow_html=True)