"""
AgriSense API Gateway.

- POST /analyze     : accept image upload, queue the job in Redis, KEDA scales worker
- GET  /result/{id} : poll for status + result
- GET  /queue-depth : current Redis queue depth (great for demo)
- GET  /health      : liveness probe
"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import redis
import json
import uuid
import os
import time
import psycopg2

app = FastAPI(title="AgriSense API Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_HOST = os.environ.get("REDIS_HOST", "redis-service")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://agrisense:agrisense@postgres-service:5432/agrisense",
)


def get_db():
    return psycopg2.connect(DB_URL)


def init_db():
    """Idempotent — the worker also calls this. Either one running first is fine."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_results (
            job_id VARCHAR(255) PRIMARY KEY,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            detection JSONB,
            treatment TEXT,
            market_data JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    conn.commit()
    cursor.close()
    conn.close()


@app.on_event("startup")
def on_startup():
    # Retry — Postgres may still be coming up
    for attempt in range(15):
        try:
            init_db()
            print("[gateway] DB schema ready")
            return
        except Exception as e:
            print(f"[gateway] init_db retry {attempt + 1}: {e}")
            time.sleep(2)
    print("[gateway] WARNING: could not init DB on startup; will retry on first request")


@app.post("/analyze")
async def analyze_image(file: UploadFile = File(...)):
    """
    Accept an image upload, push a job to Redis (KEDA detects this and scales
    disease-detector). Returns a job_id for polling.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "File must be an image")

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(400, "Image too large (max 10MB)")

    job_id = str(uuid.uuid4())

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO analysis_results (job_id, status) VALUES (%s, 'pending')",
        (job_id,),
    )
    conn.commit()
    cursor.close()
    conn.close()

    job_payload = {
        "job_id": job_id,
        "image_hex": image_bytes.hex(),
        "filename": file.filename,
    }
    r.lpush("disease_jobs", json.dumps(job_payload))

    queue_depth = r.llen("disease_jobs")
    print(f"[gateway] Job {job_id} queued. Queue depth: {queue_depth}")

    return {
        "job_id": job_id,
        "status": "queued",
        "queue_depth": queue_depth,
        "message": "Image queued for analysis. Poll /result/{job_id} for status.",
    }


@app.get("/result/{job_id}")
async def get_result(job_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status, detection, treatment, market_data FROM analysis_results WHERE job_id=%s",
        (job_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        raise HTTPException(404, "Job not found")

    status, detection, treatment, market_data = row

    if status in ("pending", "processing"):
        return {"job_id": job_id, "status": status}

    return {
        "job_id": job_id,
        "status": "complete",
        "detection": detection,
        "treatment": treatment,
        "market": market_data,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/queue-depth")
async def queue_depth():
    """Shows KEDA scaling signal in real time."""
    depth = r.llen("disease_jobs")
    return {
        "queue_depth": depth,
        "note": "KEDA scales disease-detector pods based on this",
    }
