"""Edit source and keyword configuration here; application code stays unchanged.

Direct feeds verified by fetching RSS on 2026-10-07. Google News queries are
supplemental discovery feeds; their links and attribution stay as supplied.
"""

from urllib.parse import urlencode

from src.models import NewsSource


def google_news(name: str, query: str, category: str = "aviation") -> NewsSource:
    return NewsSource(
        name=f"Google News: {name}",
        url="https://news.google.com/rss/search?"
        + urlencode(
            {
                "q": query + " when:1d",
                "hl": "en-US",
                "gl": "US",
                "ceid": "US:en",
            }
        ),
        category=category,
        priority=3,
    )


SOURCES = [
    NewsSource(name="AirlineGeeks", url="https://airlinegeeks.com/feed/", category="aviation"),
    NewsSource(name="TechCrunch", url="https://techcrunch.com/feed/", category="technology"),
    NewsSource(
        name="Ars Technica",
        url="https://feeds.arstechnica.com/arstechnica/index",
        category="technology",
    ),
    google_news(
        "Airline technology",
        'airline (technology OR "artificial intelligence" '
        'OR "digital transformation" OR biometrics OR cybersecurity)',
    ),
    google_news(
        "Airline operations",
        'airline ("disruption management" OR "revenue management" '
        'OR "dynamic pricing" OR "predictive maintenance" OR NDC OR "ONE Order")',
    ),
    google_news(
        "Türkiye competitors",
        '("Pegasus Airlines" OR "Turkish Airlines" OR AJet) '
        "(digital OR technology OR operations OR mobile OR partnership)",
    ),
    google_news(
        "European benchmarks",
        '(Ryanair OR easyJet OR "Wizz Air" OR Lufthansa '
        'OR Eurowings OR Vueling OR "Air France" OR KLM OR "British Airways" OR Iberia) '
        "(technology OR digital OR operations OR customer)",
    ),
    google_news(
        "Global benchmarks",
        '(JetBlue OR Southwest OR "Delta Air Lines" '
        'OR "United Airlines" OR Emirates OR "Qatar Airways" OR "Singapore Airlines") '
        "(technology OR digital OR operations OR customer)",
    ),
    google_news(
        "Aviation infrastructure",
        "(IATA OR EASA OR EUROCONTROL OR SITA OR Amadeus "
        "OR Sabre OR Travelport OR Airbus OR Boeing) "
        "(airline OR airport OR regulation OR technology OR sustainability)",
    ),
]

# Broad enough for unexpected aviation developments; Gemini makes the final decision.
RELEVANT_KEYWORDS = (
    "airline",
    "airlines",
    "aviation",
    "airport",
    "aircraft",
    "flight",
    "airbus",
    "boeing",
    "ajet",
    "pegasus",
    "turkish airlines",
    "ryanair",
    "easyjet",
    "wizz air",
    "lufthansa",
    "iata",
    "easa",
    "eurocontrol",
    "sita",
    "amadeus",
    "sabre",
    "travelport",
    "artificial intelligence",
    "generative ai",
    "ai",
    "ai agent",
    "automation",
    "biometric",
    "biometrics",
    "digital identity",
    "fraud",
    "cybersecurity",
    "ransomware",
    "cloud",
    "data platform",
    "data engineering",
    "real-time analytics",
    "payment",
    "payments",
    "customer service",
    "customer experience",
    "personalization",
    "recommendation",
    "predictive",
    "machine learning",
    "computer vision",
    "optimization",
    "crm",
    "loyalty",
    "mobile app",
    "mobile applications",
    "digital twin",
    "pricing",
    "revenue management",
    "ancillary",
    "ndc",
    "one order",
    "saf",
    "sustainability",
    "check-in",
    "baggage",
    "havayolu",
    "havacılık",
    "havalimanı",
    "yapay zeka",
    "siber güvenlik",
    "ödeme",
)
EXCLUDED_TITLE_PHRASES = (
    "smartphone rumor",
    "iphone rumor",
    "gaming review",
    "game review",
    "phone review",
    "best gaming",
    "celebrity",
    "horoscope",
    "unboxing",
    "discount code",
    "sponsored post",
    "affiliate deal",
    "best deals",
    "hands-on review",
)
