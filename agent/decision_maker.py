# ─────────────────────────────────────────
# decision_maker.py
# Executes trading decisions on the simulated portfolio
# Now respects per-stock investment caps
# ─────────────────────────────────────────

import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

MAX_POSITION_SIZE = float(os.getenv("MAX_POSITION_SIZE", 0.20))
STOP_LOSS_THRESHOLD = float(os.getenv("STOP_LOSS_THRESHOLD", -0.05))


def execute_decision(ticker: str, action: str, stock_data: dict,
                     portfolio: dict, stock_cap: float = 2000.0) -> dict:
    """
    Main function — takes the LLM's decision and executes it.
    Respects per-stock investment cap.
    """
    price = stock_data["price"]

    # Check stop loss first — overrides everything
    holdings = portfolio.get("holdings", {})
    if ticker in holdings:
        avg_buy = holdings[ticker]["avg_buy_price"]
        loss_pct = (price - avg_buy) / avg_buy
        if loss_pct <= STOP_LOSS_THRESHOLD:
            print(f"  ⚠️  Stop-loss triggered for {ticker}: {round(loss_pct * 100, 2)}% loss")
            return execute_sell(ticker, price, portfolio, forced=True)

    # Check risk rules
    risk_check = check_risk_rules(ticker, action, stock_data, portfolio, stock_cap)
    if not risk_check["allowed"]:
        print(f"  🚫 Trade blocked: {risk_check['reason']}")
        return {
            "executed": False,
            "action": "HOLD",
            "reason": risk_check["reason"],
            "portfolio": portfolio
        }

    if action == "BUY":
        return execute_buy(ticker, price, portfolio, stock_cap)
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


def execute_buy(ticker: str, price: float,
                portfolio: dict, stock_cap: float = 2000.0) -> dict:
    """
    Simulates buying a stock within the investment cap.
    """
    cash = portfolio.get("cash", 0)
    holdings = portfolio.get("holdings", {})

    # Calculate how much is already invested in this stock
    already_invested = 0
    if ticker in holdings:
        already_invested = holdings[ticker]["shares"] * holdings[ticker]["avg_buy_price"]

    # Remaining cap available
    remaining_cap = stock_cap - already_invested
    max_spend = min(remaining_cap, cash)

    if max_spend < price:
        return {
            "executed": False,
            "action": "HOLD",
            "reason": f"Cap reached or insufficient cash for {ticker}",
            "portfolio": portfolio
        }

    # Calculate shares to buy
    shares = int(max_spend / price)
    if shares == 0:
        return {
            "executed": False,
            "action": "HOLD",
            "reason": "Cannot buy even 1 share within cap",
            "portfolio": portfolio
        }

    total_cost = round(shares * price, 2)

    # Update portfolio
    updated_portfolio = dict(portfolio)
    updated_portfolio["cash"] = round(cash - total_cost, 2)

    updated_holdings = dict(holdings)
    if ticker in updated_holdings:
        existing = updated_holdings[ticker]
        total_shares = existing["shares"] + shares
        avg_price = round(
            ((existing["shares"] * existing["avg_buy_price"]) + total_cost) / total_shares, 2
        )
        updated_holdings[ticker] = {"shares": total_shares, "avg_buy_price": avg_price}
    else:
        updated_holdings[ticker] = {"shares": shares, "avg_buy_price": price}

    updated_portfolio["holdings"] = updated_holdings

    print(f"  ✅ BUY: {shares} shares of {ticker} @ ${price} | Total: ${total_cost} | Cap: ${stock_cap}")

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


def execute_sell(ticker: str, price: float,
                 portfolio: dict, forced: bool = False) -> dict:
    """
    Simulates selling all shares of a stock.
    forced=True means stop-loss triggered.
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

    updated_portfolio = dict(portfolio)
    updated_portfolio["cash"] = round(portfolio.get("cash", 0) + total_sale, 2)

    del holdings[ticker]
    updated_portfolio["holdings"] = holdings

    pl_emoji = "📈" if profit_loss >= 0 else "📉"
    label = "STOP-LOSS SELL" if forced else "SELL"
    print(f"  ✅ {label}: {shares} shares of {ticker} @ ${price} | Total: ${total_sale} | P&L: {pl_emoji} ${profit_loss}")

    return {
        "executed": True,
        "action": "SELL",
        "ticker": ticker,
        "shares": shares,
        "price": price,
        "total_value": total_sale,
        "profit_loss": profit_loss,
        "forced": forced,
        "portfolio": updated_portfolio
    }


def check_risk_rules(ticker: str, action: str, stock_data: dict,
                     portfolio: dict, stock_cap: float = 2000.0) -> dict:
    """
    Enforces risk management rules before any trade.
    """
    price = stock_data["price"]
    cash = portfolio.get("cash", 0)
    holdings = portfolio.get("holdings", {})

    if action == "BUY":
        # Check cash
        if cash < price:
            return {"allowed": False, "reason": f"Insufficient cash (${cash:.2f})"}

        # Check cap
        already_invested = 0
        if ticker in holdings:
            already_invested = holdings[ticker]["shares"] * holdings[ticker]["avg_buy_price"]
        if already_invested >= stock_cap:
            return {"allowed": False, "reason": f"Investment cap of ${stock_cap} reached for {ticker}"}

    if action == "SELL" and ticker not in holdings:
        return {"allowed": False, "reason": f"No shares of {ticker} to sell"}

    return {"allowed": True, "reason": "All risk checks passed"}


def calculate_portfolio_value(portfolio: dict, current_prices: dict) -> float:
    """
    Calculates total portfolio value.
    """
    total = portfolio.get("cash", 0)
    for ticker, holding in portfolio.get("holdings", {}).items():
        if ticker in current_prices:
            total += holding["shares"] * current_prices[ticker]
    return round(total, 2)


def check_alert_conditions(ticker: str, stock_data: dict,
                            portfolio: dict) -> list:
    """
    Check if any alert conditions are triggered.
    Returns list of alerts to create.
    """
    alerts = []
    holdings = portfolio.get("holdings", {})

    # Alert 1: Single stock crash
    if stock_data["change_pct"] <= -7:
        alerts.append({
            "type": "STOCK_CRASH",
            "severity": "CRITICAL",
            "ticker": ticker,
            "message": f"{ticker} dropped {stock_data['change_pct']}% today — significant single day loss detected."
        })

    # Alert 2: Stop loss approaching
    if ticker in holdings:
        avg_buy = holdings[ticker]["avg_buy_price"]
        loss_pct = ((stock_data["price"] - avg_buy) / avg_buy) * 100
        if -5 >= loss_pct > -7:
            alerts.append({
                "type": "STOP_LOSS_WARNING",
                "severity": "MEDIUM",
                "ticker": ticker,
                "message": f"{ticker} is down {round(loss_pct, 2)}% from your buy price — approaching stop loss threshold."
            })

    # Alert 3: Portfolio drawdown (checked in main.py)
    return alerts