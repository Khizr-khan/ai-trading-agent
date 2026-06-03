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
        }, on_conflict="ticker").execute()
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