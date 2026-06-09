"""FastAPI service exposing Prophet-based crop price forecasts."""
from fastapi import FastAPI
from pydantic import BaseModel
import asyncio

from forecaster import forecast_crop_price

app = FastAPI(title="AgriSense Market Intelligence")


class ForecastRequest(BaseModel):
    crop: str
    weeks_ahead: int = 3


@app.post("/forecast")
async def get_forecast(req: ForecastRequest):
    # Prophet is CPU-bound; run in executor so we don't block the event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, forecast_crop_price, req.crop, req.weeks_ahead
    )
    return result


@app.get("/health")
async def health():
    return {"status": "ok"}
