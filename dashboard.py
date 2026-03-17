import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# Page config
st.set_page_config(page_title="Trading Journal Dashboard", layout="wide")

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

# Title
st.title('📊 Trading Journal Dashboard')

# Tab selection
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Trades", "💰 Funds Flow", "📌 Pledges", "📋 Summary", "📊 Analytics"])

# ===== TAB 1: TRADES =====
with tab1:
    if not df_trades.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric('Total Trades', len(df_trades))
        with col2:
            total_pnl = df_trades['Net Total'].sum()
            st.metric('Total P&L', f'₹{total_pnl:,.2f}')
        with col3:
            win_rate = (df_trades[df_trades['Net Total'] > 0].shape[0] / len(df_trades) * 100) if len(df_trades) > 0 else 0
            st.metric('Win Rate', f'{win_rate:.1f}%')
        
        st.subheader('Daily P&L')
        daily_pnl = df_trades.groupby('Date')['Net Total'].sum().reset_index()
        daily_pnl['Cumulative P&L'] = daily_pnl['Net Total'].cumsum()
        fig = px.bar(daily_pnl, x='Date', y='Net Total', title='Daily Profit/Loss',
                     color='Net Total', color_continuous_scale='RdYlGn')
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader('Cumulative P&L')
        fig2 = px.line(daily_pnl, x='Date', y='Cumulative P&L', title='Cumulative Profit/Loss',
                       markers=True)
        st.plotly_chart(fig2, use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader('Trades by Underlying')
            underlying_counts = df_trades['Underlying'].value_counts()
            fig3 = px.pie(underlying_counts, names=underlying_counts.index, values=underlying_counts.values)
            st.plotly_chart(fig3, use_container_width=True)
        
        with col2:
            st.subheader('P&L by Underlying')
            underlying_pnl = df_trades.groupby('Underlying')['Net Total'].sum().reset_index()
            underlying_pnl = underlying_pnl.sort_values('Net Total', ascending=False)
            fig4 = px.bar(underlying_pnl, x='Underlying', y='Net Total', 
                         color='Net Total', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig4, use_container_width=True)
        
        st.subheader('All Trades')
        st.dataframe(df_trades.sort_values('Date', ascending=False), use_container_width=True)
    else:
        st.info("No trades data available")

# ===== TAB 2: FUNDS FLOW =====
with tab2:
    if not df_funds.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            deposits = df_funds[df_funds['Type'] == 'Deposit']['Amount'].sum()
            st.metric('Total Deposits', f'₹{deposits:,.2f}')
        with col2:
            withdrawals = df_funds[df_funds['Type'] == 'Withdrawal']['Amount'].sum()
            st.metric('Total Withdrawals', f'₹{withdrawals:,.2f}')
        with col3:
            net_flow = deposits - withdrawals
            st.metric('Net Inflow', f'₹{net_flow:,.2f}')
        
        st.subheader('Funds Flow by Type')
        funds_by_type = df_funds.groupby('Type')['Amount'].sum().reset_index()
        fig = px.pie(funds_by_type, names='Type', values='Amount', 
                     color_discrete_map={'Deposit': '#90EE90', 'Withdrawal': '#FF6B6B', 'Settlement Payable': '#FFB347'})
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader('Daily Funds Flow')
        daily_funds = df_funds.groupby(['Date', 'Type'])['Amount'].sum().reset_index()
        fig2 = px.bar(daily_funds, x='Date', y='Amount', color='Type', 
                      title='Daily Fund Transactions',
                      color_discrete_map={'Deposit': '#90EE90', 'Withdrawal': '#FF6B6B', 'Settlement Payable': '#FFB347'})
        st.plotly_chart(fig2, use_container_width=True)
        
        st.subheader('Funds by Broker')
        broker_funds = df_funds.groupby('Broker')['Amount'].sum().reset_index()
        fig3 = px.bar(broker_funds, x='Broker', y='Amount', title='Total Funds by Broker')
        st.plotly_chart(fig3, use_container_width=True)
        
        st.subheader('All Fund Transactions')
        st.dataframe(df_funds.sort_values('Date', ascending=False), use_container_width=True)
    else:
        st.info("No funds data available. Run fetch_and_parse_gmail.py to extract fund information.")

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
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader('Pledges by Broker')
        broker_pledges = df_pledges.groupby('Broker')['Amount'].sum().reset_index()
        fig2 = px.bar(broker_pledges, x='Broker', y='Amount', title='Total Pledges by Broker')
        st.plotly_chart(fig2, use_container_width=True)
        
        st.subheader('All Pledge Records')
        st.dataframe(df_pledges.sort_values('Date', ascending=False), use_container_width=True)
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
        st.dataframe(summary_display.sort_values('Date', ascending=False), use_container_width=True)
        
        st.subheader('Trades per Day')
        fig = px.bar(df_summary, x='Date', y='Total_Trades', color='Broker',
                     title='Number of Trades by Day')
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader('Fees Trend')
        fig2 = px.line(df_summary.sort_values('Date'), x='Date', y='Total_Fees', 
                       color='Broker', markers=True, title='Daily Fees')
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No summary data available.")

# ===== TAB 5: ANALYTICS =====
with tab5:
    st.subheader('Trading Performance')
    
    if not df_trades.empty and not df_funds.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            # P&L vs Funds correlation
            daily_trades_pnl = df_trades.groupby('Date')['Net Total'].sum().reset_index()
            daily_funds_amount = df_funds.groupby('Date')['Amount'].sum().reset_index()
            
            merged = daily_trades_pnl.merge(daily_funds_amount, on='Date', how='outer').fillna(0)
            merged.columns = ['Date', 'P&L', 'Funds']
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=merged['Date'], y=merged['P&L'], name='P&L', mode='lines+markers'))
            fig.add_trace(go.Scatter(x=merged['Date'], y=merged['Funds'], name='Funds Flow', mode='lines+markers', yaxis='y2'))
            
            fig.update_layout(
                title='P&L vs Funds Flow',
                yaxis=dict(title='P&L (₹)'),
                yaxis2=dict(title='Funds (₹)', overlaying='y', side='right'),
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # ROI Analysis (if funds are available)
            total_pnl = df_trades['Net Total'].sum()
            total_funds = df_funds[df_funds['Type'] == 'Deposit']['Amount'].sum()
            roi = (total_pnl / total_funds * 100) if total_funds > 0 else 0
            
            st.metric('Return on Investment', f'{roi:.2f}%')
            st.metric('Average Daily P&L', f'₹{df_trades.groupby("Date")["Net Total"].sum().mean():.2f}')
    
    if not df_trades.empty:
        st.subheader('Trade Statistics')
        col1, col2, col3 = st.columns(3)
        
        winning_trades = df_trades[df_trades['Net Total'] > 0]
        losing_trades = df_trades[df_trades['Net Total'] < 0]
        
        with col1:
            st.metric('Winning Trades', len(winning_trades))
            if len(winning_trades) > 0:
                st.caption(f'Avg Win: ₹{winning_trades["Net Total"].mean():.2f}')
        
        with col2:
            st.metric('Losing Trades', len(losing_trades))
            if len(losing_trades) > 0:
                st.caption(f'Avg Loss: ₹{losing_trades["Net Total"].mean():.2f}')
        
        with col3:
            st.metric('Break-even Trades', len(df_trades[df_trades['Net Total'] == 0]))
        
        # Profit factor
        if len(losing_trades) > 0:
            profit_factor = abs(winning_trades['Net Total'].sum() / losing_trades['Net Total'].sum())
            st.metric('Profit Factor', f'{profit_factor:.2f}')
