"""
Redis queue worker — KEDA scales this pod based on queue depth.
When queue is empty, KEDA scales to 0 replicas.
When jobs arrive, KEDA scales up 0 → N replicas automatically.
"""
import redis
import json
import os
import requests
import time

from model import detect_disease
from database import init_db, update_result

REDIS_HOST = os.environ.get("REDIS_HOST", "redis-service")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
QUEUE_NAME = "disease_jobs"

FOUNDRY_IQ_URL = os.environ.get("FOUNDRY_IQ_URL", "http://foundry-iq-service:8001")
MARKET_INTEL_URL = os.environ.get("MARKET_INTEL_URL", "http://market-intel-service:8002")

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)


def process_job(job_data: dict):
    job_id = job_data["job_id"]
    image_bytes = bytes.fromhex(job_data["image_hex"])

    print(f"[worker] Processing job {job_id}")

    # Step 1: detect disease
    detection = detect_disease(image_bytes)
    print(
        f"[worker] Detection: {detection['crop']} - {detection['disease']} "
        f"({detection['confidence']}%)"
    )

    # Step 2: get treatment from Foundry IQ (skip if plant is healthy)
    treatment = "Treatment information unavailable"
    if not detection["is_healthy"]:
        try:
            resp = requests.post(
                f"{FOUNDRY_IQ_URL}/treatment",
                json={
                    "crop": detection["crop"],
                    "disease": detection["disease"],
                    "severity": detection["severity"],
                },
                timeout=60,
            )
            if resp.status_code == 200:
                treatment = resp.json().get("treatment", treatment)
        except Exception as e:
            print(f"[worker] Foundry IQ error: {e}")

    # Step 3: get market intelligence
    market_data = {}
    try:
        resp = requests.post(
            f"{MARKET_INTEL_URL}/forecast",
            json={"crop": detection["crop"]},
            timeout=60,
        )
        if resp.status_code == 200:
            market_data = resp.json()
    except Exception as e:
        print(f"[worker] Market intel error: {e}")

    # Step 4: save result to PostgreSQL
    update_result(job_id, detection, treatment, market_data)
    print(f"[worker] Job {job_id} complete")


def main():
    print("[worker] Starting disease detector worker...")
    print(f"[worker] Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}")

    # Wait for dependencies, then init schema (idempotent)
    for attempt in range(10):
        try:
            init_db()
            break
        except Exception as e:
            print(f"[worker] init_db retry {attempt + 1}: {e}")
            time.sleep(3)

    print(f"[worker] Listening on queue: {QUEUE_NAME}")
    print("[worker] KEDA will scale this pod to 0 when queue is empty")

    while True:
        try:
            result = r.blpop(QUEUE_NAME, timeout=10)
            if result:
                _, raw = result
                job_data = json.loads(raw.decode("utf-8"))
                process_job(job_data)
        except redis.ConnectionError as e:
            print(f"[worker] Redis connection error: {e}. Retrying in 5s...")
            time.sleep(5)
        except Exception as e:
            print(f"[worker] Error processing job: {e}")


if __name__ == "__main__":
    main()
