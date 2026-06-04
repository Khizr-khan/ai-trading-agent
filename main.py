# ─────────────────────────────────────────
# main.py
# Entry point — runs one full agent cycle
# Now with investment caps and alert system
# ─────────────────────────────────────────

import os
from dotenv import load_dotenv
from datetime import datetime

from agent.data_fetcher import get_all_stock_data
from agent.sentiment import load_model, analyze_news
from agent.brain import analyze_stock
from agent.decision_maker import (
    execute_decision,
    calculate_portfolio_value,
    check_alert_conditions
)
from agent.memory import (
    get_portfolio,
    update_portfolio,
    save_price_snapshot,
    log_trade,
    log_agent_decision,
    update_watchlist,
    get_watchlist_tickers,
    get_stock_cap,
    create_alert
)

load_dotenv()

STARTING_CASH = float(os.getenv("STARTING_CASH", 10000))


def run_agent_cycle():
    """
    One full agent cycle with caps and alerts.
    """
    print(f"\n{'='*50}")
    print(f"Agent Cycle Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    # Step 1: Load sentiment model
    load_model()

    # Step 2: Fetch portfolio
    print("\nFetching portfolio...")
    portfolio = get_portfolio()
    print(f"  💰 Cash: ${portfolio['cash']:,.2f} | Holdings: {list(portfolio['holdings'].keys()) or 'None'}")

    # Step 3: Fetch watchlist
    print("\nFetching watchlist...")
    watchlist = get_watchlist_tickers() or []
    print(f"  📋 Watching: {', '.join(watchlist)}")

    if not watchlist:
        print("[ERROR] Watchlist is empty. Exiting.")
        return

    # Step 4: Fetch all stock data
    print("\nFetching market data...")
    all_stock_data = get_all_stock_data(watchlist)

    if not all_stock_data:
        print("[ERROR] No stock data fetched. Exiting cycle.")
        return

    # Step 5: Check portfolio-level alerts
    total_value = portfolio.get("total_value", STARTING_CASH)
    portfolio_loss_pct = ((total_value - STARTING_CASH) / STARTING_CASH) * 100
    if portfolio_loss_pct <= -10:
        create_alert(
            alert_type="PORTFOLIO_DRAWDOWN",
            message=f"Portfolio has lost {round(abs(portfolio_loss_pct), 2)}% of starting value — currently at ${total_value:,.2f}",
            severity="CRITICAL"
        )

    # Step 6: Loop through each stock
    current_prices = {}

    for ticker, stock_data in all_stock_data.items():
        print(f"\n{'─'*40}")
        print(f"Analyzing {ticker} — {stock_data.get('company_name', ticker)}")
        print(f"{'─'*40}")

        current_prices[ticker] = stock_data["price"]

        # Save price snapshot
        save_price_snapshot(
            ticker=ticker,
            price=stock_data["price"],
            change_pct=stock_data["change_pct"],
            volume=stock_data.get("volume", 0)
        )

        # Check alert conditions
        stock_alerts = check_alert_conditions(ticker, stock_data, portfolio)
        for alert in stock_alerts:
            create_alert(
                alert_type=alert["type"],
                message=alert["message"],
                severity=alert["severity"],
                ticker=alert["ticker"]
            )

        # Get investment cap for this stock
        stock_cap = get_stock_cap(ticker)
        print(f"  💰 Investment cap: ${stock_cap:,.2f}")

        # Analyze sentiment
        sentiment = analyze_news(stock_data.get("news", []))
        print(f"  📰 Sentiment: {sentiment['overall']} ({round(sentiment.get('confidence', 0)*100, 1)}% confidence)")

        # Get LLM decision
        decision = analyze_stock(stock_data, portfolio, sentiment)

        # Log decision
        log_agent_decision(
            ticker=ticker,
            action=decision["action"],
            confidence=decision["confidence"],
            reasoning=decision["reasoning"],
            risk_level=decision["risk_level"]
        )

        # Update watchlist
        if decision["action"] == "BUY":
            update_watchlist(ticker, "GOOD", decision["reasoning"], decision["confidence"])
        elif decision["action"] == "SELL":
            update_watchlist(ticker, "BAD", decision["reasoning"], decision["confidence"])

        # Execute decision with cap
        result = execute_decision(
            ticker=ticker,
            action=decision["action"],
            stock_data=stock_data,
            portfolio=portfolio,
            stock_cap=stock_cap
        )

        # Log trade if executed
        if result["executed"]:
            log_trade(
                ticker=ticker,
                action=result["action"],
                shares=result["shares"],
                price=result["price"],
                total_value=result["total_value"],
                profit_loss=result.get("profit_loss"),
                reasoning=decision["reasoning"]
            )

            # Alert if stop loss was forced
            if result.get("forced"):
                create_alert(
                    alert_type="STOP_LOSS_TRIGGERED",
                    message=f"Stop-loss triggered for {ticker}. Sold {result['shares']} shares at ${result['price']}. P&L: ${result.get('profit_loss', 0)}",
                    severity="CRITICAL",
                    ticker=ticker
                )

            portfolio = result["portfolio"]

    # Step 7: Update portfolio value
    portfolio["total_value"] = calculate_portfolio_value(portfolio, current_prices)
    update_portfolio(portfolio, current_prices)

    print(f"\n{'='*50}")
    print(f"Cycle Complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Portfolio Value: ${portfolio['total_value']:,.2f} | Cash: ${portfolio['cash']:,.2f}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    run_agent_cycle()