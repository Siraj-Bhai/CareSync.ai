"""
create_tables.py — Creates all MindGuard Pro tables in PostgreSQL and seeds demo data.
Run: python create_tables.py
"""
import psycopg2
from datetime import datetime, timezone
import os

def now(): return datetime.now(timezone.utc)

# ── Config ────────────────────────────────────────────────────────────────────
DB = dict(
    host=os.getenv("DB_HOST_NAME", "localhost"),
    port=int(os.getenv("DB_PORT", 5432)),
    dbname=os.getenv("DB_NAME", "caresync_ai"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "admin123")
)


def connect():
    return psycopg2.connect(**DB)


# ── DDL ───────────────────────────────────────────────────────────────────────
TABLES = """
CREATE TABLE IF NOT EXISTS clinicians (
    id              VARCHAR PRIMARY KEY,
    name            VARCHAR,
    email           VARCHAR UNIQUE,
    hashed_password VARCHAR,
    phone           VARCHAR,
    role            VARCHAR DEFAULT 'user',
    user_id         VARCHAR,
    created_at      TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id                VARCHAR PRIMARY KEY,
    name              VARCHAR,
    age               INTEGER,
    clinician_id      VARCHAR REFERENCES clinicians(id),
    emergency_contact VARCHAR,
    created_at        TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id                  VARCHAR PRIMARY KEY,
    user_id             VARCHAR REFERENCES users(id),
    start_time          TIMESTAMP,
    end_time            TIMESTAMP,
    overall_risk_score  FLOAT DEFAULT 0.0,
    status              VARCHAR DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS messages (
    id                VARCHAR PRIMARY KEY,
    session_id        VARCHAR REFERENCES sessions(id),
    sender            VARCHAR,
    text              TEXT,
    audio_url         VARCHAR,
    risk_score        FLOAT,
    triggered_signals JSONB,
    timestamp         TIMESTAMP
);

CREATE TABLE IF NOT EXISTS risk_history (
    id              VARCHAR PRIMARY KEY,
    user_id         VARCHAR REFERENCES users(id),
    score           FLOAT,
    risk_level      VARCHAR,
    factors         JSONB,
    predicted_score FLOAT,
    date            TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interventions (
    id           VARCHAR PRIMARY KEY,
    user_id      VARCHAR REFERENCES users(id),
    type         VARCHAR,
    triggered_by VARCHAR,
    outcome      VARCHAR,
    timestamp    TIMESTAMP
);
"""


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute(TABLES)
        print("Tables created.")
        for sql in [
            "ALTER TABLE clinicians ADD COLUMN IF NOT EXISTS role VARCHAR DEFAULT 'user'",
            "ALTER TABLE clinicians ADD COLUMN IF NOT EXISTS user_id VARCHAR",
        ]:
            cur.execute(sql)
        conn.commit()
        print("Done.")
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()
