"""
🏠 Real Estate Market Intelligence
Interactive home buyer search platform powered by Zillow data + dbt + Databricks

Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
from databricks import sql
import plotly.express as px
import plotly.graph_objects as go

# ============================================================
# CONFIG
# ============================================================
st.set_page_config(
    page_title="Real Estate Market Intelligence",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATABRICKS_HOST = st.secrets["databricks"]["host"]
DATABRICKS_HTTP_PATH = st.secrets["databricks"]["http_path"]
DATABRICKS_TOKEN = st.secrets["databricks"]["token"]

# ============================================================
# DATABASE CONNECTION
# ============================================================
@st.cache_resource
def get_connection():
    return sql.connect(
        server_hostname=DATABRICKS_HOST,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN
    )

@st.cache_data(ttl=600)
def run_query(query):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    return pd.DataFrame(rows, columns=columns)

# ============================================================
# LOAD DATA
# ============================================================
@st.cache_data(ttl=600)
def load_market_data():
    return run_query("""
        SELECT * FROM dbt_hari.realestate_marts.market_intelligence
    """)

@st.cache_data(ttl=600)
def load_investment_data():
    return run_query("""
        SELECT * FROM dbt_hari.realestate_marts.investment_hotspots
    """)

@st.cache_data(ttl=600)
def load_metro_data():
    return run_query("""
        SELECT * FROM dbt_hari.realestate_marts.area_comparison
    """)

# ============================================================
# SIDEBAR FILTERS
# ============================================================
st.sidebar.image("https://img.icons8.com/color/96/000000/home.png", width=60)
st.sidebar.title("🔍 Search Filters")

# Load data
with st.spinner("Loading market data from Databricks..."):
    df = load_market_data()
    df_invest = load_investment_data()
    df_metro = load_metro_data()

# State filter
states = sorted(df['state'].dropna().unique())
selected_states = st.sidebar.multiselect("📍 State", states, default=[])

# Metro filter
if selected_states:
    metros = sorted(df[df['state'].isin(selected_states)]['metro'].dropna().unique())
else:
    metros = sorted(df['metro'].dropna().unique())
selected_metros = st.sidebar.multiselect("🏙️ Metro Area", metros, default=[])

# Price range
st.sidebar.subheader("💰 Price Range")
min_price = int(df['home_value'].min()) if not df['home_value'].isna().all() else 0
max_price = int(df['home_value'].max()) if not df['home_value'].isna().all() else 1000000
price_range = st.sidebar.slider(
    "Home Value ($)",
    min_value=min_price,
    max_value=min(max_price, 2000000),
    value=(min_price, min(500000, max_price)),
    step=10000,
    format="$%d"
)

# Score filters
st.sidebar.subheader("⭐ Minimum Scores")
min_livability = st.sidebar.slider("Livability Score", 0, 100, 0)
min_neighborhood = st.sidebar.slider("Neighborhood Score", 0, 100, 0)
min_school = st.sidebar.slider("School Score", 0, 100, 0)

# Yield filter
st.sidebar.subheader("📈 Rental Yield")
min_yield = st.sidebar.slider("Minimum Gross Yield (%)", 0.0, 15.0, 0.0, 0.5)

# Apply filters
filtered = df.copy()
if selected_states:
    filtered = filtered[filtered['state'].isin(selected_states)]
if selected_metros:
    filtered = filtered[filtered['metro'].isin(selected_metros)]
filtered = filtered[
    (filtered['home_value'] >= price_range[0]) &
    (filtered['home_value'] <= price_range[1]) &
    (filtered['livability_score'] >= min_livability) &
    (filtered['neighborhood_score'] >= min_neighborhood) &
    (filtered['school_score'] >= min_school)
]
if min_yield > 0:
    filtered = filtered[filtered['gross_rental_yield'] >= min_yield]

# ============================================================
# MAIN CONTENT
# ============================================================
st.title("🏠 Real Estate Market Intelligence")
st.caption("Powered by Zillow ZHVI/ZORI • dbt • Databricks | Real-time analytics across 26K+ ZIP codes")

# KPI Row
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("ZIP Codes", f"{len(filtered):,}")
with col2:
    avg_value = filtered['home_value'].mean()
    st.metric("Avg Home Value", f"${avg_value:,.0f}" if not pd.isna(avg_value) else "N/A")
with col3:
    avg_rent = filtered['monthly_rent'].mean()
    st.metric("Avg Monthly Rent", f"${avg_rent:,.0f}" if not pd.isna(avg_rent) else "N/A")
with col4:
    avg_yield = filtered['gross_rental_yield'].mean()
    st.metric("Avg Rental Yield", f"{avg_yield:.2f}%" if not pd.isna(avg_yield) else "N/A")
with col5:
    avg_livability = filtered['livability_score'].mean()
    st.metric("Avg Livability", f"{avg_livability:.1f}" if not pd.isna(avg_livability) else "N/A")

st.divider()

# ============================================================
# TAB LAYOUT
# ============================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "🏘️ Buyer Search", "📊 Investment Hotspots", "🏙️ Metro Comparison", "📈 Trends"
])

# ----- TAB 1: BUYER SEARCH -----
with tab1:
    st.subheader("Top ZIP Codes by Livability Score")

    # Results table
    display_cols = [
        'zip_code', 'city', 'state', 'metro', 'home_value', 'monthly_rent',
        'gross_rental_yield', 'price_change_1yr_pct', 'neighborhood_score',
        'school_score', 'livability_score', 'livability_tier', 'metro_rank'
    ]
    available_cols = [c for c in display_cols if c in filtered.columns]
    results = filtered[available_cols].sort_values('livability_score', ascending=False).head(50)

    st.dataframe(
        results,
        use_container_width=True,
        height=400,
        column_config={
            "home_value": st.column_config.NumberColumn("Home Value", format="$%d"),
            "monthly_rent": st.column_config.NumberColumn("Monthly Rent", format="$%d"),
            "gross_rental_yield": st.column_config.NumberColumn("Yield %", format="%.2f%%"),
            "price_change_1yr_pct": st.column_config.NumberColumn("1yr Change %", format="%.2f%%"),
            "neighborhood_score": st.column_config.NumberColumn("Nbhd Score", format="%.1f"),
            "school_score": st.column_config.NumberColumn("School Score", format="%.1f"),
            "livability_score": st.column_config.NumberColumn("Livability", format="%.1f"),
        }
    )

    # Charts row
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Livability Score Distribution")
        if len(filtered) > 0:
            fig = px.histogram(
                filtered, x='livability_score', nbins=30,
                color='livability_tier',
                color_discrete_sequence=px.colors.qualitative.Set2,
                labels={'livability_score': 'Livability Score', 'count': 'ZIP Codes'}
            )
            fig.update_layout(height=350, showlegend=True, legend_title="Tier")
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Price vs Rental Yield")
        if len(filtered) > 0:
            sample = filtered.dropna(subset=['home_value', 'gross_rental_yield']).head(500)
            if len(sample) > 0:
                fig = px.scatter(
                    sample, x='home_value', y='gross_rental_yield',
                    color='livability_tier',
                    hover_data=['zip_code', 'city', 'state'],
                    labels={'home_value': 'Home Value ($)', 'gross_rental_yield': 'Gross Yield (%)'},
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

# ----- TAB 2: INVESTMENT HOTSPOTS -----
with tab2:
    st.subheader("🔥 Investment Hotspots — Buy Signals")

    # Filter investment data
    inv_filtered = df_invest.copy()
    if selected_states:
        inv_filtered = inv_filtered[inv_filtered['state'].isin(selected_states)]
    if selected_metros:
        inv_filtered = inv_filtered[inv_filtered['metro'].isin(selected_metros)]

    # Signal counts
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        count = len(inv_filtered[inv_filtered['investment_signal'] == 'STRONG BUY'])
        st.metric("🟢 STRONG BUY", count)
    with col2:
        count = len(inv_filtered[inv_filtered['investment_signal'] == 'BUY'])
        st.metric("🔵 BUY", count)
    with col3:
        count = len(inv_filtered[inv_filtered['investment_signal'] == 'HOLD'])
        st.metric("🟡 HOLD", count)
    with col4:
        count = len(inv_filtered[inv_filtered['investment_signal'] == 'WATCH'])
        st.metric("🔴 WATCH", count)

    # Top investments table
    st.subheader("Top 30 Investment Opportunities")
    inv_display = inv_filtered.sort_values('investment_score', ascending=False).head(30)
    inv_cols = ['zip_code', 'city', 'state', 'metro', 'home_value', 'monthly_rent',
                'gross_rental_yield', 'annual_appreciation_rate', 'investment_score',
                'cash_on_cash_estimate', 'investment_signal']
    available_inv_cols = [c for c in inv_cols if c in inv_display.columns]

    st.dataframe(
        inv_display[available_inv_cols],
        use_container_width=True,
        height=400,
        column_config={
            "home_value": st.column_config.NumberColumn("Home Value", format="$%d"),
            "monthly_rent": st.column_config.NumberColumn("Rent/mo", format="$%d"),
            "gross_rental_yield": st.column_config.NumberColumn("Yield %", format="%.2f%%"),
            "annual_appreciation_rate": st.column_config.NumberColumn("Apprec %", format="%.2f%%"),
            "investment_score": st.column_config.NumberColumn("Inv Score", format="%.1f"),
            "cash_on_cash_estimate": st.column_config.NumberColumn("Cash/Cash %", format="%.2f%%"),
        }
    )

    # Investment signal distribution
    col_left, col_right = st.columns(2)
    with col_left:
        fig = px.pie(
            inv_filtered, names='investment_signal',
            title="Investment Signal Distribution",
            color='investment_signal',
            color_discrete_map={
                'STRONG BUY': '#00CC66', 'BUY': '#3399FF',
                'HOLD': '#FFCC00', 'WATCH': '#FF6666'
            }
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        if len(inv_filtered) > 0:
            fig = px.scatter(
                inv_filtered.head(300), x='gross_rental_yield', y='annual_appreciation_rate',
                color='investment_signal', size='investment_score',
                hover_data=['zip_code', 'city'],
                title="Yield vs Appreciation",
                labels={'gross_rental_yield': 'Rental Yield (%)', 'annual_appreciation_rate': 'Appreciation (%)'},
                color_discrete_map={
                    'STRONG BUY': '#00CC66', 'BUY': '#3399FF',
                    'HOLD': '#FFCC00', 'WATCH': '#FF6666'
                }
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

# ----- TAB 3: METRO COMPARISON -----
with tab3:
    st.subheader("🏙️ Metro Area Comparison")

    metro_sorted = df_metro.sort_values('avg_livability_score', ascending=False)

    # Top 20 metros bar chart
    top_metros = metro_sorted.head(20)
    fig = px.bar(
        top_metros, x='metro', y='avg_livability_score',
        color='avg_rental_yield',
        color_continuous_scale='RdYlGn',
        title="Top 20 Metros by Livability Score (colored by rental yield)",
        labels={'avg_livability_score': 'Avg Livability Score', 'avg_rental_yield': 'Avg Yield %'}
    )
    fig.update_layout(height=450, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    # Metro comparison table
    metro_cols = ['metro', 'zip_count', 'median_home_value', 'avg_monthly_rent',
                  'avg_rental_yield', 'avg_appreciation_rate', 'avg_neighborhood_score',
                  'avg_school_score', 'avg_livability_score', 'pct_appreciating']
    available_metro_cols = [c for c in metro_cols if c in metro_sorted.columns]

    st.dataframe(
        metro_sorted[available_metro_cols],
        use_container_width=True,
        height=400,
        column_config={
            "median_home_value": st.column_config.NumberColumn("Median Value", format="$%d"),
            "avg_monthly_rent": st.column_config.NumberColumn("Avg Rent", format="$%d"),
            "avg_rental_yield": st.column_config.NumberColumn("Avg Yield %", format="%.2f%%"),
            "avg_appreciation_rate": st.column_config.NumberColumn("Avg Apprec %", format="%.2f%%"),
            "avg_livability_score": st.column_config.NumberColumn("Livability", format="%.1f"),
            "pct_appreciating": st.column_config.NumberColumn("% Appreciating", format="%.1f%%"),
        }
    )

    # Scatter: value vs yield by metro
    col_left, col_right = st.columns(2)
    with col_left:
        fig = px.scatter(
            metro_sorted.head(50), x='median_home_value', y='avg_rental_yield',
            size='zip_count', hover_data=['metro'],
            title="Home Value vs Rental Yield by Metro",
            labels={'median_home_value': 'Median Home Value ($)', 'avg_rental_yield': 'Avg Yield (%)'}
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        fig = px.bar(
            metro_sorted.head(15), x='metro', y='avg_appreciation_rate',
            color='avg_appreciation_rate', color_continuous_scale='RdYlGn',
            title="Top 15 Metros by Appreciation Rate",
            labels={'avg_appreciation_rate': 'Appreciation Rate (%)'}
        )
        fig.update_layout(height=400, xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

# ----- TAB 4: TRENDS -----
with tab4:
    st.subheader("📈 Price & Yield Trends")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Price Trend Distribution")
        if 'price_trend' in filtered.columns:
            trend_counts = filtered['price_trend'].value_counts().reset_index()
            trend_counts.columns = ['trend', 'count']
            fig = px.bar(
                trend_counts, x='trend', y='count',
                color='trend',
                color_discrete_map={
                    'strong_appreciation': '#00CC66',
                    'moderate_appreciation': '#99CC66',
                    'stable': '#FFCC00',
                    'moderate_decline': '#FF9966',
                    'strong_decline': '#FF3333'
                },
                title="ZIP Codes by Price Trend"
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Yield Tier Distribution")
        if 'yield_tier' in filtered.columns:
            yield_counts = filtered['yield_tier'].dropna().value_counts().reset_index()
            yield_counts.columns = ['tier', 'count']
            fig = px.pie(
                yield_counts, names='tier', values='count',
                title="ZIP Codes by Yield Tier",
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

    # Neighborhood vs School score
    st.subheader("Neighborhood Score vs School Score")
    sample = filtered.dropna(subset=['neighborhood_score', 'school_score']).head(500)
    if len(sample) > 0:
        fig = px.scatter(
            sample, x='neighborhood_score', y='school_score',
            color='livability_tier', hover_data=['zip_code', 'city', 'state'],
            title="Where do the best neighborhoods and schools overlap?",
            labels={'neighborhood_score': 'Neighborhood Score', 'school_score': 'School Score'},
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig.update_layout(height=450)
        st.plotly_chart(fig, use_container_width=True)

# ============================================================
# FOOTER
# ============================================================
st.divider()
st.caption("""
    📊 Data: Zillow ZHVI/ZORI (real), OpenStreetMap amenities, NCES schools |
    🔧 Pipeline: dbt + Databricks |
    📅 Updated: Real-time from Databricks SQL Warehouse
""")
