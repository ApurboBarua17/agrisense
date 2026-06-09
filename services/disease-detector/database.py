"""PostgreSQL persistence for analysis results."""
import psycopg2
import os
import json

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://agrisense:agrisense@postgres-service:5432/agrisense",
)


def get_connection():
    return psycopg2.connect(DB_URL)


def init_db():
    """Create tables if they don't exist. Idempotent."""
    conn = get_connection()
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


def create_job(job_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO analysis_results (job_id, status) VALUES (%s, 'processing')",
        (job_id,),
    )
    conn.commit()
    cursor.close()
    conn.close()


def update_result(job_id: str, detection: dict, treatment: str, market_data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE analysis_results
           SET status='complete', detection=%s, treatment=%s,
               market_data=%s, updated_at=NOW()
           WHERE job_id=%s""",
        (json.dumps(detection), treatment, json.dumps(market_data), job_id),
    )
    conn.commit()
    cursor.close()
    conn.close()


def get_result(job_id: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status, detection, treatment, market_data FROM analysis_results WHERE job_id=%s",
        (job_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return {
            "status": row[0],
            "detection": row[1],
            "treatment": row[2],
            "market_data": row[3],
        }
    return None
