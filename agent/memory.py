# ─────────────────────────────────────────
# memory.py
# Handles all Supabase database operations
# Read/write portfolio, trades, watchlists
# ─────────────────────────────────────────

from supabase import create_client, Client
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


# ─────────────────────────────────────────
# PORTFOLIO TABLE
# ─────────────────────────────────────────

def get_portfolio() -> dict:
    """
    Fetch current portfolio state from Supabase.
    Returns dict with cash balance and all holdings.
    """
    try:
        # Get portfolio row
        portfolio_res = supabase.table("portfolio").select("*").order("id", desc=True).limit(1).execute()
        portfolio_row = portfolio_res.data[0] if portfolio_res.data else {"cash": 10000.00, "total_value": 10000.00}

        # Get all current holdings
        holdings_res = supabase.table("holdings").select("*").execute()
        holdings = {}
        for row in holdings_res.data:
            holdings[row["ticker"]] = {
                "shares": float(row["shares"]),
                "avg_buy_price": float(row["avg_buy_price"]),
                "current_price": float(row["current_price"] or 0),
            }

        return {
            "cash": float(portfolio_row["cash"]),
            "total_value": float(portfolio_row["total_value"] or 0),
            "holdings": holdings
        }

    except Exception as e:
        print(f"[ERROR] get_portfolio failed: {e}")
        return {"cash": 10000.00, "total_value": 10000.00, "holdings": {}}


def update_portfolio(portfolio: dict, current_prices: dict) -> None:
    """
    Save updated portfolio state to Supabase after each trade cycle.
    Updates both portfolio table and holdings table.
    """
    try:
        # Update portfolio table
        supabase.table("portfolio").update({
            "cash": portfolio["cash"],
            "total_value": portfolio["total_value"],
            "last_updated": datetime.now().isoformat()
        }).eq("id", 1).execute()

        # Sync holdings table
        # First delete all existing holdings
        supabase.table("holdings").delete().neq("id", 0).execute()

        # Re-insert current holdings
        for ticker, holding in portfolio.get("holdings", {}).items():
            price = current_prices.get(ticker, holding.get("avg_buy_price", 0))
            total_value = round(holding["shares"] * price, 2)
            profit_loss = round(total_value - (holding["shares"] * holding["avg_buy_price"]), 2)

            supabase.table("holdings").insert({
                "ticker": ticker,
                "shares": holding["shares"],
                "avg_buy_price": holding["avg_buy_price"],
                "current_price": price,
                "total_value": total_value,
                "profit_loss": profit_loss,
                "last_updated": datetime.now().isoformat()
            }).execute()

        print(f"  ✅ Portfolio saved to Supabase.")

    except Exception as e:
        print(f"[ERROR] update_portfolio failed: {e}")


# ─────────────────────────────────────────
# CUSTOM WATCHLIST TABLE
# ─────────────────────────────────────────

def get_watchlist_tickers() -> list:
    """
    Fetch active tickers from custom_watchlist table.
    This replaces reading from .env — fully dynamic.
    """
    try:
        res = supabase.table("custom_watchlist").select("ticker").eq("is_active", True).execute()
        return [row["ticker"] for row in res.data]
    except Exception as e:
        print(f"[ERROR] get_watchlist_tickers failed: {e}")
        return ["AAPL", "TSLA", "MSFT"]  # Fallback


def add_ticker_to_watchlist(ticker: str) -> bool:
    """
    Add a new stock ticker to the watchlist.
    Called from Streamlit dashboard when user adds a stock.
    """
    try:
        supabase.table("custom_watchlist").upsert({
            "ticker": ticker.upper(),
            "added_by": "user",
            "is_active": True,
            "added_at": datetime.now().isoformat()
        }).execute()
        return True
    except Exception as e:
        print(f"[ERROR] add_ticker_to_watchlist failed: {e}")
        return False


def remove_ticker_from_watchlist(ticker: str) -> bool:
    """
    Deactivate a ticker from the watchlist.
    """
    try:
        supabase.table("custom_watchlist").update({
            "is_active": False
        }).eq("ticker", ticker.upper()).execute()
        return True
    except Exception as e:
        print(f"[ERROR] remove_ticker_from_watchlist failed: {e}")
        return False


# ─────────────────────────────────────────
# PRICE HISTORY TABLE
# ─────────────────────────────────────────

def save_price_snapshot(ticker: str, price: float, change_pct: float, volume: int) -> None:
    """
    Save a price snapshot every run cycle (4x daily).
    """
    try:
        supabase.table("stock_prices").insert({
            "ticker": ticker,
            "price": price,
            "change_pct": change_pct,
            "volume": volume,
            "recorded_at": datetime.now().isoformat()
        }).execute()
    except Exception as e:
        print(f"[ERROR] save_price_snapshot failed: {e}")


def get_price_history(ticker: str, days: int = 30) -> list:
    """
    Fetch price history for a ticker for the last N days.
    """
    try:
        since = (datetime.now() - timedelta(days=days)).isoformat()
        res = supabase.table("stock_prices") \
            .select("*") \
            .eq("ticker", ticker) \
            .gte("recorded_at", since) \
            .order("recorded_at", desc=False) \
            .execute()
        return res.data
    except Exception as e:
        print(f"[ERROR] get_price_history failed: {e}")
        return []


# ─────────────────────────────────────────
# TRADES HISTORY TABLE
# ─────────────────────────────────────────

def log_trade(ticker: str, action: str, shares: float,
              price: float, total_value: float,
              profit_loss: float, reasoning: str) -> None:
    """
    Log every BUY/SELL trade with full details and LLM reasoning.
    Also logs to portfolio_added or portfolio_removed tables.
    """
    try:
        supabase.table("trades_history").insert({
            "ticker": ticker,
            "action": action,
            "shares": shares,
            "price": price,
            "total_value": total_value,
            "profit_loss": profit_loss,
            "reasoning": reasoning,
            "executed_at": datetime.now().isoformat()
        }).execute()

        # Log to added/removed tables
        if action == "BUY":
            supabase.table("portfolio_added").insert({
                "ticker": ticker,
                "shares": shares,
                "buy_price": price,
                "total_cost": total_value,
                "reason": reasoning,
                "added_at": datetime.now().isoformat()
            }).execute()
        elif action == "SELL":
            supabase.table("portfolio_removed").insert({
                "ticker": ticker,
                "shares": shares,
                "sell_price": price,
                "total_value": total_value,
                "profit_loss": profit_loss,
                "reason": reasoning,
                "removed_at": datetime.now().isoformat()
            }).execute()

    except Exception as e:
        print(f"[ERROR] log_trade failed: {e}")


def get_trade_history() -> list:
    """
    Fetch all historical trades ordered by most recent.
    """
    try:
        res = supabase.table("trades_history") \
            .select("*") \
            .order("executed_at", desc=True) \
            .execute()
        return res.data
    except Exception as e:
        print(f"[ERROR] get_trade_history failed: {e}")
        return []


# ─────────────────────────────────────────
# WATCHLIST TABLES (good/bad stocks)
# ─────────────────────────────────────────

def update_watchlist(ticker: str, status: str, reason: str, confidence: int) -> None:
    """
    Update good/bad stock watchlist based on agent decisions.
    status: "GOOD" or "BAD"
    """
    try:
        supabase.table("watchlist").upsert({
            "ticker": ticker,
            "status": status,
            "reason": reason,
            "confidence": confidence,
            "last_updated": datetime.now().isoformat()
        }).execute()
    except Exception as e:
        print(f"[ERROR] update_watchlist failed: {e}")


def get_watchlist(status: str) -> list:
    """
    Fetch good or bad stock watchlist.
    status: "GOOD" or "BAD"
    """
    try:
        res = supabase.table("watchlist") \
            .select("*") \
            .eq("status", status) \
            .order("last_updated", desc=True) \
            .execute()
        return res.data
    except Exception as e:
        print(f"[ERROR] get_watchlist failed: {e}")
        return []


# ─────────────────────────────────────────
# AGENT DECISIONS LOG TABLE
# ─────────────────────────────────────────

def log_agent_decision(ticker: str, action: str, confidence: int,
                       reasoning: str, risk_level: str) -> None:
    """
    Log every agent decision including HOLDs with full reasoning trace.
    """
    try:
        supabase.table("agent_decisions_log").insert({
            "ticker": ticker,
            "action": action,
            "confidence": confidence,
            "reasoning": reasoning,
            "risk_level": risk_level,
            "decided_at": datetime.now().isoformat()
        }).execute()
    except Exception as e:
        print(f"[ERROR] log_agent_decision failed: {e}")


def get_recent_decisions(limit: int = 50) -> list:
    """
    Fetch most recent agent decisions.
    """
    try:
        res = supabase.table("agent_decisions_log") \
            .select("*") \
            .order("decided_at", desc=True) \
            .limit(limit) \
            .execute()
        return res.data
    except Exception as e:
        print(f"[ERROR] get_recent_decisions failed: {e}")
        return []


# ─────────────────────────────────────────
# STOCK CAPS TABLE
# ─────────────────────────────────────────

def get_stock_cap(ticker: str) -> float:
    """
    Get maximum investment cap for a specific stock.
    Returns cap amount or default 2000.0 if not set.
    """
    try:
        res = supabase.table("stock_caps") \
            .select("max_investment") \
            .eq("ticker", ticker) \
            .eq("is_active", True) \
            .execute()
        if res.data:
            return float(res.data[0]["max_investment"])
        return 2000.0  # Default cap
    except Exception as e:
        print(f"[ERROR] get_stock_cap failed: {e}")
        return 2000.0


def set_stock_cap(ticker: str, max_investment: float) -> bool:
    """
    Set or update investment cap for a stock.
    Called from Streamlit dashboard.
    """
    try:
        supabase.table("stock_caps").upsert({
            "ticker": ticker.upper(),
            "max_investment": max_investment,
            "is_active": True
        }, on_conflict="ticker").execute()
        return True
    except Exception as e:
        print(f"[ERROR] set_stock_cap failed: {e}")
        return False


def get_all_caps() -> list:
    """
    Fetch all stock caps for dashboard display.
    """
    try:
        res = supabase.table("stock_caps") \
            .select("*") \
            .eq("is_active", True) \
            .execute()
        return res.data
    except Exception as e:
        print(f"[ERROR] get_all_caps failed: {e}")
        return []


# ─────────────────────────────────────────
# ALERTS TABLE
# ─────────────────────────────────────────

def create_alert(alert_type: str, message: str,
                 severity: str, ticker: str = None) -> None:
    """
    Create a new alert in the database.
    Called by agent when critical conditions detected.
    """
    try:
        supabase.table("alerts").insert({
            "alert_type": alert_type,
            "ticker": ticker,
            "message": message,
            "severity": severity,
            "is_read": False,
            "created_at": datetime.now().isoformat()
        }).execute()
        print(f"  🚨 ALERT created: [{severity}] {message}")
    except Exception as e:
        print(f"[ERROR] create_alert failed: {e}")


def get_unread_alerts() -> list:
    """
    Fetch all unread alerts for dashboard display.
    """
    try:
        res = supabase.table("alerts") \
            .select("*") \
            .eq("is_read", False) \
            .order("created_at", desc=True) \
            .execute()
        return res.data
    except Exception as e:
        print(f"[ERROR] get_unread_alerts failed: {e}")
        return []


def mark_alert_read(alert_id: int) -> None:
    """
    Mark an alert as read when user acknowledges it.
    """
    try:
        supabase.table("alerts") \
            .update({"is_read": True}) \
            .eq("id", alert_id) \
            .execute()
    except Exception as e:
        print(f"[ERROR] mark_alert_read failed: {e}")


# ─────────────────────────────────────────
# USER SETTINGS TABLE
# ─────────────────────────────────────────

def get_user_settings() -> dict:
    """
    Fetch user settings (risk tolerance etc.)
    """
    try:
        res = supabase.table("user_settings") \
            .select("*") \
            .order("id", desc=False) \
            .limit(1) \
            .execute()
        if res.data:
            return res.data[0]
        return {"risk_tolerance": "conservative"}
    except Exception as e:
        print(f"[ERROR] get_user_settings failed: {e}")
        return {"risk_tolerance": "conservative"}


def update_user_settings(risk_tolerance: str,
                         notification_email: str = None) -> bool:
    """
    Update user settings from dashboard.
    """
    try:
        supabase.table("user_settings").update({
            "risk_tolerance": risk_tolerance,
            "notification_email": notification_email,
            "updated_at": datetime.now().isoformat()
        }).eq("id", 1).execute()
        return True
    except Exception as e:
        print(f"[ERROR] update_user_settings failed: {e}")
        return False