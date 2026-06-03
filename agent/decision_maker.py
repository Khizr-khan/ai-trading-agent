# ─────────────────────────────────────────
# decision_maker.py
# Executes trading decisions on the simulated portfolio
# Updates portfolio, logs trades, enforces risk rules
# ─────────────────────────────────────────

import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

MAX_POSITION_SIZE = float(os.getenv("MAX_POSITION_SIZE", 0.20))
STOP_LOSS_THRESHOLD = float(os.getenv("STOP_LOSS_THRESHOLD", -0.05))


def execute_decision(ticker: str, action: str, stock_data: dict, portfolio: dict) -> dict:
    """
    Main function — takes the LLM's decision and executes it.
    Enforces risk rules before executing.
    Returns dict with updated portfolio and trade record.
    """
    price = stock_data["price"]

    # Always check risk rules first
    risk_check = check_risk_rules(ticker, action, stock_data, portfolio)

    if not risk_check["allowed"]:
        print(f"  🚫 Trade blocked: {risk_check['reason']}")
        return {
            "executed": False,
            "action": "HOLD",
            "reason": risk_check["reason"],
            "portfolio": portfolio
        }

    # Execute based on action
    if action == "BUY":
        return execute_buy(ticker, price, portfolio)
    elif action == "SELL":
        return execute_sell(ticker, price, portfolio)
    else:
        print(f"  ⏸️  HOLD — no portfolio changes.")
        return {
            "executed": False,
            "action": "HOLD",
            "reason": "Agent decided to hold",
            "portfolio": portfolio
        }


def execute_buy(ticker: str, price: float, portfolio: dict) -> dict:
    """
    Simulates buying a stock.
    Calculates how many shares to buy based on available cash
    and MAX_POSITION_SIZE rule.
    """
    total_value = portfolio.get("total_value", portfolio.get("cash", 10000))
    cash = portfolio.get("cash", 0)

    # Max amount to spend on this stock
    max_spend = min(total_value * MAX_POSITION_SIZE, cash)

    if max_spend < price:
        return {
            "executed": False,
            "action": "HOLD",
            "reason": "Not enough cash to buy even 1 share",
            "portfolio": portfolio
        }

    # Calculate shares to buy (whole shares only)
    shares = int(max_spend / price)
    total_cost = round(shares * price, 2)

    # Update portfolio
    updated_portfolio = dict(portfolio)
    updated_portfolio["cash"] = round(cash - total_cost, 2)

    # Update holdings
    holdings = dict(portfolio.get("holdings", {}))
    if ticker in holdings:
        # Average down — recalculate average buy price
        existing = holdings[ticker]
        total_shares = existing["shares"] + shares
        avg_price = round(
            ((existing["shares"] * existing["avg_buy_price"]) + total_cost) / total_shares, 2
        )
        holdings[ticker] = {"shares": total_shares, "avg_buy_price": avg_price}
    else:
        holdings[ticker] = {"shares": shares, "avg_buy_price": price}

    updated_portfolio["holdings"] = holdings

    print(f"  ✅ BUY: {shares} shares of {ticker} @ ${price} | Total: ${total_cost}")

    return {
        "executed": True,
        "action": "BUY",
        "ticker": ticker,
        "shares": shares,
        "price": price,
        "total_value": total_cost,
        "profit_loss": None,
        "portfolio": updated_portfolio
    }


def execute_sell(ticker: str, price: float, portfolio: dict) -> dict:
    """
    Simulates selling all shares of a stock.
    Calculates profit/loss vs average buy price.
    """
    holdings = dict(portfolio.get("holdings", {}))

    if ticker not in holdings:
        return {
            "executed": False,
            "action": "HOLD",
            "reason": f"No shares of {ticker} to sell",
            "portfolio": portfolio
        }

    shares = holdings[ticker]["shares"]
    avg_buy_price = holdings[ticker]["avg_buy_price"]
    total_sale = round(shares * price, 2)
    profit_loss = round(total_sale - (shares * avg_buy_price), 2)

    # Update portfolio
    updated_portfolio = dict(portfolio)
    updated_portfolio["cash"] = round(portfolio.get("cash", 0) + total_sale, 2)

    # Remove from holdings
    del holdings[ticker]
    updated_portfolio["holdings"] = holdings

    pl_emoji = "📈" if profit_loss >= 0 else "📉"
    print(f"  ✅ SELL: {shares} shares of {ticker} @ ${price} | Total: ${total_sale} | P&L: {pl_emoji} ${profit_loss}")

    return {
        "executed": True,
        "action": "SELL",
        "ticker": ticker,
        "shares": shares,
        "price": price,
        "total_value": total_sale,
        "profit_loss": profit_loss,
        "portfolio": updated_portfolio
    }


def check_risk_rules(ticker: str, action: str, stock_data: dict, portfolio: dict) -> dict:
    """
    Enforces risk management rules before any trade.
    Returns dict with allowed (bool) and reason (str).
    """
    price = stock_data["price"]
    cash = portfolio.get("cash", 0)
    holdings = portfolio.get("holdings", {})
    total_value = portfolio.get("total_value", cash)

    # Rule 1: Auto stop-loss — override HOLD with SELL if stock tanked
    if ticker in holdings:
        avg_buy = holdings[ticker]["avg_buy_price"]
        loss_pct = (price - avg_buy) / avg_buy
        if loss_pct <= STOP_LOSS_THRESHOLD:
            print(f"  ⚠️  Stop-loss triggered for {ticker}: {round(loss_pct * 100, 2)}% loss")
            return {"allowed": True, "reason": "Stop-loss triggered — forcing SELL"}

    # Rule 2: Don't buy if not enough cash
    if action == "BUY" and cash < price:
        return {"allowed": False, "reason": f"Insufficient cash (${cash:.2f}) to buy {ticker} at ${price}"}

    # Rule 3: Don't buy if position would exceed MAX_POSITION_SIZE
    if action == "BUY" and ticker in holdings:
        current_position = holdings[ticker]["shares"] * price
        if current_position / total_value >= MAX_POSITION_SIZE:
            return {"allowed": False, "reason": f"Position in {ticker} already at max size ({MAX_POSITION_SIZE*100}%)"}

    # Rule 4: Don't sell if nothing owned
    if action == "SELL" and ticker not in holdings:
        return {"allowed": False, "reason": f"No shares of {ticker} in portfolio to sell"}

    return {"allowed": True, "reason": "All risk checks passed"}


def calculate_portfolio_value(portfolio: dict, current_prices: dict) -> float:
    """
    Calculates total portfolio value:
    cash + (shares * current price) for each holding.
    """
    total = portfolio.get("cash", 0)

    for ticker, holding in portfolio.get("holdings", {}).items():
        if ticker in current_prices:
            total += holding["shares"] * current_prices[ticker]

    return round(total, 2)