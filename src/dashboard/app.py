import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
from pathlib import Path
from streamlit_lightweight_charts import renderLightweightCharts
import logging
from datetime import timedelta

# Add project root to sys.path to allow imports from src
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR
from src.utils.logger import setup_logging
from src.data.price_fetcher import fetch_and_save_price
from src.data.price_fetcher_coingecko import fetch_and_save_price_coingecko
from src.data.attention_fetcher import fetch_zec_news, save_attention_data
from src.features.attention_features import process_attention_features

# 页面配置
st.set_page_config(page_title="Crypto Attention Lab | ZEC Analysis", layout="wide", initial_sidebar_state="collapsed")
setup_logging(logging.INFO)

# Timeframe mapping
TIMEFRAME_MAP = {
    "1D": "1d",
    "4H": "4h",
    "1H": "1h",
    "15M": "15m"
}

TIMEFRAME_LIMITS = {
    "1d": 365,
    "4h": 180,
    "1h": 120,
    "15m": 96
}


# ==================== Helper Functions ====================

def load_raw_news_df():
    """Load raw news data for display"""
    news_file = RAW_DATA_DIR / "attention_zec_news.csv"
    if not news_file.exists():
        news_file = RAW_DATA_DIR / "attention_zec_mock.csv"
    if not news_file.exists():
        return None
    df_news = pd.read_csv(news_file)
    if 'datetime' in df_news.columns:
        df_news['datetime'] = pd.to_datetime(df_news['datetime'], errors='coerce')
    return df_news


@st.cache_data
def load_data(timeframe='1d'):
    """Load price and attention data for specified timeframe"""
    safe_symbol = "ZECUSDT"
    price_file_main = RAW_DATA_DIR / f"price_{safe_symbol}_{timeframe}.csv"
    price_file_fallback = RAW_DATA_DIR / f"price_{safe_symbol}_{timeframe}_fallback.csv"
    attention_file = PROCESSED_DATA_DIR / "attention_features_zec.csv"

    # Load price data
    if price_file_main.exists():
        price_file = price_file_main
        price_source = st.session_state.get('price_source', 'Local (primary)')
    elif price_file_fallback.exists():
        price_file = price_file_fallback
        price_source = 'Fallback (synthetic)'
    else:
        return None, None, None, None

    # Load attention data
    if not attention_file.exists():
        return None, None, None, None

    df_price = pd.read_csv(price_file)
    df_price['datetime'] = pd.to_datetime(df_price['datetime'], utc=True, errors='coerce').dt.tz_localize(None)
    
    df_attention = pd.read_csv(attention_file)
    df_attention['datetime'] = pd.to_datetime(df_attention['datetime'], utc=True, errors='coerce').dt.tz_localize(None)
    
    return df_price, df_attention, str(price_file), price_source


def render_top_summary(df_price, df_attention):
    """Render top summary cards with key metrics"""
    if df_price is None or df_price.empty:
        st.warning("No data available")
        return
    
    # Get latest values
    latest_price = df_price.iloc[-1]
    prev_price = df_price.iloc[-2] if len(df_price) > 1 else latest_price
    
    price_change = ((latest_price['close'] - prev_price['close']) / prev_price['close'] * 100) if prev_price['close'] != 0 else 0
    latest_volume = latest_price.get('volume', 0)
    
    # Get today's attention metrics
    today = pd.Timestamp.now().normalize()
    today_attention = df_attention[df_attention['datetime'].dt.normalize() == today]
    avg_attention = today_attention['attention_score'].mean() if not today_attention.empty else 0
    
    # Get today's news count from raw news
    df_news = load_raw_news_df()
    news_count_today = 0
    if df_news is not None:
        news_today = df_news[df_news['datetime'].dt.normalize() == today]
        news_count_today = len(news_today)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="ZEC Price",
            value=f"${latest_price['close']:.2f}",
            delta=f"{price_change:+.2f}%"
        )
    
    with col2:
        st.metric(
            label="24h Volume",
            value=f"{latest_volume:,.0f}"
        )
    
    with col3:
        st.metric(
            label="Today Attention",
            value=f"{avg_attention:.1f}/100"
        )
    
    with col4:
        st.metric(
            label="Today News Count",
            value=f"{news_count_today}"
        )


def render_middle_panels(df_price, df_attention, df_news, start_date, end_date):
    """Render middle information panels"""
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.subheader("📊 Price Overview (Last 90 Days)")
        if df_price is not None and not df_price.empty:
            # Show last 90 days mini chart
            df_mini = df_price.tail(90).copy()
            fig_mini = go.Figure()
            fig_mini.add_trace(go.Scatter(
                x=df_mini['datetime'],
                y=df_mini['close'],
                mode='lines',
                fill='tozeroy',
                line=dict(color='#3b82f6', width=2),
                name='Price'
            ))
            fig_mini.update_layout(
                height=200,
                margin=dict(l=0, r=0, t=0, b=0),
                showlegend=False,
                xaxis=dict(showgrid=False, showticklabels=False),
                yaxis=dict(showgrid=True, gridcolor='#1f2937'),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_mini, width='stretch')
    
    with col_right:
        st.subheader("📰 Recent News")
        if df_news is not None and not df_news.empty:
            mask_news = (df_news['datetime'].dt.date >= start_date) & (df_news['datetime'].dt.date <= end_date)
            df_news_sel = df_news.loc[mask_news].copy()
            df_news_sel = df_news_sel.sort_values('datetime', ascending=False).head(8)
            
            for _, row in df_news_sel.iterrows():
                time_str = row['datetime'].strftime('%m-%d %H:%M') if pd.notna(row['datetime']) else 'N/A'
                source = row.get('source', 'Unknown')
                title = row.get('title', 'No title')
                title_short = title[:60] + '...' if len(title) > 60 else title
                st.caption(f"**{time_str}** | {source}")
                st.text(title_short)
                st.divider()
        else:
            st.info("No news available. Click 'Refresh Data' to fetch.")


def render_main_charts(df_filtered, timeframe_label):
    """Render main TradingView-style charts"""
    if df_filtered is None or df_filtered.empty:
        st.warning("No data to display")
        return
    
    def to_unix_sec(ts):
        try:
            return int(pd.Timestamp(ts).timestamp())
        except Exception:
            return None

    candle_data = []
    volume_data = []
    for _, row in df_filtered.dropna(subset=['open','high','low','close']).iterrows():
        t = to_unix_sec(row['datetime'])
        if t is None:
            continue
        candle_data.append({
            'time': t,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
        })
        if 'volume' in row and pd.notna(row['volume']):
            color = 'rgba(38,166,154,0.5)' if row['close'] >= row['open'] else 'rgba(239,83,80,0.5)'
            volume_data.append({'time': t, 'value': float(row['volume']), 'color': color})

    attention_data = []
    if 'attention_score' in df_filtered.columns:
        for _, row in df_filtered.dropna(subset=['attention_score']).iterrows():
            t = to_unix_sec(row['datetime'])
            if t is None:
                continue
            attention_data.append({'time': t, 'value': float(row['attention_score'])})

    charts = [
        {
            'height': 480,
            'layout': {
                'background': {'type': 'solid', 'color': '#050816'},
                'textColor': '#e5e7eb',
            },
            'grid': {
                'vertLines': {'color': '#1f2937'},
                'horzLines': {'color': '#1f2937'}
            },
            'timeScale': {'timeVisible': True, 'secondsVisible': False},
            'series': [
                {'type': 'Candlestick', 'data': candle_data, 'priceScaleId': 'right'},
                {'type': 'Histogram', 'data': volume_data, 'priceScaleId': '', 'scaleMargins': {'top': 0.85, 'bottom': 0}},
            ],
        },
        {
            'height': 200,
            'layout': {
                'background': {'type': 'solid', 'color': '#050816'},
                'textColor': '#e5e7eb',
            },
            'grid': {
                'vertLines': {'color': '#1f2937'},
                'horzLines': {'color': '#1f2937'}
            },
            'timeScale': {'timeVisible': True, 'secondsVisible': False},
            'series': [
                {'type': 'Line', 'data': attention_data, 'color': '#f59e0b', 'lineWidth': 2},
            ],
        },
    ]

    renderLightweightCharts(charts, key=f"tv_charts_{timeframe_label}")



# ==================== Main Application ====================

st.title("🕵️ Crypto Attention Lab: ZEC Analysis")

# Timeframe selector
st.subheader("⏱️ Select Timeframe")
timeframe_options = list(TIMEFRAME_MAP.keys())
selected_tf = st.radio("Timeframe:", timeframe_options, index=0, horizontal=True, key="timeframe_selector")
timeframe_label = TIMEFRAME_MAP[selected_tf]

# Refresh data button
with st.sidebar:
    st.header("🔄 Data Management")
    
    if st.button("Refresh Data", type="primary", width='stretch'):
        with st.spinner(f"Fetching ZEC/{selected_tf} data..."):
            # Clear cache
            load_data.clear()
            
            symbol = "ZEC/USDT"
            limit = TIMEFRAME_LIMITS[selected_tf]
            
            # Fetch price data
            try:
                filepath, is_fallback = fetch_and_save_price(
                    symbol=symbol,
                    timeframe=timeframe_label,
                    limit=limit,
                    max_retries=3
                )
                if is_fallback:
                    st.session_state['price_source'] = 'Fallback (synthetic)'
                    st.warning(f"⚠️ Used fallback data for {selected_tf}")
                else:
                    st.session_state['price_source'] = 'Binance/CoinGecko'
                    st.success(f"✅ Price data ({selected_tf}) fetched successfully")
            except Exception as e:
                st.error(f"❌ Failed to fetch price data: {e}")
            
            # Fetch news data (only for 1D)
            if selected_tf == "1 Day":
                try:
                    news_list = fetch_zec_news()
                    save_attention_data(news_list)
                    st.success(f"✅ News data fetched: {len(news_list)} items")
                except Exception as e:
                    st.error(f"❌ Failed to fetch news: {e}")
                
                # Process attention features
                try:
                    process_attention_features()
                    st.success("✅ Attention features processed")
                except Exception as e:
                    st.error(f"❌ Failed to process features: {e}")

# Load data
df_price, df_attention, price_file_path, price_source = load_data(timeframe_label)
df_news = load_raw_news_df()

if df_price is None or df_attention is None:
    st.warning("⚠️ No data available. Click 'Refresh Data' to fetch.")
    st.stop()

# Display data source info in sidebar
with st.sidebar:
    st.divider()
    st.caption(f"**Price Source:** {price_source}")
    st.caption(f"**Timeframe:** {selected_tf}")
    st.caption(f"**Data Points:** {len(df_price)}")

# ==================== Layer 1: Top Summary Cards ====================
st.markdown("---")
render_top_summary(df_price, df_attention)

# ==================== Layer 2: Middle Info Panels ====================
st.markdown("---")

# Date range selector
col_date1, col_date2 = st.columns(2)
with col_date1:
    min_date = df_price['datetime'].min().date()
    max_date = df_price['datetime'].max().date()
    # Calculate default start date, but ensure it's not before min_date
    default_start = max_date - timedelta(days=30)
    if default_start < min_date:
        default_start = min_date
    start_date = st.date_input("Start Date", value=default_start, min_value=min_date, max_value=max_date)
with col_date2:
    end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)

if start_date > end_date:
    st.error("Start date must be before end date")
    st.stop()

render_middle_panels(df_price, df_attention, df_news, start_date, end_date)

# ==================== Layer 3: Main Charts ====================
st.markdown("---")
st.subheader(f"📈 Price & Attention Analysis ({selected_tf})")

# Merge price and attention data
df_merged = pd.merge(df_price, df_attention, on='datetime', how='left')

# Filter by date range
mask = (df_merged['datetime'].dt.date >= start_date) & (df_merged['datetime'].dt.date <= end_date)
df_filtered = df_merged.loc[mask].copy()

render_main_charts(df_filtered, timeframe_label)

# ==================== Additional: News Table ====================
st.markdown("---")
st.subheader("📰 News Details")

if df_news is not None and not df_news.empty:
    mask_news = (df_news['datetime'].dt.date >= start_date) & (df_news['datetime'].dt.date <= end_date)
    df_news_display = df_news.loc[mask_news].copy()
    df_news_display = df_news_display.sort_values('datetime', ascending=False)
    df_news_display['datetime'] = df_news_display['datetime'].dt.strftime('%Y-%m-%d %H:%M')
    
    st.dataframe(
        df_news_display[['datetime', 'source', 'title', 'url']],
        width='stretch',
        column_config={
            "datetime": "Time",
            "source": "Source",
            "title": "Title",
            "url": st.column_config.LinkColumn("Link", display_text="View")
        },
        hide_index=True
    )
else:
    st.info("No news data available. Click 'Refresh Data' to fetch news.")

st.markdown("---")
st.caption("💡 Crypto Attention Lab | Analyzing the relationship between news attention and price movements")



# Sidebar: 控制面板
st.sidebar.header("Controls")

if st.sidebar.button("🔄 Refresh Data"):
    with st.spinner("Fetching new data..."):
        # 1. Try fetch Price from Binance (may fail due to network/proxy)
        try:
            _res = fetch_and_save_price(limit=365)
            if isinstance(_res, tuple):
                price_path, is_fallback = _res
            else:
                price_path, is_fallback = _res, (isinstance(_res, str) and 'fallback' in _res)
        except Exception as e:
            st.sidebar.warning(f"Binance fetch raised an error: {e}")
            price_path, is_fallback = None, True

        # If Binance failed or returned fallback, try CoinGecko as a robust backup
        if (not price_path) or is_fallback:
            try:
                cg_path = fetch_and_save_price_coingecko(days=365)
                st.sidebar.info("Used CoinGecko as fallback for price data.")
                price_path = cg_path
                st.session_state['price_source'] = 'CoinGecko'
            except Exception as e:
                st.sidebar.error(f"CoinGecko fetch also failed: {e}")
        else:
            # Binance succeeded (may still be fallback path if synthetic) — mark accordingly
            if is_fallback:
                st.session_state['price_source'] = 'Fallback (synthetic)'
            else:
                st.session_state['price_source'] = 'Binance'
        if price_path:
            st.session_state['price_path'] = price_path

        # 2. Fetch Attention (Mock)
        news = fetch_zec_news()
        save_attention_data(news)
        # 3. Process Features
        process_attention_features()
    st.sidebar.success("Data updated!")

# 加载数据
@st.cache_data
def load_data():
    price_file_main = RAW_DATA_DIR / "price_ZECUSDT_1d.csv"
    price_file_fallback = RAW_DATA_DIR / "price_ZECUSDT_1d_fallback.csv"
    attention_file = PROCESSED_DATA_DIR / "attention_features_zec.csv"

    # 优先使用真实抓取文件，找不到则使用回退合成数据
    if price_file_main.exists():
        price_file = price_file_main
        price_source = st.session_state.get('price_source', 'Local (primary)')
    elif price_file_fallback.exists():
        price_file = price_file_fallback
        price_source = 'Fallback (synthetic)'
    else:
        return None, None, None, None

    if not attention_file.exists():
        return None, None, None, None

    df_price = pd.read_csv(price_file)
    df_price['datetime'] = pd.to_datetime(df_price['datetime'], utc=True, errors='coerce').dt.tz_localize(None)
    
    df_attention = pd.read_csv(attention_file)
    df_attention['datetime'] = pd.to_datetime(df_attention['datetime'], utc=True, errors='coerce').dt.tz_localize(None)
    
    return df_price, df_attention, str(price_file), price_source

df_price, df_attention, price_path, price_source = load_data()

if df_price is None or df_attention is None:
    st.warning("Data not found. Please click 'Refresh Data' in the sidebar.")
else:
    with st.sidebar:
        st.caption("Price Data Source")
        st.code(f"{price_source}\n{price_path}")

    # 合并数据以便绘图 (按日期对齐)
    # 注意：价格数据可能包含周末，新闻数据也是连续的
    df_merged = pd.merge(df_price, df_attention, on='datetime', how='outer').sort_values('datetime')
    
    # 过滤时间范围
    min_date = df_merged['datetime'].min()
    max_date = df_merged['datetime'].max()
    
    # 确保 min_date 和 max_date 是 datetime.date 对象，用于 slider
    start_date, end_date = st.slider(
        "Select Date Range",
        min_value=min_date.date(),
        max_value=max_date.date(),
        value=(min_date.date(), max_date.date())
    )
    
    mask = (df_merged['datetime'].dt.date >= start_date) & (df_merged['datetime'].dt.date <= end_date)
    df_filtered = df_merged.loc[mask]

    # 使用 TradingView 风格的 lightweight-charts 绘制
    def to_unix_sec(ts):
        try:
            return int(pd.Timestamp(ts).timestamp())
        except Exception:
            return None

    candle_data = []
    volume_data = []
    for _, row in df_filtered.dropna(subset=['open','high','low','close']).iterrows():
        t = to_unix_sec(row['datetime'])
        if t is None:
            continue
        candle_data.append({
            'time': t,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
        })
        if 'volume' in row and pd.notna(row['volume']):
            color = 'rgba(38,166,154,0.5)' if row['close'] >= row['open'] else 'rgba(239,83,80,0.5)'
            volume_data.append({'time': t, 'value': float(row['volume']), 'color': color})

    attention_data = []
    if 'attention_score' in df_filtered.columns:
        for _, row in df_filtered.dropna(subset=['attention_score']).iterrows():
            t = to_unix_sec(row['datetime'])
            if t is None:
                continue
            attention_data.append({'time': t, 'value': float(row['attention_score'])})

    charts = [
        {
            'height': 520,
            'layout': {
                'background': {'type': 'solid', 'color': '#0f1116'},
                'textColor': '#DDE2EB',
            },
            'grid': {
                'vertLines': {'color': '#1f2430'},
                'horzLines': {'color': '#1f2430'}
            },
            'timeScale': {'timeVisible': True, 'secondsVisible': False},
            'series': [
                {'type': 'Candlestick', 'data': candle_data, 'priceScaleId': 'right'},
                {'type': 'Histogram', 'data': volume_data, 'priceScaleId': '', 'scaleMargins': {'top': 0.85, 'bottom': 0}},
            ],
        },
        {
            'height': 260,
            'layout': {
                'background': {'type': 'solid', 'color': '#0f1116'},
                'textColor': '#DDE2EB',
            },
            'grid': {
                'vertLines': {'color': '#1f2430'},
                'horzLines': {'color': '#1f2430'}
            },
            'timeScale': {'timeVisible': True, 'secondsVisible': False},
            'series': [
                {'type': 'Line', 'data': attention_data, 'color': '#f4a261', 'lineWidth': 2},
            ],
        },
    ]

    renderLightweightCharts(charts, key="tv_charts")

    # 加载新闻原始数据用于概览
    def load_raw_news_df():
        news_file = RAW_DATA_DIR / "attention_zec_news.csv"
        if not news_file.exists():
            news_file = RAW_DATA_DIR / "attention_zec_mock.csv"
        if not news_file.exists():
            return None
        df_news = pd.read_csv(news_file)
        if 'datetime' in df_news.columns:
            df_news['datetime'] = pd.to_datetime(df_news['datetime'], errors='coerce')
        return df_news

    df_news = load_raw_news_df()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Recent Price Data")
        st.dataframe(df_price.tail())
    with col2:
        st.subheader("Recent Attention Data")
        st.dataframe(df_attention.tail())

    # 新闻概览（按当前选择时间范围过滤）
    st.subheader("News Overview (in selected range)")
    if df_news is not None and not df_news.empty:
        mask_news = (df_news['datetime'].dt.date >= start_date) & (df_news['datetime'].dt.date <= end_date)
        df_news_sel = df_news.loc[mask_news].copy()
        df_news_sel = df_news_sel.sort_values('datetime', ascending=False)
        show_cols = [c for c in ['datetime', 'source', 'title', 'url'] if c in df_news_sel.columns]
        st.dataframe(df_news_sel[show_cols].head(30))
    else:
        st.info("No news available. Click 'Refresh Data' to fetch.")
