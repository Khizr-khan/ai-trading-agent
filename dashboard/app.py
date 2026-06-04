# ─────────────────────────────────────────
# app.py - Phase 2 Streamlit Dashboard
# Dynamic stock search, caps, alerts,
# manual buy/sell, portfolio analytics
# ─────────────────────────────────────────

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import yfinance as yf
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.memory import (
    get_portfolio, get_price_history, get_trade_history,
    get_watchlist, get_recent_decisions, add_ticker_to_watchlist,
    remove_ticker_from_watchlist, get_watchlist_tickers,
    get_stock_cap, set_stock_cap, get_all_caps,
    get_unread_alerts, mark_alert_read,
    get_user_settings, update_user_settings
)
from agent.decision_maker import execute_buy, execute_sell, calculate_portfolio_value
from agent.memory import update_portfolio, log_trade

# ─────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────
st.set_page_config(page_title="AI Trading Agent", page_icon="📈", layout="wide")
st.title("📈 AI Trading Agent Dashboard")
st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if st.button("🔄 Refresh"):
    st.rerun()

# ─────────────────────────────────────────
# ALERTS BANNER (shows at top if any)
# ─────────────────────────────────────────
alerts = get_unread_alerts()
if alerts:
    st.error(f"🚨 You have {len(alerts)} unread alert(s)!")
    for alert in alerts:
        severity_color = "🔴" if alert["severity"] == "CRITICAL" else "🟡"
        with st.expander(f"{severity_color} [{alert['severity']}] {alert['alert_type']} — {alert.get('ticker', 'Portfolio')}"):
            st.write(alert["message"])
            st.caption(alert["created_at"])
            if st.button("Mark as Read", key=f"alert_{alert['id']}"):
                mark_alert_read(alert["id"])
                st.rerun()
    st.divider()

# ─────────────────────────────────────────
# Row 1: Portfolio Summary
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
    st.metric("Invested", f"${max(invested, 0):,.2f}")
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
            cap = get_stock_cap(ticker)
            invested_amt = round(h["shares"] * h["avg_buy_price"], 2)
            holdings_data.append({
                "Ticker": ticker,
                "Shares": h["shares"],
                "Avg Buy": f"${h['avg_buy_price']}",
                "Current": f"${current}",
                "P&L": f"${pl}",
                "P&L %": f"{pl_pct_h}%",
                "Cap Used": f"${invested_amt} / ${cap}"
            })
        st.dataframe(pd.DataFrame(holdings_data), use_container_width=True, hide_index=True)
    else:
        st.info("No holdings yet.")

with col_right:
    st.subheader("📉 Price History")
    watchlist_tickers = get_watchlist_tickers()
    if watchlist_tickers:
        ticker_select = st.selectbox("Select Stock", watchlist_tickers)
        history = get_price_history(ticker_select, days=30)
        if history:
            df = pd.DataFrame(history)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["recorded_at"], y=df["price"],
                mode="lines+markers", name=ticker_select,
                line=dict(color="#00C896", width=2), marker=dict(size=4)
            ))
            fig.update_layout(
                xaxis_title="Time", yaxis_title="Price ($)",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=10, b=0), height=300
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Price history will appear after first agent run.")
    else:
        st.info("Add stocks to watchlist first.")

st.divider()

# ─────────────────────────────────────────
# Row 3: Manual Buy / Sell
# ─────────────────────────────────────────
st.subheader("🖐️ Manual Trade")
st.caption("Override the agent — buy or sell manually anytime")

col_buy, col_sell = st.columns(2)

with col_buy:
    st.write("**Manual Buy**")
    buy_ticker = st.selectbox("Stock to Buy", watchlist_tickers, key="buy_select")
    if buy_ticker:
        try:
            live_price = yf.Ticker(buy_ticker).info.get("currentPrice", 0)
            cap = get_stock_cap(buy_ticker)
            holdings = portfolio.get("holdings", {})
            already_invested = 0
            if buy_ticker in holdings:
                already_invested = holdings[buy_ticker]["shares"] * holdings[buy_ticker]["avg_buy_price"]
            remaining_cap = cap - already_invested
            max_shares = int(min(remaining_cap, cash) / live_price) if live_price > 0 else 0

            st.caption(f"Live price: ${live_price} | Cap remaining: ${remaining_cap:,.2f} | Max shares: {max_shares}")
            buy_shares = st.number_input("Shares to buy", min_value=1, max_value=max(max_shares, 1), value=1, key="buy_shares")

            if st.button("✅ Buy Now"):
                if max_shares == 0:
                    st.error("Cap reached or insufficient cash.")
                else:
                    stock_data = {"price": live_price, "ticker": buy_ticker}
                    result = execute_buy(buy_ticker, live_price, portfolio, cap)
                    if result["executed"]:
                        log_trade(buy_ticker, "BUY", result["shares"], live_price,
                                  result["total_value"], None, "Manual buy by user")
                        current_prices = {buy_ticker: live_price}
                        result["portfolio"]["total_value"] = calculate_portfolio_value(
                            result["portfolio"], current_prices)
                        update_portfolio(result["portfolio"], current_prices)
                        st.success(f"Bought {result['shares']} shares of {buy_ticker} at ${live_price}")
                        st.rerun()
                    else:
                        st.error(result["reason"])
        except Exception as e:
            st.error(f"Could not fetch price: {e}")

with col_sell:
    st.write("**Manual Sell**")
    owned_tickers = list(portfolio.get("holdings", {}).keys())
    if owned_tickers:
        sell_ticker = st.selectbox("Stock to Sell", owned_tickers, key="sell_select")
        holding = portfolio["holdings"][sell_ticker]
        try:
            live_price = yf.Ticker(sell_ticker).info.get("currentPrice", holding["avg_buy_price"])
            st.caption(f"Live price: ${live_price} | You own: {holding['shares']} shares")
            if st.button("✅ Sell All"):
                result = execute_sell(sell_ticker, live_price, portfolio)
                if result["executed"]:
                    log_trade(sell_ticker, "SELL", result["shares"], live_price,
                              result["total_value"], result["profit_loss"], "Manual sell by user")
                    current_prices = {sell_ticker: live_price}
                    result["portfolio"]["total_value"] = calculate_portfolio_value(
                        result["portfolio"], current_prices)
                    update_portfolio(result["portfolio"], current_prices)
                    st.success(f"Sold {result['shares']} shares of {sell_ticker} | P&L: ${result['profit_loss']}")
                    st.rerun()
                else:
                    st.error(result["reason"])
        except Exception as e:
            st.error(f"Could not fetch price: {e}")
    else:
        st.info("No stocks owned to sell.")

st.divider()

# ─────────────────────────────────────────
# Row 4: Good / Bad Stocks
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
# Row 5: Trade History
# ─────────────────────────────────────────
st.subheader("📋 Full Trade History")
trades = get_trade_history()
col_added, col_removed = st.columns(2)

with col_added:
    st.write("**➕ Stocks Added**")
    buys = [t for t in trades if t["action"] == "BUY"]
    if buys:
        df_buys = pd.DataFrame(buys)[["ticker", "shares", "price", "total_value", "executed_at"]]
        df_buys.columns = ["Ticker", "Shares", "Price", "Total Cost", "Date"]
        st.dataframe(df_buys, use_container_width=True, hide_index=True)
    else:
        st.info("No buys yet.")

with col_removed:
    st.write("**➖ Stocks Removed**")
    sells = [t for t in trades if t["action"] == "SELL"]
    if sells:
        df_sells = pd.DataFrame(sells)[["ticker", "shares", "price", "total_value", "profit_loss", "executed_at"]]
        df_sells.columns = ["Ticker", "Shares", "Price", "Total", "P&L", "Date"]
        st.dataframe(df_sells, use_container_width=True, hide_index=True)
    else:
        st.info("No sells yet.")

st.divider()

# ─────────────────────────────────────────
# Row 6: Agent Reasoning Log
# ─────────────────────────────────────────
st.subheader("🧠 Agent Reasoning Log")
decisions = get_recent_decisions(limit=50)
if decisions:
    df_decisions = pd.DataFrame(decisions)[["ticker", "action", "confidence", "risk_level", "reasoning", "decided_at"]]
    df_decisions.columns = ["Ticker", "Action", "Confidence", "Risk", "Reasoning", "Date"]
    st.dataframe(df_decisions, use_container_width=True, hide_index=True)
else:
    st.info("Agent reasoning will appear here after first run.")

st.divider()

# ─────────────────────────────────────────
# Row 7: Manage Watchlist + Caps
# ─────────────────────────────────────────
st.subheader("⚙️ Manage Watchlist & Investment Caps")

col_add, col_remove = st.columns(2)

with col_add:
    st.write("**Add a Stock**")
    search_query = st.text_input("Search by name or ticker (e.g. Apple or AAPL)")
    if search_query:
        try:
            ticker_obj = yf.Ticker(search_query.upper())
            info = ticker_obj.info
            company_name = info.get("longName", "Unknown")
            current_price = info.get("currentPrice", info.get("regularMarketPrice", 0))

            if company_name != "Unknown" and current_price:
                st.success(f"Found: **{company_name}** ({search_query.upper()}) — ${current_price}")
                cap_amount = st.number_input("Set investment cap ($)", min_value=100,
                                             max_value=10000, value=2000, step=100,
                                             key="new_cap")
                if st.button("➕ Add to Watchlist"):
                    add_ticker_to_watchlist(search_query.upper())
                    set_stock_cap(search_query.upper(), cap_amount)
                    st.success(f"{search_query.upper()} added with ${cap_amount} cap!")
                    st.rerun()
            else:
                st.warning("Ticker not found. Try the exact ticker symbol (e.g. AAPL, TSLA)")
        except Exception as e:
            st.warning("Could not find that stock. Try the exact ticker symbol.")

with col_remove:
    st.write("**Remove a Stock**")
    current_tickers = get_watchlist_tickers()
    if current_tickers:
        ticker_to_remove = st.selectbox("Select ticker to remove", current_tickers)
        if st.button("➖ Remove Stock"):
            remove_ticker_from_watchlist(ticker_to_remove)
            st.success(f"{ticker_to_remove} removed!")
            st.rerun()
    else:
        st.info("No stocks in watchlist.")

st.divider()

# ─────────────────────────────────────────
# Row 8: Investment Caps Overview
# ─────────────────────────────────────────
st.subheader("💰 Investment Caps")
caps = get_all_caps()
if caps:
    caps_data = []
    for cap in caps:
        ticker = cap["ticker"]
        max_inv = cap["max_investment"]
        holding = portfolio.get("holdings", {}).get(ticker, {})
        invested = round(holding.get("shares", 0) * holding.get("avg_buy_price", 0), 2)
        remaining = round(max_inv - invested, 2)
        caps_data.append({
            "Ticker": ticker,
            "Max Investment": f"${max_inv:,.2f}",
            "Invested": f"${invested:,.2f}",
            "Remaining": f"${remaining:,.2f}",
            "Usage": f"{round((invested/max_inv)*100, 1)}%" if max_inv > 0 else "0%"
        })
    st.dataframe(pd.DataFrame(caps_data), use_container_width=True, hide_index=True)

    st.write("**Update a Cap**")
    cap_ticker = st.selectbox("Select stock", [c["ticker"] for c in caps], key="cap_select")
    new_cap = st.number_input("New cap amount ($)", min_value=100,
                               max_value=10000, value=2000, step=100)
    if st.button("💾 Update Cap"):
        set_stock_cap(cap_ticker, new_cap)
        st.success(f"Cap for {cap_ticker} updated to ${new_cap}")
        st.rerun()
else:
    st.info("No caps set yet. Add stocks to watchlist first.")

st.divider()

# ─────────────────────────────────────────
# Row 9: User Settings
# ─────────────────────────────────────────
st.subheader("🛠️ Agent Settings")
settings = get_user_settings()

risk = st.selectbox("Risk Tolerance",
                    ["conservative", "moderate", "aggressive"],
                    index=["conservative", "moderate", "aggressive"].index(
                        settings.get("risk_tolerance", "conservative")))
email = st.text_input("Notification Email (for alerts)",
                      value=settings.get("notification_email") or "")

if st.button("💾 Save Settings"):
    update_user_settings(risk, email)
    st.success("Settings saved!")