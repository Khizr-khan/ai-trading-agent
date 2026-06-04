# ─────────────────────────────────────────
# sentiment.py
# Analyzes news headlines for sentiment
# Uses Groq LLM instead of HuggingFace
# (avoids rate limiting on GitHub Actions)
# ─────────────────────────────────────────

from groq import Groq
import os
import json
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def load_model():
    """
    No model to load anymore — using Groq API.
    Kept for compatibility with main.py.
    """
    print("  ✅ Sentiment engine ready (Groq).")


def analyze_news(headlines: list) -> dict:
    """
    Analyze a list of headlines using Groq LLM.
    Returns dict with overall sentiment and confidence.
    """
    if not headlines:
        return {
            "overall": "NEUTRAL",
            "confidence": 0.0,
            "positive_count": 0,
            "negative_count": 0,
            "breakdown": []
        }

    headlines_text = "\n".join(f"- {h}" for h in headlines)

    prompt = f"""Analyze the sentiment of these financial news headlines.
Return ONLY a JSON object, no other text.

Headlines:
{headlines_text}

Return this exact JSON format:
{{
  "overall": "POSITIVE" or "NEGATIVE" or "NEUTRAL",
  "confidence": float between 0.0 and 1.0,
  "positive_count": integer,
  "negative_count": integer,
  "neutral_count": integer,
  "breakdown": [
    {{"headline": "...", "label": "POSITIVE/NEGATIVE/NEUTRAL", "score": 0.0}}
  ]
}}"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a financial sentiment analyzer. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )

        raw = response.choices[0].message.content.strip()
        # Clean any markdown formatting
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        return result

    except Exception as e:
        print(f"  [ERROR] Sentiment analysis failed: {e}")
        return {
            "overall": "NEUTRAL",
            "confidence": 0.5,
            "positive_count": 0,
            "negative_count": 0,
            "breakdown": []
        }