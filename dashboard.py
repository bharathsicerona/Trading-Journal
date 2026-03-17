import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta

# Page config
st.set_page_config(page_title="Trading Journal Dashboard", layout="wide")

# Initialize session state for drilldown
if 'selected_date' not in st.session_state:
    st.session_state.selected_date = None
if 'selected_broker' not in st.session_state:
    st.session_state.selected_broker = None
if 'selected_underlying' not in st.session_state:
    st.session_state.selected_underlying = None
if 'date_filter' not in st.session_state:
    st.session_state.date_filter = None

# Load data files
trades_file = 'trades.csv'
funds_file = 'funds_transactions.csv'
pledges_file = 'pledges.csv'
summary_file = 'account_summary.csv'

# Load trades
if os.path.exists(trades_file):
    df_trades = pd.read_csv(trades_file)
    df_trades['Date'] = pd.to_datetime(df_trades['Date'])
    df_trades['Expiry'] = pd.to_datetime(df_trades['Expiry'])
else:
    df_trades = pd.DataFrame()

# Load funds transactions
if os.path.exists(funds_file):
    df_funds = pd.read_csv(funds_file)
    df_funds['Date'] = pd.to_datetime(df_funds['Date'])
    # Add currency column if it doesn't exist (for backward compatibility)
    if 'Currency' not in df_funds.columns:
        df_funds['Currency'] = df_funds['Broker'].apply(lambda x: 'USD' if x == 'Exness' else 'INR')
else:
    df_funds = pd.DataFrame()

# Load pledges
if os.path.exists(pledges_file):
    df_pledges = pd.read_csv(pledges_file)
    df_pledges['Date'] = pd.to_datetime(df_pledges['Date'])
else:
    df_pledges = pd.DataFrame()

# Load account summary
if os.path.exists(summary_file):
    df_summary = pd.read_csv(summary_file)
    df_summary['Date'] = pd.to_datetime(df_summary['Date'])
else:
    df_summary = pd.DataFrame()

# Title with drilldown info
title_col1, title_col2 = st.columns([3, 1])
with title_col1:
    st.title('📊 Trading Journal Dashboard')
with title_col2:
    if st.button('🔄 Clear Filters'):
        st.session_state.selected_date = None
        st.session_state.selected_broker = None
        st.session_state.selected_underlying = None
        st.session_state.date_filter = None
        st.rerun()

# Global filters
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)

with col1:
    if not df_trades.empty:
        date_range = st.date_input(
            "Date Range",
            value=(df_trades['Date'].min().date(), df_trades['Date'].max().date()),
            key="date_range"
        )
    else:
        date_range = None

with col2:
    if not df_trades.empty:
        # Check if Broker column exists, otherwise use Exchange or default
        if 'Broker' in df_trades.columns and df_trades['Broker'].notna().any():
            brokers = ['All'] + sorted(df_trades['Broker'].dropna().unique().tolist())
            broker_label = "Broker"
        else:
            # Use Exchange as proxy for broker filtering
            brokers = ['All'] + sorted(df_trades['Exchange'].unique().tolist())
            broker_label = "Exchange"
        selected_broker = st.selectbox(broker_label, brokers, key="broker_filter")
    else:
        selected_broker = 'All'
        broker_label = "Broker"

with col3:
    if not df_trades.empty:
        underlyings = ['All'] + sorted(df_trades['Underlying'].unique().tolist())
        selected_underlying = st.selectbox("Underlying", underlyings, key="underlying_filter")
    else:
        selected_underlying = 'All'

with col4:
    if not df_trades.empty:
        pnl_filter = st.selectbox("P&L Filter", ['All', 'Profitable', 'Loss', 'Break-even'], key="pnl_filter")
    else:
        pnl_filter = 'All'

# Apply filters to trades data
def apply_filters(df):
    if df.empty:
        return df

    # Date filter
    if date_range and len(date_range) == 2:
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]

    # Broker/Exchange filter
    if selected_broker != 'All':
        if 'Broker' in df.columns and df['Broker'].notna().any():
            df = df[df['Broker'] == selected_broker]
        elif 'Exchange' in df.columns:
            df = df[df['Exchange'] == selected_broker]

    # Underlying filter
    if selected_underlying != 'All':
        df = df[df['Underlying'] == selected_underlying]

    # P&L filter
    if pnl_filter == 'Profitable':
        df = df[df['Net Total'] > 0]
    elif pnl_filter == 'Loss':
        df = df[df['Net Total'] < 0]
    elif pnl_filter == 'Break-even':
        df = df[df['Net Total'] == 0]

    return df

# Apply filters
df_trades_filtered = apply_filters(df_trades)
df_funds_filtered = df_funds[df_funds['Date'].isin(df_trades_filtered['Date'])] if not df_funds.empty else df_funds
df_pledges_filtered = df_pledges[df_pledges['Date'].isin(df_trades_filtered['Date'])] if not df_pledges.empty else df_pledges
df_summary_filtered = df_summary[df_summary['Date'].isin(df_trades_filtered['Date'])] if not df_summary.empty else df_summary

# Tab selection
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Trades", "💰 Funds Flow", "📌 Pledges", "📋 Summary", "📊 Analytics"])

# ===== TAB 1: TRADES =====
with tab1:
    if not df_trades_filtered.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric('Total Trades', len(df_trades_filtered))
        with col2:
            total_pnl = df_trades_filtered['Net Total'].sum()
            st.metric('Total P&L', f'₹{total_pnl:,.2f}')
        with col3:
            win_rate = (df_trades_filtered[df_trades_filtered['Net Total'] > 0].shape[0] / len(df_trades_filtered) * 100) if len(df_trades_filtered) > 0 else 0
            st.metric('Win Rate', f'{win_rate:.1f}%')
        with col4:
            avg_trade = df_trades_filtered['Net Total'].mean()
            st.metric('Avg Trade', f'₹{avg_trade:.2f}')

        # Drilldown section
        if st.session_state.selected_date or st.session_state.selected_broker or st.session_state.selected_underlying:
            st.markdown("### 🔍 Drilldown View")
            drill_col1, drill_col2, drill_col3 = st.columns(3)

            with drill_col1:
                if st.session_state.selected_date:
                    st.info(f"📅 **Date:** {st.session_state.selected_date.strftime('%Y-%m-%d')}")
            with drill_col2:
                if st.session_state.selected_broker:
                    st.info(f"🏢 **Broker:** {st.session_state.selected_broker}")
            with drill_col3:
                if st.session_state.selected_underlying:
                    st.info(f"📈 **Underlying:** {st.session_state.selected_underlying}")

            # Show detailed trades for drilldown
            drilldown_trades = df_trades_filtered.copy()
            if st.session_state.selected_date:
                drilldown_trades = drilldown_trades[drilldown_trades['Date'].dt.date == st.session_state.selected_date]
            if st.session_state.selected_broker:
                drilldown_trades = drilldown_trades[drilldown_trades['Broker'] == st.session_state.selected_broker]
            if st.session_state.selected_underlying:
                drilldown_trades = drilldown_trades[drilldown_trades['Underlying'] == st.session_state.selected_underlying]

            if not drilldown_trades.empty:
                st.markdown(f"**{len(drilldown_trades)} trades found**")
                st.dataframe(drilldown_trades, width='stretch')
            else:
                st.warning("No trades match the drilldown criteria")

        st.markdown("---")

        # Daily P&L with drilldown
        st.subheader('📊 Daily P&L (Click bars for details)')
        daily_pnl = df_trades_filtered.groupby('Date')['Net Total'].sum().reset_index()
        daily_pnl['Cumulative P&L'] = daily_pnl['Net Total'].cumsum()

        # Create clickable bar chart
        fig = px.bar(daily_pnl, x='Date', y='Net Total', title='Daily Profit/Loss',
                     color='Net Total', color_continuous_scale='RdYlGn')

        # Add click event handling
        fig.update_traces(marker=dict(line=dict(width=1, color='DarkSlateGrey')))
        clicked = st.plotly_chart(fig, width='stretch', on_select="rerun")

        # Handle bar clicks for drilldown
        if clicked and 'selection' in clicked and clicked['selection']['points']:
            selected_point = clicked['selection']['points'][0]
            if 'x' in selected_point:
                selected_date = pd.to_datetime(selected_point['x']).date()
                st.session_state.selected_date = selected_date
                st.rerun()

        # Cumulative P&L
        st.subheader('📈 Cumulative P&L')
        fig2 = px.line(daily_pnl, x='Date', y='Cumulative P&L', title='Cumulative Profit/Loss',
                       markers=True)
        st.plotly_chart(fig2, width='stretch')

        col1, col2 = st.columns(2)

        with col1:
            st.subheader(f'🏢 Trades by {broker_label} (Click for details)')
            if 'Broker' in df_trades_filtered.columns and df_trades_filtered['Broker'].notna().any():
                broker_counts = df_trades_filtered['Broker'].value_counts()
                title_text = f'Trade Distribution by {broker_label}'
            else:
                broker_counts = df_trades_filtered['Exchange'].value_counts()
                title_text = 'Trade Distribution by Exchange'

            fig3 = px.pie(broker_counts, names=broker_counts.index, values=broker_counts.values,
                         title=title_text)

            # Add click handling for pie chart
            clicked_pie = st.plotly_chart(fig3, width='stretch', on_select="rerun")

            if clicked_pie and 'selection' in clicked_pie and clicked_pie['selection']['points']:
                selected_point = clicked_pie['selection']['points'][0]
                if 'label' in selected_point:
                    st.session_state.selected_broker = selected_point['label']
                    st.rerun()

        with col2:
            st.subheader('📈 P&L by Underlying (Click for details)')
            underlying_pnl = df_trades_filtered.groupby('Underlying')['Net Total'].sum().reset_index()
            underlying_pnl = underlying_pnl.sort_values('Net Total', ascending=False)

            fig4 = px.bar(underlying_pnl, x='Underlying', y='Net Total',
                         color='Net Total', color_continuous_scale='RdYlGn',
                         title='Profit/Loss by Underlying')

            # Add click handling for bar chart
            clicked_bar = st.plotly_chart(fig4, width='stretch', on_select="rerun")

            if clicked_bar and 'selection' in clicked_bar and clicked_bar['selection']['points']:
                selected_point = clicked_bar['selection']['points'][0]
                if 'x' in selected_point:
                    st.session_state.selected_underlying = selected_point['x']
                    st.rerun()

        # Trade timing analysis
        st.subheader('⏰ Trade Timing Analysis')
        col1, col2 = st.columns(2)

        with col1:
            # Trades by day of week
            df_trades_filtered['Day_of_Week'] = df_trades_filtered['Date'].dt.day_name()
            dow_pnl = df_trades_filtered.groupby('Day_of_Week')['Net Total'].agg(['sum', 'count']).reset_index()
            dow_pnl.columns = ['Day', 'Total_PnL', 'Trade_Count']
            dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            dow_pnl['Day'] = pd.Categorical(dow_pnl['Day'], categories=dow_order, ordered=True)
            dow_pnl = dow_pnl.sort_values('Day')

            fig5 = px.bar(dow_pnl, x='Day', y='Total_PnL', color='Total_PnL',
                         color_continuous_scale='RdYlGn', title='P&L by Day of Week')
            st.plotly_chart(fig5, width='stretch')

        with col2:
            # Trades by time of day (if time data available)
            if 'Time' in df_trades_filtered.columns:
                df_trades_filtered['Hour'] = pd.to_datetime(df_trades_filtered['Time']).dt.hour
                hourly_pnl = df_trades_filtered.groupby('Hour')['Net Total'].sum().reset_index()
                fig6 = px.bar(hourly_pnl, x='Hour', y='Net Total', title='P&L by Hour of Day')
                st.plotly_chart(fig6, width='stretch')
            else:
                st.info("Time data not available for hourly analysis")

        # Broker-specific analysis
        if 'Broker' in df_trades_filtered.columns and df_trades_filtered['Broker'].notna().any():
            st.markdown("---")
            st.subheader("🏢 Broker Performance Comparison")

            broker_summary = df_trades_filtered.groupby('Broker').agg({
                'Net Total': ['sum', 'count', 'mean'],
                'Quantity': 'sum'
            }).round(2)

            broker_summary.columns = ['Total P&L', 'Trade Count', 'Avg Trade', 'Total Quantity']
            broker_summary = broker_summary.reset_index()

            # Display broker comparison table
            st.dataframe(broker_summary, use_container_width=True)

            # Broker P&L comparison chart
            fig_broker = px.bar(broker_summary, x='Broker', y='Total P&L',
                              title='P&L by Broker', color='Total P&L',
                              color_continuous_scale='RdYlGn')
            st.plotly_chart(fig_broker, width='stretch')

            # Individual broker details in expandable sections
            for broker in df_trades_filtered['Broker'].unique():
                broker_data = df_trades_filtered[df_trades_filtered['Broker'] == broker]

                with st.expander(f"📊 {broker} Details ({len(broker_data)} trades)"):
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric(f"{broker} Total P&L", f"₹{broker_data['Net Total'].sum():,.2f}")
                    with col2:
                        st.metric(f"{broker} Win Rate", f"{(broker_data['Net Total'] > 0).mean()*100:.1f}%")
                    with col3:
                        st.metric(f"{broker} Avg Trade", f"₹{broker_data['Net Total'].mean():.2f}")
                    with col4:
                        st.metric(f"{broker} Total Trades", len(broker_data))

                    # Broker-specific charts
                    col1, col2 = st.columns(2)

                    with col1:
                        # Daily P&L for this broker
                        daily_broker = broker_data.groupby('Date')['Net Total'].sum().reset_index()
                        fig_daily = px.bar(daily_broker, x='Date', y='Net Total',
                                         title=f'{broker} Daily P&L')
                        st.plotly_chart(fig_daily, width='stretch')

                    with col2:
                        # Underlying performance for this broker
                        underlying_broker = broker_data.groupby('Underlying')['Net Total'].sum().reset_index()
                        underlying_broker = underlying_broker.sort_values('Net Total', ascending=False)
                        fig_under = px.bar(underlying_broker, x='Underlying', y='Net Total',
                                         title=f'{broker} by Underlying')
                        st.plotly_chart(fig_under, width='stretch')
        st.subheader('📋 All Trades')
        col1, col2, col3 = st.columns(3)

        with col1:
            # Available sort columns (excluding date/time columns)
            sort_options = [col for col in df_trades_filtered.columns if col not in ['Date', 'Expiry'] and df_trades_filtered[col].dtype in ['int64', 'float64', 'object']]
            sort_by = st.selectbox("Sort by", sort_options, key="sort_trades")
        with col2:
            sort_order = st.selectbox("Order", ['Descending', 'Ascending'], key="sort_order")
        with col3:
            # Safe default columns that exist
            safe_defaults = []
            available_columns = df_trades_filtered.columns.tolist()
            preferred_columns = ['Date', 'Underlying', 'Type', 'Quantity', 'WAP', 'Net Total', 'Exchange']
            for col in preferred_columns:
                if col in available_columns:
                    safe_defaults.append(col)

            show_columns = st.multiselect("Show columns",
                                        available_columns,
                                        default=safe_defaults,
                                        key="show_columns")

        # Apply sorting
        ascending = sort_order == 'Ascending'
        sorted_trades = df_trades_filtered.sort_values(sort_by, ascending=ascending)

        # Show selected columns
        if show_columns:
            st.dataframe(sorted_trades[show_columns], width='stretch')
        else:
            st.dataframe(sorted_trades, width='stretch')

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
        with col4:
            avg_transaction = df_funds_filtered['Amount'].mean()
            st.metric('Avg Transaction', f'₹{avg_transaction:.2f}')

        # Funds Flow by Type with drilldown
        st.subheader('💰 Funds Flow by Type (Click segments for details)')
        funds_by_type = df_funds_filtered.groupby('Type')['Amount'].sum().reset_index()
        fig = px.pie(funds_by_type, names='Type', values='Amount',
                     color_discrete_map={'Deposit': '#90EE90', 'Withdrawal': '#FF6B6B', 'Settlement Payable': '#FFB347'},
                     title='Fund Transactions by Type')

        # Add click handling for pie chart
        clicked_pie_funds = st.plotly_chart(fig, width='stretch', on_select="rerun")

        if clicked_pie_funds and 'selection' in clicked_pie_funds and clicked_pie_funds['selection']['points']:
            selected_point = clicked_pie_funds['selection']['points'][0]
            if 'label' in selected_point:
                # Filter funds by selected type
                selected_type = selected_point['label']
                type_funds = df_funds_filtered[df_funds_filtered['Type'] == selected_type]
                st.markdown(f"### 📋 {selected_type} Transactions")
                st.dataframe(type_funds.sort_values('Date', ascending=False), width='stretch')

        # Daily Funds Flow with drilldown
        st.subheader('📅 Daily Funds Flow (Click bars for details)')
        daily_funds = df_funds_filtered.groupby(['Date', 'Type'])['Amount'].sum().reset_index()
        fig2 = px.bar(daily_funds, x='Date', y='Amount', color='Type',
                      title='Daily Fund Transactions',
                      color_discrete_map={'Deposit': '#90EE90', 'Withdrawal': '#FF6B6B', 'Settlement Payable': '#FFB347'})

        # Add click handling for bar chart
        clicked_bar_funds = st.plotly_chart(fig2, width='stretch', on_select="rerun")

        if clicked_bar_funds and 'selection' in clicked_bar_funds and clicked_bar_funds['selection']['points']:
            selected_point = clicked_bar_funds['selection']['points'][0]
            if 'x' in selected_point and 'legendgroup' in selected_point:
                selected_date = pd.to_datetime(selected_point['x']).date()
                selected_type = selected_point['legendgroup']
                day_funds = df_funds_filtered[(df_funds_filtered['Date'].dt.date == selected_date) &
                                            (df_funds_filtered['Type'] == selected_type)]
                st.markdown(f"### 📋 {selected_type} on {selected_date}")
                st.dataframe(day_funds, width='stretch')

        # Funds by Broker with drilldown
        if 'Broker' in df_funds_filtered.columns and df_funds_filtered['Broker'].notna().any():
            st.subheader('🏢 Funds by Broker (Click bars for details)')
            broker_funds = df_funds_filtered.groupby('Broker')['Amount'].sum().reset_index()
            fig3 = px.bar(broker_funds, x='Broker', y='Amount', title='Total Funds by Broker',
                         color='Amount', color_continuous_scale='Blues')

            # Add click handling for broker bar chart
            clicked_broker_funds = st.plotly_chart(fig3, width='stretch', on_select="rerun")

            if clicked_broker_funds and 'selection' in clicked_broker_funds and clicked_broker_funds['selection']['points']:
                selected_point = clicked_broker_funds['selection']['points'][0]
                if 'x' in selected_point:
                    selected_broker_funds = selected_point['x']
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
                                title='Trading P&L vs Funds Flow Correlation',
                                trendline="ols")
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

        total_trades = len(df_trades_filtered)
        winning_trades = df_trades_filtered[df_trades_filtered['Net Total'] > 0]
        losing_trades = df_trades_filtered[df_trades_filtered['Net Total'] < 0]
        breakeven_trades = df_trades_filtered[df_trades_filtered['Net Total'] == 0]

        with col1:
            st.metric('Total Trades', total_trades)
        with col2:
            win_rate = len(winning_trades) / total_trades * 100
            st.metric('Win Rate', f'{win_rate:.1f}%')
        with col3:
            profit_factor = abs(winning_trades['Net Total'].sum() / losing_trades['Net Total'].sum()) if len(losing_trades) > 0 else float('inf')
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
            trade_results = ['Win' if x > 0 else 'Loss' if x < 0 else 'Break-even' for x in df_trades_filtered['Net Total']]
            result_counts = pd.Series(trade_results).value_counts()

            fig1 = px.pie(result_counts, names=result_counts.index, values=result_counts.values,
                         title='Trade Result Distribution',
                         color_discrete_map={'Win': '#90EE90', 'Loss': '#FF6B6B', 'Break-even': '#FFD700'})
            st.plotly_chart(fig1, width='stretch')

        with col2:
            # P&L Distribution Histogram
            fig2 = px.histogram(df_trades_filtered, x='Net Total', nbins=50,
                              title='P&L Distribution',
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
            df_trades_filtered['Week'] = df_trades_filtered['Date'].dt.to_period('W').astype(str)
            weekly_perf = df_trades_filtered.groupby('Week')['Net Total'].sum().reset_index()
            weekly_perf['Week'] = pd.to_datetime(weekly_perf['Week'])

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
            if 'Type' in df_trades_filtered.columns:
                type_perf = df_trades_filtered.groupby('Type')['Net Total'].agg(['sum', 'count', 'mean']).reset_index()
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
        if not underlying_pnl.empty:
            best_underlying = underlying_pnl.loc[underlying_pnl['Net Total'].idxmax()]
            insights.append(f"🏆 Best performing underlying: {best_underlying['Underlying']} (₹{best_underlying['Net Total']:,.2f})")

        # Trading frequency
        avg_trades_per_day = len(df_trades_filtered) / len(df_trades_filtered['Date'].dt.date.unique())
        if avg_trades_per_day > 10:
            insights.append("⚡ High trading frequency. Consider reducing to improve quality.")
        elif avg_trades_per_day < 2:
            insights.append("🐌 Low trading frequency. May have room for more opportunities.")

        for insight in insights:
            st.info(insight)

    else:
        st.info("No trades data available for analytics")
