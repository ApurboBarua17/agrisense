"""Prophet-based crop price forecasting."""
import warnings

warnings.filterwarnings("ignore")

from prophet import Prophet  # noqa: E402  (imported after filterwarnings to suppress prophet startup warnings)
import pandas as pd  # noqa: E402

from usda_client import get_historical_prices  # noqa: E402


def forecast_crop_price(crop: str, weeks_ahead: int = 3) -> dict:
    """
    Forecast crop price `weeks_ahead` weeks out using Prophet.
    Returns current price, forecast, trend, and a sell-or-wait recommendation.
    """
    historical = get_historical_prices(crop)

    if len(historical) < 6:
        return {
            "current_price": 0.0,
            "forecast_price": 0.0,
            "trend": "unknown",
            "pct_change": 0.0,
            "recommendation": "Insufficient market data. Consult local agricultural office.",
            "unit": "$/lb",
            "crop": crop,
        }

    df = pd.DataFrame(historical)
    df["ds"] = pd.to_datetime(df["ds"])
    df["y"] = pd.to_numeric(df["y"])

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        seasonality_mode="multiplicative",
    )
    model.fit(df)

    # Forecast exactly `weeks_ahead` weeks into the future
    future = model.make_future_dataframe(periods=weeks_ahead, freq="W")
    forecast = model.predict(future)

    current_price = float(df["y"].iloc[-1])
    forecast_row = forecast.iloc[-1]
    forecast_price = max(0.01, round(float(forecast_row["yhat"]), 2))
    forecast_low = max(0.01, round(float(forecast_row["yhat_lower"]), 2))
    forecast_high = max(0.01, round(float(forecast_row["yhat_upper"]), 2))

    pct_change = ((forecast_price - current_price) / current_price) * 100
    trend = "up" if pct_change > 3 else "down" if pct_change < -3 else "stable"

    recommendation = _make_recommendation(
        current_price, forecast_price, pct_change, weeks_ahead
    )

    return {
        "current_price": round(current_price, 3),
        "forecast_price": forecast_price,
        "forecast_low": forecast_low,
        "forecast_high": forecast_high,
        "forecast_weeks": weeks_ahead,
        "pct_change": round(pct_change, 1),
        "trend": trend,
        "recommendation": recommendation,
        "unit": "$/lb",
        "crop": crop,
    }


def _make_recommendation(current: float, forecast: float, pct_change: float, weeks: int) -> str:
    if pct_change >= 15:
        return (
            f"WAIT TO SELL — Price expected to rise {pct_change:.1f}% in {weeks} weeks "
            f"(${current:.2f} -> ${forecast:.2f}/lb). Treat the disease now and sell at harvest."
        )
    if pct_change >= 5:
        return (
            f"SLIGHT ADVANTAGE IN WAITING — Price expected to rise {pct_change:.1f}% "
            f"in {weeks} weeks. Worthwhile if the disease can be controlled."
        )
    if pct_change <= -15:
        return (
            f"SELL NOW — Price expected to fall {abs(pct_change):.1f}% in {weeks} weeks "
            f"(${current:.2f} -> ${forecast:.2f}/lb). Sell healthy stock immediately."
        )
    if pct_change <= -5:
        return (
            f"LEAN TOWARD SELLING — Price expected to soften {abs(pct_change):.1f}% in {weeks} weeks."
        )
    return (
        f"MARKET STABLE — Price expected to stay near ${current:.2f}/lb. "
        "Focus on treating the disease for full yield."
    )
