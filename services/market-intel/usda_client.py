"""
USDA NASS API (National Agricultural Statistics Service).
Free API — register for key at https://quickstats.nass.usda.gov/api
"""
import requests
import os
from datetime import datetime, timedelta

USDA_API_KEY = os.environ.get("USDA_NASS_API_KEY", "DEMO_KEY")
BASE_URL = "https://quickstats.nass.usda.gov/api/api_GET/"

# Map HuggingFace model crop names to USDA commodity names
CROP_TO_USDA = {
    "Tomato": "TOMATOES",
    "Apple": "APPLES",
    "Potato": "POTATOES",
    "Corn": "CORN, GRAIN",
    "Grape": "GRAPES",
    "Peach": "PEACHES",
    "Pepper": "PEPPERS",
    "Strawberry": "STRAWBERRIES",
    "Cherry": "CHERRIES",
    "Blueberry": "BLUEBERRIES",
    "Orange": "ORANGES",
    "Soybean": "SOYBEANS",
    "Squash": "SQUASH",
    "Raspberry": "RASPBERRIES",
}

# Fallback mock data — keeps the demo working when USDA API is down or key is missing
MOCK_PRICES = {
    "TOMATOES":     [0.38, 0.41, 0.39, 0.43, 0.45, 0.42, 0.47, 0.50, 0.48, 0.52, 0.55, 0.53],
    "APPLES":       [0.28, 0.30, 0.29, 0.31, 0.33, 0.32, 0.34, 0.36, 0.35, 0.38, 0.40, 0.39],
    "POTATOES":     [0.18, 0.19, 0.20, 0.21, 0.20, 0.22, 0.23, 0.24, 0.22, 0.25, 0.26, 0.25],
    "CORN, GRAIN":  [4.20, 4.35, 4.28, 4.40, 4.55, 4.48, 4.60, 4.72, 4.65, 4.80, 4.92, 4.85],
    "STRAWBERRIES": [1.20, 1.30, 1.25, 1.35, 1.40, 1.38, 1.45, 1.52, 1.48, 1.55, 1.62, 1.58],
    "GRAPES":       [0.55, 0.58, 0.56, 0.60, 0.63, 0.61, 0.65, 0.68, 0.66, 0.70, 0.73, 0.71],
}


def get_historical_prices(crop: str) -> list[dict]:
    """
    Returns list of {ds: date_string, y: price} for Prophet.
    Tries USDA API first, falls back to mock data.
    """
    usda_commodity = CROP_TO_USDA.get(crop, crop.upper())

    if USDA_API_KEY and USDA_API_KEY != "DEMO_KEY":
        try:
            params = {
                "key": USDA_API_KEY,
                "commodity_desc": usda_commodity,
                "statisticcat_desc": "PRICE RECEIVED",
                "unit_desc": "$ / CWT",
                "year__GE": "2018",
                "format": "json",
                "agg_level_desc": "NATIONAL",
            }
            resp = requests.get(BASE_URL, params=params, timeout=10)
            data = resp.json()

            if "data" in data and len(data["data"]) > 0:
                prices = []
                month_map = {
                    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
                    "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8,
                    "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
                }
                for item in data["data"]:
                    try:
                        val = float(item["Value"].replace(",", ""))
                        year = int(item["year"])
                        period = item.get("reference_period_desc", "JAN")
                        month = month_map.get(period[:3].upper(), 6)
                        prices.append({
                            "ds": f"{year}-{month:02d}-01",
                            "y": val / 100,  # CWT -> per-lb approx
                        })
                    except (ValueError, KeyError):
                        continue
                if len(prices) >= 12:
                    return sorted(prices, key=lambda x: x["ds"])
        except Exception as e:
            print(f"[usda] API error: {e}, falling back to mock data")

    # Fallback: 24 months of mock historical data
    mock_vals = MOCK_PRICES.get(usda_commodity, MOCK_PRICES["TOMATOES"])
    base = datetime(2024, 1, 1)
    return [
        {
            "ds": (base + timedelta(days=30 * i)).strftime("%Y-%m-%d"),
            "y": mock_vals[i % len(mock_vals)],
        }
        for i in range(24)
    ]
