# ─────────────────────────────────────────
# brain.py
# LLM reasoning engine using Groq (free)
# This is where the agentic magic happens
# ─────────────────────────────────────────

from groq import Groq
import os
import json
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ─────────────────────────────────────────
# SYSTEM PROMPT — The agent's personality
# and trading strategy rules
# ─────────────────────────────────────────
SYSTEM_PROMPT = """
You are a conservative AI stock trading agent managing a simulated portfolio.
This is paper trading only — no real money is involved.

Your trading rules:
- If price dropped more than 3% today AND news sentiment is NEGATIVE → recommend SELL
- If price has risen for 3 or more consecutive days AND sentiment is POSITIVE → recommend BUY
- If sentiment is NEUTRAL or signals are mixed → recommend HOLD
- Never recommend putting more than 20% of portfolio value into one stock
- If a stock is already owned and sentiment turns NEGATIVE → recommend SELL
- If cash is below $500, do not BUY anything
- If you do NOT own the stock, your only valid actions are BUY or HOLD. Never recommend SELL on unowned stocks.

Your response must always be a valid JSON object with exactly these fields:
{
  "action": "BUY" or "SELL" or "HOLD",
  "confidence": integer between 0 and 100,
  "reasoning": "your explanation in 2-3 sentences",
  "risk_level": "LOW" or "MEDIUM" or "HIGH"
}

Do not include any text outside the JSON object. No preamble, no explanation, just the JSON.
"""


def build_user_prompt(stock_data: dict, portfolio: dict, sentiment: dict) -> str:
    """
    Builds the user message sent to the LLM each cycle.
    Formats all data in a clear, structured way for the model.
    """
    ticker = stock_data["ticker"]
    holdings = portfolio.get("holdings", {})
    currently_owned = ticker in holdings
    shares_owned = holdings.get(ticker, {}).get("shares", 0) if currently_owned else 0

    # Format recent headlines
    headlines_text = ""
    if stock_data.get("news"):
        headlines_text = "\n".join(f"  - {h}" for h in stock_data["news"][:5])
    else:
        headlines_text = "  - No recent news available"

    prompt = f"""
Analyze this stock and make a trading decision:

STOCK: {ticker} ({stock_data.get('company_name', ticker)})
Sector: {stock_data.get('sector', 'Unknown')}

PRICE DATA:
  Current Price:     ${stock_data['price']}
  Previous Close:    ${stock_data['prev_close']}
  Today's Change:    {stock_data['change_pct']}%
  Volume:            {stock_data.get('volume', 'N/A'):,}
  52-Week High:      ${stock_data.get('week_52_high', 'N/A')}
  52-Week Low:       ${stock_data.get('week_52_low', 'N/A')}
  Consecutive Rising Days: {stock_data.get('rising_days', 0)}

NEWS SENTIMENT:
  Overall:           {sentiment['overall']}
  Confidence:        {round(sentiment['confidence'] * 100, 1)}%
  Positive Articles: {sentiment['positive_count']}
  Negative Articles: {sentiment['negative_count']}

RECENT HEADLINES:
{headlines_text}

PORTFOLIO STATE:
  Available Cash:    ${portfolio.get('cash', 0):,.2f}
  Currently Owned:   {'Yes — ' + str(shares_owned) + ' shares' if currently_owned else 'No'}
  Total Portfolio Value: ${portfolio.get('total_value', 0):,.2f}

Based on your trading rules, what is your decision?
"""
    return prompt


def analyze_stock(stock_data: dict, portfolio: dict, sentiment: dict) -> dict:
    """
    Core agentic function — sends stock data, portfolio state,
    and sentiment to Groq LLM and gets a trading decision back.

    Returns dict with action, confidence, reasoning, risk_level.
    """
    try:
        user_prompt = build_user_prompt(stock_data, portfolio, sentiment)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",   # Free, fast Groq model
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,          # Low temperature = more consistent decisions
            max_tokens=300
        )

        raw = response.choices[0].message.content.strip()

        # Parse JSON response
        decision = json.loads(raw)

        # Validate required fields
        assert decision["action"] in ["BUY", "SELL", "HOLD"]
        assert 0 <= decision["confidence"] <= 100
        assert decision["risk_level"] in ["LOW", "MEDIUM", "HIGH"]

        print(f"  🧠 Decision: {decision['action']} | Confidence: {decision['confidence']}% | Risk: {decision['risk_level']}")
        print(f"  💬 Reasoning: {decision['reasoning']}")

        return decision

    except json.JSONDecodeError as e:
        print(f"  [ERROR] LLM returned invalid JSON: {e}")
        return {"action": "HOLD", "confidence": 0, "reasoning": "JSON parse error — defaulting to HOLD", "risk_level": "HIGH"}

    except Exception as e:
        print(f"  [ERROR] Brain analysis failed: {e}")
        return {"action": "HOLD", "confidence": 0, "reasoning": f"Error: {str(e)}", "risk_level": "HIGH"}