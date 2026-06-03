# ─────────────────────────────────────────
# data_fetcher.py
# Fetches live stock prices and news
# ─────────────────────────────────────────

import yfinance as yf
from newsapi import NewsApiClient
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

news_client = NewsApiClient(api_key=os.getenv("NEWS_API_KEY"))


def get_stock_price(ticker: str) -> dict:
    """
    Fetch current stock price and basic info for a given ticker.
    Returns a dict with price, change %, volume, 52w high/low.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        prev_close = info.get("previousClose", current_price)
        change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close else 0

        return {
            "ticker": ticker,
            "price": round(current_price, 2),
            "prev_close": round(prev_close, 2),
            "change_pct": round(change_pct, 2),
            "volume": info.get("volume", 0),
            "avg_volume": info.get("averageVolume", 0),
            "week_52_high": info.get("fiftyTwoWeekHigh", 0),
            "week_52_low": info.get("fiftyTwoWeekLow", 0),
            "company_name": info.get("longName", ticker),
            "sector": info.get("sector", "Unknown"),
            "fetched_at": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"[ERROR] Failed to fetch price for {ticker}: {e}")
        return None


def get_stock_history(ticker: str, days: int = 7) -> list:
    """
    Fetch historical price data for the last N days.
    Used to detect trends (rising/falling over multiple days).
    Returns a list of dicts with date and closing price.
    """
    try:
        stock = yf.Ticker(ticker)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        history = stock.history(start=start_date, end=end_date)

        result = []
        for date, row in history.iterrows():
            result.append({
                "date": date.strftime("%Y-%m-%d"),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"])
            })

        return result

    except Exception as e:
        print(f"[ERROR] Failed to fetch history for {ticker}: {e}")
        return []


def get_news(ticker: str, company_name: str) -> list:
    """
    Fetch latest news headlines for a stock.
    Returns a list of headline strings from the last 24 hours.
    """
    try:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")

        response = news_client.get_everything(
            q=f"{ticker} OR {company_name}",
            from_param=yesterday,
            to=today,
            language="en",
            sort_by="relevancy",
            page_size=5
        )

        headlines = []
        if response["status"] == "ok":
            for article in response["articles"]:
                if article["title"] and article["title"] != "[Removed]":
                    headlines.append(article["title"])

        return headlines

    except Exception as e:
        print(f"[ERROR] Failed to fetch news for {ticker}: {e}")
        return []


def get_all_stock_data(watchlist: list) -> dict:
    """
    Master function: fetches price + news + history for all stocks.
    Called by main.py every run cycle.
    Returns a dict keyed by ticker with all relevant data.
    """
    all_data = {}

    for ticker in watchlist:
        print(f"  Fetching data for {ticker}...")

        price_data = get_stock_price(ticker)
        if not price_data:
            print(f"  [SKIP] Could not fetch {ticker}, skipping.")
            continue

        history = get_stock_history(ticker, days=7)
        news = get_news(ticker, price_data.get("company_name", ticker))

        # Detect trend: count consecutive rising days
        rising_days = 0
        if len(history) >= 2:
            for i in range(len(history) - 1, 0, -1):
                if history[i]["close"] > history[i - 1]["close"]:
                    rising_days += 1
                else:
                    break

        all_data[ticker] = {
            **price_data,
            "history": history,
            "news": news,
            "rising_days": rising_days
        }

        print(f"  ✅ {ticker}: ${price_data['price']} ({price_data['change_pct']}%) | {len(news)} news articles")

    return all_data