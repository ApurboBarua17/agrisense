"""FastAPI wrapper around the Azure AI Foundry agent."""
from fastapi import FastAPI
from pydantic import BaseModel
import asyncio

from agent import get_treatment, setup_agent, FALLBACK_MODE

app = FastAPI(title="AgriSense Foundry IQ Service")


class TreatmentRequest(BaseModel):
    crop: str
    disease: str
    severity: str = "moderate"


@app.on_event("startup")
async def startup():
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, setup_agent)
    except Exception as e:
        # Don't kill the service if Azure setup fails — fall back to stub responses
        print(f"[foundry] setup_agent failed: {e}. Service will run in fallback mode.")


@app.post("/treatment")
async def get_treatment_endpoint(req: TreatmentRequest):
    loop = asyncio.get_event_loop()
    treatment = await loop.run_in_executor(
        None, get_treatment, req.crop, req.disease, req.severity
    )
    return {
        "crop": req.crop,
        "disease": req.disease,
        "treatment": treatment,
        "source": (
            "Fallback (Azure not configured)"
            if FALLBACK_MODE
            else "Azure AI Foundry (Foundry IQ) + USDA Extension Documents"
        ),
    }


@app.get("/health")
async def health():
    return {"status": "ok", "mode": "fallback" if FALLBACK_MODE else "azure"}
