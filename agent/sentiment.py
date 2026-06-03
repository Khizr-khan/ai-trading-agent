# ─────────────────────────────────────────
# sentiment.py
# Analyzes news headlines for sentiment
# Uses HuggingFace transformers locally (free)
# ─────────────────────────────────────────

from transformers import pipeline

# Global model variable — loaded once at startup
sentiment_model = None


def load_model():
    """
    Load HuggingFace sentiment analysis pipeline.
    Called once at startup to avoid reloading on every run.
    Model: distilbert-base-uncased-finetuned-sst-2-english (small + fast)
    Downloads automatically on first run (~250MB), cached after that.
    """
    global sentiment_model
    print("  Loading sentiment model...")
    sentiment_model = pipeline(
        "sentiment-analysis",
        model="distilbert-base-uncased-finetuned-sst-2-english"
    )
    print("  ✅ Sentiment model loaded.")


def analyze_headline(headline: str) -> dict:
    """
    Analyze a single news headline.
    Returns dict with:
      - label: "POSITIVE" or "NEGATIVE"
      - score: confidence 0.0 to 1.0
    """
    try:
        # Truncate headline to 512 chars (model limit)
        result = sentiment_model(headline[:512])[0]
        return {
            "headline": headline,
            "label": result["label"],
            "score": round(result["score"], 4)
        }
    except Exception as e:
        print(f"  [ERROR] Sentiment analysis failed: {e}")
        return {"headline": headline, "label": "NEUTRAL", "score": 0.5}


def analyze_news(headlines: list) -> dict:
    """
    Analyze a list of headlines and return an overall sentiment summary.
    Returns dict with:
      - overall: "POSITIVE", "NEGATIVE", or "NEUTRAL"
      - confidence: average confidence score
      - positive_count: number of positive headlines
      - negative_count: number of negative headlines
      - breakdown: list of individual headline results
    """
    if not headlines:
        return {
            "overall": "NEUTRAL",
            "confidence": 0.0,
            "positive_count": 0,
            "negative_count": 0,
            "breakdown": []
        }

    breakdown = [analyze_headline(h) for h in headlines]

    positive = [r for r in breakdown if r["label"] == "POSITIVE"]
    negative = [r for r in breakdown if r["label"] == "NEGATIVE"]

    # Determine overall sentiment by majority
    if len(positive) > len(negative):
        overall = "POSITIVE"
        confidence = round(sum(r["score"] for r in positive) / len(positive), 4)
    elif len(negative) > len(positive):
        overall = "NEGATIVE"
        confidence = round(sum(r["score"] for r in negative) / len(negative), 4)
    else:
        overall = "NEUTRAL"
        confidence = 0.5

    return {
        "overall": overall,
        "confidence": confidence,
        "positive_count": len(positive),
        "negative_count": len(negative),
        "breakdown": breakdown
    }