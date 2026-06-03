# ─────────────────────────────────────────
# app.py
# Streamlit Dashboard — Frontend
# ─────────────────────────────────────────

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.memory import (
    get_portfolio,
    get_price_history,
    get_trade_history,
    get_watchlist,
    get_recent_decisions,
    add_ticker_to_watchlist,
    remove_ticker_from_watchlist,
    get_watchlist_tickers
)

# ─────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────
st.set_page_config(
    page_title="AI Trading Agent",
    page_icon="📈",
    layout="wide"
)

st.title("📈 AI Trading Agent Dashboard")
st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Auto refresh button
if st.button("🔄 Refresh Data"):
    st.rerun()

# ─────────────────────────────────────────
# Row 1: Portfolio Summary Cards
# ─────────────────────────────────────────
st.subheader("💼 Portfolio Summary")

portfolio = get_portfolio()
cash = portfolio.get("cash", 10000)
total_value = portfolio.get("total_value", 10000)
invested = total_value - cash
profit_loss = total_value - 10000
pl_pct = round((profit_loss / 10000) * 100, 2)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Value", f"${total_value:,.2f}", f"{pl_pct}%")
with col2:
    st.metric("Cash Available", f"${cash:,.2f}")
with col3:
    st.metric("Invested", f"${invested:,.2f}")
with col4:
    st.metric("Total P&L", f"${profit_loss:,.2f}", f"{pl_pct}%",
              delta_color="normal" if profit_loss >= 0 else "inverse")

st.divider()

# ─────────────────────────────────────────
# Row 2: Holdings + Price Chart
# ─────────────────────────────────────────
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("📊 Current Holdings")
    holdings = portfolio.get("holdings", {})
    if holdings:
        holdings_data = []
        for ticker, h in holdings.items():
            current = h.get("current_price", h["avg_buy_price"])
            pl = round((current - h["avg_buy_price"]) * h["shares"], 2)
            pl_pct_h = round(((current - h["avg_buy_price"]) / h["avg_buy_price"]) * 100, 2)
            holdings_data.append({
                "Ticker": ticker,
                "Shares": h["shares"],
                "Avg Buy": f"${h['avg_buy_price']}",
                "Current": f"${current}",
                "P&L": f"${pl}",
                "P&L %": f"{pl_pct_h}%"
            })
        st.dataframe(pd.DataFrame(holdings_data), use_container_width=True, hide_index=True)
    else:
        st.info("No holdings yet — agent will populate this after first run.")

with col_right:
    st.subheader("📉 Price History")
    watchlist_tickers = get_watchlist_tickers()
    ticker_select = st.selectbox("Select Stock", watchlist_tickers)

    if ticker_select:
        history = get_price_history(ticker_select, days=30)
        if history:
            df = pd.DataFrame(history)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["recorded_at"],
                y=df["price"],
                mode="lines+markers",
                name=ticker_select,
                line=dict(color="#00C896", width=2),
                marker=dict(size=4)
            ))
            fig.update_layout(
                xaxis_title="Time",
                yaxis_title="Price ($)",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=10, b=0),
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Price history will appear after first agent run.")

st.divider()

# ─────────────────────────────────────────
# Row 3: Good Stocks + Bad Stocks
# ─────────────────────────────────────────
col_good, col_bad = st.columns(2)

with col_good:
    st.subheader("✅ Good Stocks")
    good = get_watchlist("GOOD")
    if good:
        df_good = pd.DataFrame(good)[["ticker", "confidence", "reason", "last_updated"]]
        df_good.columns = ["Ticker", "Confidence", "Reason", "Last Updated"]
        st.dataframe(df_good, use_container_width=True, hide_index=True)
    else:
        st.info("Bullish stocks will appear here.")

with col_bad:
    st.subheader("🚨 Bad Stocks")
    bad = get_watchlist("BAD")
    if bad:
        df_bad = pd.DataFrame(bad)[["ticker", "confidence", "reason", "last_updated"]]
        df_bad.columns = ["Ticker", "Confidence", "Reason", "Last Updated"]
        st.dataframe(df_bad, use_container_width=True, hide_index=True)
    else:
        st.info("Bearish stocks will appear here.")

st.divider()

# ─────────────────────────────────────────
# Row 4: Stocks Added + Removed
# ─────────────────────────────────────────
col_added, col_removed = st.columns(2)

with col_added:
    st.subheader("➕ Stocks Added to Portfolio")
    trades = get_trade_history()
    buys = [t for t in trades if t["action"] == "BUY"]
    if buys:
        df_buys = pd.DataFrame(buys)[["ticker", "shares", "price", "total_value", "executed_at"]]
        df_buys.columns = ["Ticker", "Shares", "Price", "Total Cost", "Date"]
        st.dataframe(df_buys, use_container_width=True, hide_index=True)
    else:
        st.info("Buy history will appear here.")

with col_removed:
    st.subheader("➖ Stocks Removed from Portfolio")
    sells = [t for t in trades if t["action"] == "SELL"]
    if sells:
        df_sells = pd.DataFrame(sells)[["ticker", "shares", "price", "total_value", "profit_loss", "executed_at"]]
        df_sells.columns = ["Ticker", "Shares", "Price", "Total Value", "P&L", "Date"]
        st.dataframe(df_sells, use_container_width=True, hide_index=True)
    else:
        st.info("Sell history will appear here.")

st.divider()

# ─────────────────────────────────────────
# Row 5: Full Trade History
# ─────────────────────────────────────────
st.subheader("📋 Full Trade History")
if trades:
    df_trades = pd.DataFrame(trades)[["ticker", "action", "shares", "price", "total_value", "profit_loss", "reasoning", "executed_at"]]
    df_trades.columns = ["Ticker", "Action", "Shares", "Price", "Total", "P&L", "Reasoning", "Date"]
    st.dataframe(df_trades, use_container_width=True, hide_index=True)
else:
    st.info("All trades will be logged here.")

st.divider()

# ─────────────────────────────────────────
# Row 6: Agent Reasoning Log
# ─────────────────────────────────────────
st.subheader("🧠 Agent Reasoning Log")
st.caption("Every decision the agent makes — including WHY")
decisions = get_recent_decisions(limit=50)
if decisions:
    df_decisions = pd.DataFrame(decisions)[["ticker", "action", "confidence", "risk_level", "reasoning", "decided_at"]]
    df_decisions.columns = ["Ticker", "Action", "Confidence", "Risk", "Reasoning", "Date"]
    st.dataframe(df_decisions, use_container_width=True, hide_index=True)
else:
    st.info("Agent reasoning traces will appear here after first run.")

st.divider()

# ─────────────────────────────────────────
# Row 7: Manage Watchlist
# ─────────────────────────────────────────
st.subheader("⚙️ Manage Watchlist")
col_add, col_remove = st.columns(2)

with col_add:
    st.write("**Add a Stock**")
    new_ticker = st.text_input("Enter ticker symbol (e.g. NVDA)", max_chars=10)
    if st.button("➕ Add Stock"):
        if new_ticker:
            success = add_ticker_to_watchlist(new_ticker.upper())
            if success:
                st.success(f"{new_ticker.upper()} added to watchlist!")
                st.rerun()
            else:
                st.error("Failed to add ticker. Please try again.")
        else:
            st.warning("Please enter a ticker symbol.")

with col_remove:
    st.write("**Remove a Stock**")
    current_tickers = get_watchlist_tickers()
    ticker_to_remove = st.selectbox("Select ticker to remove", current_tickers)
    if st.button("➖ Remove Stock"):
        success = remove_ticker_from_watchlist(ticker_to_remove)
        if success:
            st.success(f"{ticker_to_remove} removed from watchlist!")
            st.rerun()
        else:
            st.error("Failed to remove ticker. Please try again.")