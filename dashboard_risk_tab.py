# ===== TAB 6: RISK ANALYSIS =====
with tab6:
    st.subheader('🎯 Risk Management Analysis')

    if not df_trades_filtered.empty:
        # Risk Metrics
        col1, col2, col3, col4 = st.columns(4)

        # Calculate risk metrics
        returns = df_trades_filtered['Net Total']
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
        annual_return = (cumulative_returns.iloc[-1] / len(df_trades_filtered['Date'].dt.date.unique()) * 365)
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
            'Date': df_trades_filtered['Date'],
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
                'Date': df_trades_filtered['Date'],
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

        if 'Quantity' in df_trades_filtered.columns:
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
                    st.metric('Current Avg Position', f"{df_trades_filtered['Quantity'].mean():.0f}")

                # Position size distribution
                fig_position = px.histogram(
                    df_trades_filtered, x='Quantity',
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

        if kelly_fraction < 0.1:
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