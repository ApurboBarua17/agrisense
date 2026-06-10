"""FastAPI wrapper around the GitHub-Models-backed treatment agent."""
from fastapi import FastAPI
from pydantic import BaseModel
import asyncio

from agent import get_treatment, setup_agent, MODEL

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
        # Don't kill the service if the connection check fails — get_treatment has its own fallback
        print(f"[foundry] setup_agent failed: {e}. Service will still serve fallback responses.")


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
        "source": f"GitHub Models ({MODEL}) + USDA Extension documents",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL}
