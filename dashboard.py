import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')
import logging
logger = logging.getLogger(__name__)

# Optional click-based plotly events (streamlit-plotly-events)
try:
    from streamlit_plotly_events import plotly_events
    HAVE_PLOTLY_EVENTS = True
except Exception:
    plotly_events = None
    HAVE_PLOTLY_EVENTS = False

# Page config
st.set_page_config(
    page_title="Trading Journal Dashboard",
    layout="wide",
    page_icon="📊",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #ff4b4b;
    }
    .positive {
        border-left-color: #00cc44 !important;
    }
    .negative {
        border-left-color: #ff4b4b !important;
    }
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state with better defaults
session_state_defaults = {
    'selected_date': None,
    'selected_broker': None,
    'selected_underlying': None,
    'date_filter': None,
    'selected_trade_type': None,
    'selected_fund_type': None,
    'show_advanced': False
}

for key, default in session_state_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Sidebar for global controls
st.sidebar.title("🎛️ Controls")

# Theme selector
theme = st.sidebar.selectbox("Theme", ["Light", "Dark"], index=0)
if theme == "Dark":
    st.markdown("""
    <style>
        .stApp { background-color: #0e1117; color: white; }
        .metric-card { background-color: #262730; color: white; }
    </style>
    """, unsafe_allow_html=True)

# Data loading with error handling
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data():
    """Load all data files with proper error handling"""
    data = {}

    # File paths
    files = {
        'trades': 'trades.csv',
        'funds': 'funds_transactions.csv',
        'pledges': 'pledges.csv',
        'summary': 'account_summary.csv'
    }

    for key, filename in files.items():
        if os.path.exists(filename):
            try:
                df = pd.read_csv(filename)

                # Convert date columns
                date_columns = [col for col in df.columns if 'date' in col.lower() or col in ['Date', 'Expiry']]
                for col in date_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')

                # Data validation
                if key == 'trades':
                    required_cols = ['Date', 'Net Total']
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    if missing_cols:
                        st.error(f"Missing required columns in trades.csv: {missing_cols}")
                        df = pd.DataFrame()
                    else:
                        # Add calculated columns
                        df['Trade_Result'] = df['Net Total'].apply(lambda x: 'Win' if x > 0 else 'Loss' if x < 0 else 'Break-even')
                        df['Abs_PnL'] = df['Net Total'].abs()
                        df['Day_of_Week'] = df['Date'].dt.day_name()
                        df['Month'] = df['Date'].dt.month_name()
                        df['Year'] = df['Date'].dt.year

                elif key == 'funds':
                    if 'Currency' not in df.columns:
                        df['Currency'] = df.get('Broker', '').apply(lambda x: 'USD' if str(x).lower() == 'exness' else 'INR')

                data[key] = df
                st.sidebar.success(f"✅ {key.title()}: {len(df)} records")

            except Exception as e:
                st.sidebar.error(f"❌ Error loading {filename}: {str(e)}")
                data[key] = pd.DataFrame()
        else:
            data[key] = pd.DataFrame()
            st.sidebar.warning(f"⚠️ {filename} not found")

    return data

# Load data
data = load_data()
df_trades = data.get('trades', pd.DataFrame())
df_funds = data.get('funds', pd.DataFrame())
df_pledges = data.get('pledges', pd.DataFrame())
df_summary = data.get('summary', pd.DataFrame())

# Load processed files metadata if present
processed_csv = os.path.join(os.getcwd(), 'processed_files.csv')
df_processed = None
if os.path.exists(processed_csv):
    try:
        df_processed = pd.read_csv(processed_csv)
        # Ensure proper datetime
        if 'DownloadedAt' in df_processed.columns:
            try:
                df_processed['DownloadedAt'] = pd.to_datetime(df_processed['DownloadedAt'], errors='coerce')
            except Exception:
                pass
    except Exception as e:
        df_processed = None
        logger.debug(f"Could not read processed_files.csv: {e}")

# Show processed files summary in the sidebar
with st.sidebar.expander("📁 Processed Files", expanded=False):
    if df_processed is not None and not df_processed.empty:
        st.write(f"Total processed files: {len(df_processed)}")
        # show counts by broker
        if 'Broker' in df_processed.columns:
            counts = df_processed['Broker'].value_counts().to_dict()
            st.write("Broker counts:")
            for b, c in counts.items():
                st.write(f"- {b}: {c}")
        # show a small table
        st.dataframe(df_processed.sort_values('DownloadedAt', ascending=False).head(50))
    else:
        st.write("No processed_files.csv found or it's empty yet.")

# Sidebar filters
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Global Filters")

# Date range filter
if not df_trades.empty:
    min_date = df_trades['Date'].min().date()
    max_date = df_trades['Date'].max().date()
    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
else:
    date_range = None

# Broker filter
if not df_trades.empty and 'Broker' in df_trades.columns:
    brokers = ['All'] + sorted(df_trades['Broker'].dropna().unique().tolist())
    selected_broker = st.sidebar.selectbox("Broker", brokers, key="broker_filter")
else:
    selected_broker = 'All'

# Underlying filter
if not df_trades.empty:
    underlyings = ['All'] + sorted(df_trades['Underlying'].unique().tolist())
    selected_underlying = st.sidebar.selectbox("Underlying", underlyings, key="underlying_filter")
else:
    selected_underlying = 'All'

# P&L filter
pnl_filter = st.sidebar.selectbox("P&L Filter", ['All', 'Profitable', 'Loss', 'Break-even'], key="pnl_filter")

# Advanced filters toggle
show_advanced = st.sidebar.checkbox("Show Advanced Filters", key="show_advanced")
if show_advanced:
    # Trade type filter
    if not df_trades.empty and 'Type' in df_trades.columns:
        trade_types = ['All'] + sorted(df_trades['Type'].dropna().unique().tolist())
        selected_trade_type = st.sidebar.selectbox("Trade Type", trade_types, key="trade_type_filter")
    else:
        selected_trade_type = 'All'

    # Exchange filter
    if not df_trades.empty and 'Exchange' in df_trades.columns:
        exchanges = ['All'] + sorted(df_trades['Exchange'].dropna().unique().tolist())
        selected_exchange = st.sidebar.selectbox("Exchange", exchanges, key="exchange_filter")
    else:
        selected_exchange = 'All'
else:
    selected_trade_type = 'All'
    selected_exchange = 'All'

# Clear filters button
if st.sidebar.button("🗑️ Clear All Filters"):
    for key in session_state_defaults.keys():
        st.session_state[key] = session_state_defaults[key]
    st.rerun()

# Apply filters function with improved logic
def apply_filters(df, data_type='trades'):
    """Apply all filters to dataframe with better error handling"""
    if df.empty:
        return df

    df_filtered = df.copy()

    # Date filter
    if date_range and len(date_range) == 2:
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        df_filtered = df_filtered[(df_filtered['Date'] >= start_date) & (df_filtered['Date'] <= end_date)]

    # Broker filter
    if selected_broker != 'All' and 'Broker' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Broker'] == selected_broker]

    # Underlying filter
    if selected_underlying != 'All' and 'Underlying' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Underlying'] == selected_underlying]

    # P&L filter
    if pnl_filter != 'All' and 'Net Total' in df_filtered.columns:
        if pnl_filter == 'Profitable':
            df_filtered = df_filtered[df_filtered['Net Total'] > 0]
        elif pnl_filter == 'Loss':
            df_filtered = df_filtered[df_filtered['Net Total'] < 0]
        elif pnl_filter == 'Break-even':
            df_filtered = df_filtered[df_filtered['Net Total'] == 0]

    # Advanced filters
    if show_advanced:
        if selected_trade_type != 'All' and 'Type' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['Type'] == selected_trade_type]

        if selected_exchange != 'All' and 'Exchange' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['Exchange'] == selected_exchange]

    return df_filtered

# Apply filters
df_trades_filtered = apply_filters(df_trades, 'trades')
df_funds_filtered = apply_filters(df_funds, 'funds') if not df_funds.empty else df_funds
df_pledges_filtered = apply_filters(df_pledges, 'pledges') if not df_pledges.empty else df_pledges
df_summary_filtered = apply_filters(df_summary, 'summary') if not df_summary.empty else df_summary

# Create Round-Trip trades dataframe for accurate win rate and PnL metrics
# This combines a buy leg and a sell leg for the same contract on the same day
if not df_trades_filtered.empty:
    rt_group_cols = ['Date', 'Underlying', 'Strike', 'Type']
    valid_cols = [c for c in rt_group_cols if c in df_trades_filtered.columns]
    agg_dict = {'Net Total': 'sum'}
    if 'Broker' in df_trades_filtered.columns:
        valid_cols.append('Broker')
    if 'Quantity' in df_trades_filtered.columns:
        agg_dict['Quantity'] = 'max'  # Proxy to keep the column
        
    df_round_trips = df_trades_filtered.groupby(valid_cols, dropna=False).agg(agg_dict).reset_index()
    if 'Date' in df_round_trips.columns:
        df_round_trips['Day_of_Week'] = df_round_trips['Date'].dt.day_name()
        df_round_trips['Month'] = df_round_trips['Date'].dt.month_name()
        df_round_trips['Year'] = df_round_trips['Date'].dt.year
else:
    df_round_trips = pd.DataFrame()

# Main dashboard title with summary
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.title('📊 Trading Journal Dashboard')
    # UI hint about interactivity
    if HAVE_PLOTLY_EVENTS:
        st.markdown("**Tip:** Click any chart element to drill down (clicks are supported). You can still use the selectboxes below charts as an alternative.")
    else:
        st.markdown("**Tip:** Click-based drilldowns are not available. Use the selectboxes below charts to filter and drill down.")
with col2:
    if not df_trades_filtered.empty:
        total_pnl = df_trades_filtered['Net Total'].sum()
        pnl_class = "positive" if total_pnl >= 0 else "negative"
        st.markdown(f"""
        <div class="metric-card {pnl_class}">
            <h3>Total P&L</h3>
            <h2>₹{total_pnl:,.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
with col3:
    if not df_round_trips.empty:
        win_rate = (df_round_trips['Net Total'] > 0).mean() * 100
        st.markdown(f"""
        <div class="metric-card positive">
            <h3>Win Rate</h3>
            <h2>{win_rate:.1f}%</h2>
        </div>
        """, unsafe_allow_html=True)

# Tab navigation with better organization
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈 Trades", "💰 Funds Flow", "📌 Pledges",
    "📋 Summary", "📊 Analytics", "🎯 Risk Analysis"
])

# ===== TAB 1: TRADES =====
with tab1:
    if not df_trades_filtered.empty:
        # Key metrics row
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            st.metric('Total Trades', len(df_round_trips))
        with col2:
            total_pnl = df_trades_filtered['Net Total'].sum()
            st.metric('Total P&L', f'₹{total_pnl:,.2f}')
        with col3:
            win_rate = (df_round_trips['Net Total'] > 0).mean() * 100
            st.metric('Win Rate', f'{win_rate:.1f}%')
        with col4:
            avg_trade = df_round_trips['Net Total'].mean()
            st.metric('Avg Trade', f'₹{avg_trade:.2f}')
        with col5:
            largest_win = df_round_trips['Net Total'].max()
            st.metric('Largest Win', f'₹{largest_win:,.2f}')
        with col6:
            largest_loss = df_round_trips['Net Total'].min()
            st.metric('Largest Loss', f'₹{largest_loss:,.2f}')

        # Charts section
        st.markdown("---")

        # Daily P&L with improved interactivity
        st.subheader('📊 Daily P&L Performance')
        daily_pnl = df_trades_filtered.groupby('Date')['Net Total'].sum().reset_index()
        daily_pnl['Cumulative P&L'] = daily_pnl['Net Total'].cumsum()

        # Create interactive bar chart
        fig_daily = px.bar(
            daily_pnl, x='Date', y='Net Total',
            title='Daily Profit/Loss',
            color='Net Total',
            color_continuous_scale='RdYlGn',
            hover_data=['Cumulative P&L']
        )

        # Add reference line at zero
        fig_daily.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.7)

        # Handle click events properly
        st.plotly_chart(fig_daily, use_container_width=True)

        # Explicit date selector for drilldown (safe alternative to plot selection)
        date_options = [None] + list(daily_pnl['Date'].dt.date.unique())
        chosen_date = st.selectbox("Select date to drill down", options=date_options, format_func=lambda d: "" if d is None else d.strftime("%Y-%m-%d"), key="daily_select")
        if chosen_date:
            st.session_state.selected_date = chosen_date

        # Show drilldown if date selected
        if st.session_state.selected_date:
            st.markdown(f"### 🔍 Details for {st.session_state.selected_date.strftime('%Y-%m-%d')}")

            day_trades = df_trades_filtered[df_trades_filtered['Date'].dt.date == st.session_state.selected_date]
            day_rt = df_round_trips[df_round_trips['Date'].dt.date == st.session_state.selected_date]

            if not day_trades.empty:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Day's P&L", f"₹{day_trades['Net Total'].sum():,.2f}")
                with col2:
                    st.metric("Trades", len(day_rt))
                with col3:
                    st.metric("Win Rate", f"{(day_rt['Net Total'] > 0).mean()*100:.1f}%" if not day_rt.empty else "0.0%")

                st.dataframe(day_trades, use_container_width=True)
            else:
                st.info("No trades found for selected date")

        # Cumulative P&L
        st.subheader('📈 Cumulative P&L')
        fig_cumulative = px.line(
            daily_pnl, x='Date', y='Cumulative P&L',
            title='Cumulative Profit/Loss',
            markers=True,
            line_shape='spline'
        )
        fig_cumulative.add_hline(y=0, line_dash="dash", line_color="red", opacity=0.7)
        st.plotly_chart(fig_cumulative, use_container_width=True)

        # Performance by categories
        col1, col2 = st.columns(2)

        with col1:
            st.subheader('🏢 Performance by Broker')
            if 'Broker' in df_trades_filtered.columns and df_trades_filtered['Broker'].notna().any():
                broker_perf = df_trades_filtered.groupby('Broker').agg({
                    'Net Total': ['sum', 'count', 'mean'],
                    'Quantity': 'sum'
                }).round(2)
                broker_perf.columns = ['Total P&L', 'Trade Count', 'Avg Trade', 'Total Quantity']
                broker_perf = broker_perf.reset_index()

                fig_broker = px.bar(
                    broker_perf, x='Broker', y='Total P&L',
                    title='P&L by Broker',
                    color='Total P&L',
                    color_continuous_scale='RdYlGn',
                    text='Trade Count'
                )
                st.plotly_chart(fig_broker, use_container_width=True)

                # Broker details in expandable sections
                for broker in broker_perf['Broker']:
                    broker_data = df_trades_filtered[df_trades_filtered['Broker'] == broker]
                    broker_rt = df_round_trips[df_round_trips['Broker'] == broker]
                    with st.expander(f"📊 {broker} Details"):
                        bcol1, bcol2, bcol3, bcol4 = st.columns(4)
                        with bcol1:
                            st.metric(f"{broker} P&L", f"₹{broker_data['Net Total'].sum():,.2f}")
                        with bcol2:
                            st.metric(f"Win Rate", f"{(broker_rt['Net Total'] > 0).mean()*100:.1f}%" if not broker_rt.empty else "0.0%")
                        with bcol3:
                            st.metric(f"Avg Trade", f"₹{broker_rt['Net Total'].mean():.2f}" if not broker_rt.empty else "₹0.00")
                        with bcol4:
                            st.metric(f"Trades", len(broker_rt))

        with col2:
            st.subheader('📈 Performance by Underlying')
            underlying_perf = df_trades_filtered.groupby('Underlying')['Net Total'].sum().reset_index()
            underlying_perf = underlying_perf.sort_values('Net Total', ascending=False)

            fig_underlying = px.bar(
                underlying_perf, x='Underlying', y='Net Total',
                title='P&L by Underlying',
                color='Net Total',
                color_continuous_scale='RdYlGn'
            )
            st.plotly_chart(fig_underlying, use_container_width=True)

        # Trade timing analysis
        st.subheader('⏰ Trade Timing Analysis')
        col1, col2, col3 = st.columns(3)

        with col1:
            # Day of week analysis
            dow_perf = df_round_trips.groupby('Day_of_Week').agg({
                'Net Total': ['sum', 'count', 'mean']
            }).round(2)
            dow_perf.columns = ['Total P&L', 'Trade Count', 'Avg Trade']
            dow_perf = dow_perf.reset_index()

            # Reorder days
            day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            dow_perf['Day_of_Week'] = pd.Categorical(dow_perf['Day_of_Week'], categories=day_order, ordered=True)
            dow_perf = dow_perf.sort_values('Day_of_Week')

            fig_dow = px.bar(
                dow_perf, x='Day_of_Week', y='Total P&L',
                title='P&L by Day of Week',
                color='Total P&L',
                color_continuous_scale='RdYlGn'
            )
            st.plotly_chart(fig_dow, use_container_width=True)

        with col2:
            # Monthly analysis
            monthly_perf = df_round_trips.groupby('Month')['Net Total'].sum().reset_index()
            month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December']
            monthly_perf['Month'] = pd.Categorical(monthly_perf['Month'], categories=month_order, ordered=True)
            monthly_perf = monthly_perf.sort_values('Month')

            fig_monthly = px.bar(
                monthly_perf, x='Month', y='Net Total',
                title='P&L by Month',
                color='Net Total',
                color_continuous_scale='RdYlGn'
            )
            st.plotly_chart(fig_monthly, use_container_width=True)

        with col3:
            # Trade type analysis
            if 'Type' in df_round_trips.columns:
                type_perf = df_round_trips.groupby('Type').agg({
                    'Net Total': ['sum', 'count', 'mean']
                }).round(2)
                type_perf.columns = ['Total P&L', 'Trade Count', 'Avg Trade']
                type_perf = type_perf.reset_index()
                type_perf = type_perf.sort_values('Total P&L', ascending=False)

                fig_type = px.bar(
                    type_perf, x='Type', y='Total P&L',
                    title='P&L by Trade Type',
                    color='Total P&L',
                    color_continuous_scale='RdYlGn'
                )
                st.plotly_chart(fig_type, use_container_width=True)

        # Detailed trades table with sorting
        st.subheader('📋 Detailed Trades')
        col1, col2, col3 = st.columns(3)

        with col1:
            sort_options = [col for col in df_trades_filtered.columns
                          if col not in ['Date', 'Expiry'] and
                          df_trades_filtered[col].dtype in ['int64', 'float64', 'object']]
            sort_by = st.selectbox("Sort by", sort_options, key="sort_trades")

        with col2:
            sort_order = st.selectbox("Order", ['Descending', 'Ascending'], key="sort_order_trades")

        with col3:
            available_columns = df_trades_filtered.columns.tolist()
            default_columns = ['Date', 'Underlying', 'Type', 'Quantity', 'Net Total', 'Exchange']
            safe_defaults = [col for col in default_columns if col in available_columns]
            show_columns = st.multiselect(
                "Show columns",
                available_columns,
                default=safe_defaults,
                key="show_columns_trades"
            )

        # Apply sorting
        ascending = sort_order == 'Ascending'
        sorted_trades = df_trades_filtered.sort_values(sort_by, ascending=ascending)

        # Display table
        if show_columns:
            st.dataframe(sorted_trades[show_columns], use_container_width=True)
        else:
            st.dataframe(sorted_trades, use_container_width=True)

    else:
        st.info("No trades data available or no data matches current filters")

# ===== TAB 2: FUNDS FLOW =====
with tab2:
    if not df_funds_filtered.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            deposits = df_funds_filtered['Amount'].where(df_funds_filtered['Type'] == 'Deposit').sum()
            currency = df_funds_filtered['Currency'].iloc[0] if not df_funds_filtered.empty else 'INR'
            st.metric('Total Deposits', f"{currency} {deposits:,.2f}")
        with col2:
            withdrawals = df_funds_filtered['Amount'].where(df_funds_filtered['Type'] == 'Withdrawal').sum()
            st.metric('Total Withdrawals', f"{currency} {withdrawals:,.2f}")
        with col3:
            net_flow = deposits - withdrawals
            st.metric('Net Inflow', f"{currency} {net_flow:,.2f}")
        with col4:
            avg_transaction = df_funds_filtered['Amount'].mean()
            st.metric('Avg Transaction', f"{currency} {avg_transaction:.2f}")

        # Funds Flow by Type with drilldown
        st.subheader('💰 Funds Flow by Type (Click segments for details)')
        funds_by_type = df_funds_filtered.groupby('Type')['Amount'].sum().reset_index()
        fig = px.pie(funds_by_type, names='Type', values='Amount',
                     color_discrete_map={'Deposit': '#90EE90', 'Withdrawal': '#FF6B6B', 'Settlement Payable': '#FFB347'},
                     title='Fund Transactions by Type')

        # Add click handling for pie chart
        st.plotly_chart(fig, width='stretch')

        # Provide explicit type selector for pie drilldown
        fund_type_options = ['All'] + funds_by_type['Type'].tolist()
        selected_fund_type = st.selectbox("Select fund type", options=fund_type_options, key="fund_pie_select")
        if selected_fund_type != 'All':
            type_funds = df_funds_filtered[df_funds_filtered['Type'] == selected_fund_type]
            st.markdown(f"### 📋 {selected_fund_type} Transactions")
            st.dataframe(type_funds.sort_values('Date', ascending=False), width='stretch')

        # Daily Funds Flow with drilldown
        st.subheader('📅 Daily Funds Flow (Click bars for details)')
        daily_funds = df_funds_filtered.groupby(['Date', 'Type'])['Amount'].sum().reset_index()
        fig2 = px.bar(daily_funds, x='Date', y='Amount', color='Type',
                      title='Daily Fund Transactions',
                      color_discrete_map={'Deposit': '#90EE90', 'Withdrawal': '#FF6B6B', 'Settlement Payable': '#FFB347'})

        # Add click handling for bar chart
        st.plotly_chart(fig2, width='stretch')

        # Provide selectors for date and type to drilldown
        date_options = [None] + sorted(daily_funds['Date'].dt.date.unique().tolist())
        selected_bar_date = st.selectbox("Select date", options=date_options, format_func=lambda d: "" if d is None else d.strftime("%Y-%m-%d"), key="fund_bar_date")
        type_options = ['All'] + sorted(daily_funds['Type'].unique().tolist())
        selected_bar_type = st.selectbox("Select type", options=type_options, key="fund_bar_type")
        if selected_bar_date and selected_bar_type:
            if selected_bar_type != 'All':
                day_funds = df_funds_filtered[(df_funds_filtered['Date'].dt.date == selected_bar_date) &
                                            (df_funds_filtered['Type'] == selected_bar_type)]
            else:
                day_funds = df_funds_filtered[df_funds_filtered['Date'].dt.date == selected_bar_date]
            st.markdown(f"### 📋 {selected_bar_type} on {selected_bar_date}" if selected_bar_type != 'All' else f"### 📋 Funds on {selected_bar_date}")
            st.dataframe(day_funds, width='stretch')

        # Funds by Broker with drilldown
        if 'Broker' in df_funds_filtered.columns and df_funds_filtered['Broker'].notna().any():
            st.subheader('🏢 Funds by Broker (Click bars for details)')
            broker_funds = df_funds_filtered.groupby('Broker')['Amount'].sum().reset_index()
            fig3 = px.bar(broker_funds, x='Broker', y='Amount', title='Total Funds by Broker',
                         color='Amount', color_continuous_scale='Blues')

            if HAVE_PLOTLY_EVENTS:
                sel = plotly_events(fig3, click_event=True, key="broker_funds_events")
                if sel:
                    broker_name = sel[0].get('x')
                    broker_detail = df_funds_filtered[df_funds_filtered['Broker'] == broker_name]
                    broker_currency = broker_detail['Currency'].iloc[0] if not broker_detail.empty else 'INR'
                    st.markdown(f"### 📋 {broker_name} Fund Transactions ({broker_currency})")
                    st.dataframe(broker_detail.sort_values('Date', ascending=False), width='stretch')

                # Fallback selector as well
                broker_options = ['All'] + broker_funds['Broker'].tolist()
                selected_broker_funds = st.selectbox("Select broker", options=broker_options, key="broker_funds_select")
                if selected_broker_funds != 'All':
                    broker_detail = df_funds_filtered[df_funds_filtered['Broker'] == selected_broker_funds]
                    broker_currency = broker_detail['Currency'].iloc[0] if not broker_detail.empty else 'INR'
                    st.markdown(f"### 📋 {selected_broker_funds} Fund Transactions ({broker_currency})")
                    st.dataframe(broker_detail.sort_values('Date', ascending=False), width='stretch')
            else:
                st.plotly_chart(fig3, width='stretch')

                # Provide broker selector for drilldown
                broker_options = ['All'] + broker_funds['Broker'].tolist()
                selected_broker_funds = st.selectbox("Select broker", options=broker_options, key="broker_funds_select")
                if selected_broker_funds != 'All':
                    broker_detail = df_funds_filtered[df_funds_filtered['Broker'] == selected_broker_funds]
                    broker_currency = broker_detail['Currency'].iloc[0] if not broker_detail.empty else 'INR'
                    st.markdown(f"### 📋 {selected_broker_funds} Fund Transactions ({broker_currency})")
                    st.dataframe(broker_detail.sort_values('Date', ascending=False), width='stretch')
        else:
            st.subheader('💰 Funds by Type')
            broker_funds = df_funds_filtered.groupby('Type')['Amount'].sum().reset_index()
            fig3 = px.bar(broker_funds, x='Type', y='Amount', title='Total Funds by Type')
            st.plotly_chart(fig3, width='stretch')

        # Funds vs Trading Performance
        if not df_trades_filtered.empty:
            st.subheader('🔄 Funds vs Trading Performance')
            col1, col2 = st.columns(2)

            with col1:
                # Daily correlation
                daily_trades_pnl = df_trades_filtered.groupby('Date')['Net Total'].sum().reset_index()
                daily_funds_net = df_funds_filtered.groupby('Date')['Amount'].sum().reset_index()

                merged = daily_trades_pnl.merge(daily_funds_net, on='Date', how='outer').fillna(0)
                merged.columns = ['Date', 'Trading_PnL', 'Funds_Flow']

                fig4 = px.scatter(merged, x='Trading_PnL', y='Funds_Flow',
                                title='Trading P&L vs Funds Flow Correlation')
                st.plotly_chart(fig4, width='stretch')

            with col2:
                # Cumulative view
                merged = merged.sort_values('Date')
                merged['Cum_Trading'] = merged['Trading_PnL'].cumsum()
                merged['Cum_Funds'] = merged['Funds_Flow'].cumsum()

                fig5 = go.Figure()
                fig5.add_trace(go.Scatter(x=merged['Date'], y=merged['Cum_Trading'],
                                        name='Cumulative Trading P&L', mode='lines+markers'))
                fig5.add_trace(go.Scatter(x=merged['Date'], y=merged['Cum_Funds'],
                                        name='Cumulative Funds Flow', mode='lines+markers', yaxis='y2'))

                fig5.update_layout(
                    title='Cumulative Trading vs Funds Flow',
                    yaxis=dict(title='Trading P&L (₹)'),
                    yaxis2=dict(title='Funds Flow (₹)', overlaying='y', side='right'),
                    hovermode='x unified'
                )
                st.plotly_chart(fig5, width='stretch')

        # All Fund Transactions with filtering
        st.subheader('📋 All Fund Transactions')
        col1, col2 = st.columns(2)

        with col1:
            fund_sort_by = st.selectbox("Sort by", ['Date', 'Amount', 'Type', 'Broker'], key="sort_funds")
        with col2:
            fund_sort_order = st.selectbox("Order", ['Descending', 'Ascending'], key="fund_sort_order")

        # Apply sorting
        fund_ascending = fund_sort_order == 'Ascending'
        sorted_funds = df_funds_filtered.sort_values(fund_sort_by, ascending=fund_ascending)

        st.dataframe(sorted_funds, width='stretch')

    else:
        st.info("No funds data available or no data matches current filters. Run fetch_and_parse_gmail.py to extract fund information.")

# ===== TAB 3: PLEDGES =====
with tab3:
    if not df_pledges.empty:
        st.metric('Total Pledge Records', len(df_pledges))
        total_pledged = df_pledges['Amount'].sum()
        st.metric('Total Pledged Amount', f'₹{total_pledged:,.2f}')
        
        st.subheader('Pledges Over Time')
        daily_pledges = df_pledges.groupby('Date')['Amount'].sum().reset_index()
        fig = px.line(daily_pledges, x='Date', y='Amount', title='Daily Pledge Amount',
                      markers=True)
        st.plotly_chart(fig, width='stretch')
        
        st.subheader('Pledges by Broker')
        broker_pledges = df_pledges.groupby('Broker')['Amount'].sum().reset_index()
        fig2 = px.bar(broker_pledges, x='Broker', y='Amount', title='Total Pledges by Broker')
        st.plotly_chart(fig2, width='stretch')
        
        st.subheader('All Pledge Records')
        st.dataframe(df_pledges.sort_values('Date', ascending=False), width='stretch')
    else:
        st.info("No pledge data available. Run fetch_and_parse_gmail.py to extract pledge information.")

# ===== TAB 4: SUMMARY =====
with tab4:
    if not df_summary.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric('PDFs Processed', len(df_summary))
        with col2:
            total_trades_summary = df_summary['Total_Trades'].sum()
            st.metric('Total Trades', int(total_trades_summary))
        with col3:
            total_fees = df_summary['Total_Fees'].sum()
            st.metric('Total Fees', f'₹{total_fees:,.2f}')
        
        st.subheader('Summary by Date')
        summary_display = df_summary[['Date', 'Broker', 'Total_Trades', 'Total_Fees', 'Settlement_Amount']].copy()
        st.dataframe(summary_display.sort_values('Date', ascending=False), width='stretch')
        
        st.subheader('Trades per Day')
        fig = px.bar(df_summary, x='Date', y='Total_Trades', color='Broker',
                     title='Number of Trades by Day')
        st.plotly_chart(fig, width='stretch')
        
        st.subheader('Fees Trend')
        fig2 = px.line(df_summary.sort_values('Date'), x='Date', y='Total_Fees', 
                       color='Broker', markers=True, title='Daily Fees')
        st.plotly_chart(fig2, width='stretch')
    else:
        st.info("No summary data available.")

# ===== TAB 5: ANALYTICS =====
with tab5:
    st.subheader('📊 Advanced Trading Analytics')

    if not df_trades_filtered.empty:
        # Performance Overview
        col1, col2, col3, col4 = st.columns(4)

        total_trades = len(df_round_trips)
        winning_trades = df_round_trips[df_round_trips['Net Total'] > 0]
        losing_trades = df_round_trips[df_round_trips['Net Total'] < 0]

        with col1:
            st.metric('Total Trades', total_trades)
        with col2:
            win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
            st.metric('Win Rate', f'{win_rate:.1f}%')
        with col3:
            profit_factor = abs(winning_trades['Net Total'].sum() / losing_trades['Net Total'].sum()) if len(losing_trades) > 0 and losing_trades['Net Total'].sum() != 0 else float('inf')
            st.metric('Profit Factor', f'{profit_factor:.2f}')
        with col4:
            avg_win = winning_trades['Net Total'].mean() if len(winning_trades) > 0 else 0
            avg_loss = abs(losing_trades['Net Total'].mean()) if len(losing_trades) > 0 else 0
            expectancy = (win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss)
            st.metric('Expectancy', f'₹{expectancy:.2f}')

        # Risk-Reward Analysis
        st.subheader('🎯 Risk-Reward Analysis')
        col1, col2 = st.columns(2)

        with col1:
            # Win/Loss Distribution
            trade_results = ['Win' if x > 0 else 'Loss' if x < 0 else 'Break-even' for x in df_round_trips['Net Total']]
            result_counts = pd.Series(trade_results).value_counts()

            fig1 = px.pie(result_counts, names=result_counts.index, values=result_counts.values,
                         title='Trade Result Distribution',
                         color_discrete_map={'Win': '#90EE90', 'Loss': '#FF6B6B', 'Break-even': '#FFD700'})
            st.plotly_chart(fig1, width='stretch')

        with col2:
            # P&L Distribution Histogram
            fig2 = px.histogram(df_round_trips, x='Net Total', nbins=50,
                              title='P&L Distribution (Round-Trip Trades)',
                              color_discrete_sequence=['#636EFA'])
            fig2.add_vline(x=0, line_dash="dash", line_color="red")
            st.plotly_chart(fig2, width='stretch')

        # Performance by Time Periods
        st.subheader('⏰ Performance by Time Period')
        col1, col2, col3 = st.columns(3)

        with col1:
            # Monthly Performance
            df_trades_filtered['Month'] = df_trades_filtered['Date'].dt.to_period('M').astype(str)
            monthly_perf = df_trades_filtered.groupby('Month')['Net Total'].sum().reset_index()
            monthly_perf['Month'] = pd.to_datetime(monthly_perf['Month'])

            fig3 = px.bar(monthly_perf, x='Month', y='Net Total',
                         title='Monthly Performance', color='Net Total',
                         color_continuous_scale='RdYlGn')
            st.plotly_chart(fig3, width='stretch')

        with col2:
            # Weekly Performance
            df_trades_filtered['Week'] = df_trades_filtered['Date'].dt.to_period('W').apply(lambda r: r.start_time)
            weekly_perf = df_trades_filtered.groupby('Week')['Net Total'].sum().reset_index()

            fig4 = px.line(weekly_perf, x='Week', y='Net Total',
                          title='Weekly Performance', markers=True)
            st.plotly_chart(fig4, width='stretch')

        with col3:
            # Best/Worst Performing Days
            daily_perf = df_trades_filtered.groupby(df_trades_filtered['Date'].dt.date)['Net Total'].sum().reset_index()
            daily_perf = daily_perf.sort_values('Net Total', ascending=False)

            st.markdown("**Top 5 Best Days:**")
            for _, row in daily_perf.head(5).iterrows():
                st.write(f"📅 {row['Date']}: ₹{row['Net Total']:,.2f}")

            st.markdown("**Top 5 Worst Days:**")
            for _, row in daily_perf.tail(5).iterrows():
                st.write(f"📅 {row['Date']}: ₹{row['Net Total']:,.2f}")

        # Strategy Analysis
        st.subheader('🎲 Strategy & Pattern Analysis')
        col1, col2 = st.columns(2)

        with col1:
            # Trade Type Analysis
            if 'Type' in df_round_trips.columns:
                type_perf = df_round_trips.groupby('Type')['Net Total'].agg(['sum', 'count', 'mean']).reset_index()
                type_perf.columns = ['Type', 'Total_PnL', 'Count', 'Avg_PnL']

                fig5 = px.bar(type_perf, x='Type', y='Total_PnL',
                             title='Performance by Trade Type', color='Total_PnL',
                             color_continuous_scale='RdYlGn')
                st.plotly_chart(fig5, width='stretch')

        with col2:
            # Underlying Performance Heatmap
            if len(df_trades_filtered['Underlying'].unique()) > 1:
                pivot_data = df_trades_filtered.pivot_table(
                    values='Net Total',
                    index=df_trades_filtered['Date'].dt.month,
                    columns='Underlying',
                    aggfunc='sum'
                ).fillna(0)

                fig6 = px.imshow(pivot_data,
                               title='Underlying Performance Heatmap (Monthly)',
                               color_continuous_scale='RdYlGn')
                st.plotly_chart(fig6, width='stretch')

        # Correlation Analysis
        if not df_funds_filtered.empty:
            st.subheader('🔗 Trading vs Funds Correlation')

            # Daily correlation
            daily_trades = df_trades_filtered.groupby('Date')['Net Total'].sum().reset_index()
            daily_funds = df_funds_filtered.groupby('Date')['Amount'].sum().reset_index()

            corr_data = daily_trades.merge(daily_funds, on='Date', how='outer').fillna(0)
            corr_data.columns = ['Date', 'Trading_PnL', 'Funds_Flow']

            col1, col2 = st.columns(2)

            with col1:
                # Scatter plot without trendline (avoids statsmodels dependency)
                fig4 = px.scatter(corr_data, x='Trading_PnL', y='Funds_Flow',
                                title='Trading P&L vs Funds Flow')
                st.plotly_chart(fig4, width='stretch')

            with col2:
                # Correlation metrics
                correlation = corr_data['Trading_PnL'].corr(corr_data['Funds_Flow'])
                st.metric('P&L vs Funds Correlation', f'{correlation:.3f}')

                # Rolling correlation (if enough data)
                if len(corr_data) > 7:
                    corr_data['Rolling_Corr'] = corr_data['Trading_PnL'].rolling(7).corr(corr_data['Funds_Flow'])
                    fig8 = px.line(corr_data, x='Date', y='Rolling_Corr',
                                 title='7-Day Rolling Correlation')
                    st.plotly_chart(fig8, width='stretch')

        # Key Insights
        st.subheader('💡 Key Insights & Recommendations')

        insights = []

        # Win rate insights
        if win_rate > 60:
            insights.append("🎉 Excellent win rate! Your strategy is performing well.")
        elif win_rate < 40:
            insights.append("⚠️ Low win rate. Consider reviewing your entry criteria.")

        # Profit factor insights
        if profit_factor > 2:
            insights.append("💰 Strong profit factor! Your winners significantly outweigh losses.")
        elif profit_factor < 1:
            insights.append("⚠️ Profit factor < 1. Your losses exceed wins - risk management needed.")

        # Consistency insights
        daily_std = daily_perf['Net Total'].std()
        daily_mean = daily_perf['Net Total'].mean()
        if daily_std > abs(daily_mean) * 2:
            insights.append("📊 High volatility in daily performance. Consider position sizing.")

        # Best performing underlying
        underlying_pnl = df_trades_filtered.groupby('Underlying')['Net Total'].sum().reset_index()
        if not underlying_pnl.empty:
            best_underlying = underlying_pnl.loc[underlying_pnl['Net Total'].idxmax()]
            insights.append(f"🏆 Best performing underlying: {best_underlying['Underlying']} (₹{best_underlying['Net Total']:,.2f})")

        # Trading frequency
        avg_trades_per_day = len(df_round_trips) / len(df_trades_filtered['Date'].dt.date.unique())
        if avg_trades_per_day > 10:
            insights.append("⚡ High trading frequency. Consider reducing to improve quality.")
        elif avg_trades_per_day < 2:
            insights.append("🐌 Low trading frequency. May have room for more opportunities.")

        for insight in insights:
            st.info(insight)

    else:
        st.info("No trades data available for analytics")

# ===== TAB 6: RISK ANALYSIS =====
with tab6:
    st.subheader('🎯 Risk Management Analysis')

    if not df_trades_filtered.empty:
        # Risk Metrics
        col1, col2, col3, col4 = st.columns(4)

        # Calculate risk metrics based on round-trip returns
        df_rt_sorted = df_round_trips.sort_values('Date').copy()
        returns = df_rt_sorted['Net Total']
        cumulative_returns = returns.cumsum()

        # Maximum drawdown
        peak = cumulative_returns.expanding().max()
        drawdown = cumulative_returns - peak
        max_drawdown = drawdown.min()
        max_drawdown_pct = (max_drawdown / peak.max()) * 100 if peak.max() > 0 else 0

        # Value at Risk (95% confidence)
        var_95 = np.percentile(returns, 5)

        # Expected Shortfall (CVaR)
        cvar_95 = returns[returns <= var_95].mean() if len(returns[returns <= var_95]) > 0 else 0

        # Calmar Ratio
        unique_days = len(df_trades_filtered['Date'].dt.date.unique())
        last_return = cumulative_returns.iloc[-1] if not cumulative_returns.empty else 0
        annual_return = (last_return / unique_days * 365) if unique_days > 0 else 0
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        with col1:
            st.metric('Max Drawdown', f'₹{max_drawdown:,.2f}')
        with col2:
            st.metric('Max Drawdown %', f'{max_drawdown_pct:.2f}%')
        with col3:
            st.metric('VaR (95%)', f'₹{var_95:,.2f}')
        with col4:
            st.metric('CVaR (95%)', f'₹{cvar_95:,.2f}')

        st.markdown("---")

        # Drawdown Analysis
        st.subheader('📉 Drawdown Analysis')

        # Create drawdown chart
        drawdown_df = pd.DataFrame({
            'Date': df_rt_sorted['Date'],
            'Cumulative_PnL': cumulative_returns,
            'Drawdown': drawdown,
            'Drawdown_Pct': (drawdown / peak) * 100
        })

        col1, col2 = st.columns(2)

        with col1:
            fig_drawdown = px.line(
                drawdown_df, x='Date', y='Drawdown',
                title='Portfolio Drawdown Over Time',
                color_discrete_sequence=['red']
            )
            fig_drawdown.add_hline(y=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig_drawdown, use_container_width=True)

        with col2:
            fig_drawdown_pct = px.area(
                drawdown_df, x='Date', y='Drawdown_Pct',
                title='Drawdown Percentage',
                color_discrete_sequence=['orange']
            )
            st.plotly_chart(fig_drawdown_pct, use_container_width=True)

        # Risk-Adjusted Returns
        st.subheader('📊 Risk-Adjusted Performance')

        # Calculate rolling Sharpe ratio
        if len(returns) > 10:
            rolling_sharpe = returns.rolling(window=10).mean() / returns.rolling(window=10).std() * np.sqrt(252)
            rolling_sharpe_df = pd.DataFrame({
                'Date': df_rt_sorted['Date'],
                'Rolling_Sharpe': rolling_sharpe
            })

            fig_rolling_sharpe = px.line(
                rolling_sharpe_df, x='Date', y='Rolling_Sharpe',
                title='10-Trade Rolling Sharpe Ratio'
            )
            fig_rolling_sharpe.add_hline(y=0, line_dash="dash", line_color="red")
            st.plotly_chart(fig_rolling_sharpe, use_container_width=True)

        # Position Sizing Analysis
        st.subheader('📏 Position Sizing Analysis')

        kelly_fraction = None
        if 'Quantity' in df_round_trips.columns:
            # Kelly Criterion approximation
            win_rate = (returns > 0).mean()
            avg_win = returns[returns > 0].mean()
            avg_loss = abs(returns[returns < 0].mean())

            if avg_loss > 0:
                kelly_fraction = win_rate - ((1 - win_rate) / (avg_win / avg_loss))
                optimal_position_size = kelly_fraction * 100  # as percentage

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric('Kelly Fraction', f'{kelly_fraction:.3f}')
                with col2:
                    st.metric('Optimal Position Size', f'{max(0, optimal_position_size):.1f}%')
                with col3:
                    st.metric('Current Avg Position', f"{df_round_trips['Quantity'].mean():.0f}")

                # Position size distribution
                fig_position = px.histogram(
                    df_round_trips, x='Quantity',
                    title='Position Size Distribution',
                    nbins=20
                )
                st.plotly_chart(fig_position, use_container_width=True)

        # Risk Management Recommendations
        st.subheader('🛡️ Risk Management Recommendations')

        recommendations = []

        if max_drawdown_pct > 20:
            recommendations.append("⚠️ **High drawdown detected.** Consider reducing position sizes or implementing trailing stops.")

        if abs(var_95) > abs(returns.mean()) * 2:
            recommendations.append("⚠️ **High Value at Risk.** Daily losses can be significant - consider diversification.")

        if calmar_ratio < 1:
            recommendations.append("⚠️ **Poor risk-adjusted returns.** Focus on reducing drawdowns relative to returns.")

        if kelly_fraction is not None and kelly_fraction < 0.1:
            recommendations.append("💡 **Conservative Kelly fraction.** Consider smaller position sizes for capital preservation.")

        if len(recommendations) == 0:
            recommendations.append("✅ **Risk management looks good.** Continue monitoring and maintaining current practices.")

        for rec in recommendations:
            st.info(rec)

        # Stress Testing
        st.subheader('🔥 Stress Testing Scenarios')

        col1, col2, col3 = st.columns(3)

        with col1:
            # Worst case scenario (5 worst days)
            daily_perf = df_trades_filtered.groupby(df_trades_filtered['Date'].dt.date)['Net Total'].sum().reset_index()
            worst_5_days = daily_perf.nsmallest(5, 'Net Total')['Net Total'].sum()
            st.metric('5 Worst Days Loss', f'₹{worst_5_days:,.2f}')

        with col2:
            # 10% worst trades
            worst_10pct_trades = int(len(returns) * 0.1)
            if worst_10pct_trades > 0:
                worst_10pct_loss = returns.nsmallest(worst_10pct_trades).sum()
                st.metric('10% Worst Trades Loss', f'₹{worst_10pct_loss:,.2f}')

        with col3:
            # Recovery time estimation
            if max_drawdown < 0:
                recovery_trades = 0
                cumulative = 0
                for pnl in reversed(returns):
                    cumulative += pnl
                    recovery_trades += 1
                    if cumulative >= abs(max_drawdown):
                        break
                st.metric('Est. Recovery Trades', recovery_trades)

    else:
        st.info("No trades data available for risk analysis")

# Footer
st.markdown("---")
st.markdown("*Dashboard last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "*")
