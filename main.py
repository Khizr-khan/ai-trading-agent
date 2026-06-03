# ─────────────────────────────────────────
# main.py
# Entry point — runs one full agent cycle
# Called by GitHub Actions 4x daily
# ─────────────────────────────────────────

import os
from dotenv import load_dotenv
from datetime import datetime

from agent.data_fetcher import get_all_stock_data
from agent.sentiment import load_model, analyze_news
from agent.brain import analyze_stock
from agent.decision_maker import execute_decision, calculate_portfolio_value
from agent.memory import (
    get_portfolio,
    update_portfolio,
    save_price_snapshot,
    log_trade,
    log_agent_decision,
    update_watchlist,
    get_watchlist_tickers
)

load_dotenv()


def run_agent_cycle():
    """
    One full agent cycle:
    1. Load sentiment model
    2. Fetch portfolio state from Supabase
    3. Fetch watchlist from Supabase
    4. Fetch all stock data
    5. For each stock: analyze sentiment → get LLM decision → execute → log
    6. Update portfolio value in Supabase
    """
    print(f"\n{'='*50}")
    print(f"Agent Cycle Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    # Step 1: Load sentiment model once
    load_model()

    # Step 2: Fetch current portfolio state from Supabase
    print("\nFetching portfolio...")
    portfolio = get_portfolio()
    print(f"  💰 Cash: ${portfolio['cash']:,.2f} | Holdings: {list(portfolio['holdings'].keys()) or 'None'}")

    # Step 3: Fetch watchlist from Supabase (dynamic — includes user added stocks)
    print("\nFetching watchlist...")
    watchlist = get_watchlist_tickers() or []
    print(f"  📋 Watching: {', '.join(watchlist)}")

    # Step 4: Fetch all stock data (prices + news + history)
    print("\nFetching market data...")
    all_stock_data = get_all_stock_data(watchlist)

    if not all_stock_data:
        print("[ERROR] No stock data fetched. Exiting cycle.")
        return

    # Step 5: Loop through each stock and make decisions
    current_prices = {}

    for ticker, stock_data in all_stock_data.items():
        print(f"\n{'─'*40}")
        print(f"Analyzing {ticker} — {stock_data.get('company_name', ticker)}")
        print(f"{'─'*40}")

        current_prices[ticker] = stock_data["price"]

        # Save price snapshot to database
        save_price_snapshot(
            ticker=ticker,
            price=stock_data["price"],
            change_pct=stock_data["change_pct"],
            volume=stock_data.get("volume", 0)
        )

        # Analyze news sentiment
        sentiment = analyze_news(stock_data.get("news", []))
        print(f"  📰 Sentiment: {sentiment['overall']} ({round(sentiment['confidence']*100, 1)}% confidence)")

        # Get LLM decision
        decision = analyze_stock(stock_data, portfolio, sentiment)

        # Log decision to database regardless of action
        log_agent_decision(
            ticker=ticker,
            action=decision["action"],
            confidence=decision["confidence"],
            reasoning=decision["reasoning"],
            risk_level=decision["risk_level"]
        )

        # Update good/bad watchlist
        if decision["action"] == "BUY":
            update_watchlist(ticker, "GOOD", decision["reasoning"], decision["confidence"])
        elif decision["action"] == "SELL":
            update_watchlist(ticker, "BAD", decision["reasoning"], decision["confidence"])

        # Execute decision on portfolio
        result = execute_decision(ticker, decision["action"], stock_data, portfolio)

        # If trade was executed, log it and update portfolio state
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
            # Update portfolio for next iteration
            portfolio = result["portfolio"]

    # Step 6: Recalculate and save total portfolio value
    portfolio["total_value"] = calculate_portfolio_value(portfolio, current_prices)
    update_portfolio(portfolio, current_prices)

    print(f"\n{'='*50}")
    print(f"Cycle Complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Portfolio Value: ${portfolio['total_value']:,.2f} | Cash: ${portfolio['cash']:,.2f}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    run_agent_cycle()