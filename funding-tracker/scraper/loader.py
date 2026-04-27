"""
What this file does: loads cleaned CSV into Postgres and raw JSON into MongoDB (so we keep both clean + raw)

How I built this: I made Postgres the main "query" store for the dashboard (filters/pagination is easier in SQL),
and MongoDB just stores the raw scraped docs so we can audit/reprocess without losing original text.

Things I learned while writing this:
- mixing SQL + NoSQL actually makes sense here (raw is messy, clean is structured)
- parameterized inserts / conflict handling prevents duplicate URL issues
- Mongo upsert is nice because rerunning the pipeline doesn't create duplicates
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

import pandas as pd
import psycopg2
import pymongo
from dotenv import load_dotenv

load_dotenv()


def setup_logging() -> None:
    """Configure loader logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _pg_conn_params() -> Dict[str, Any]:
    """Build PostgreSQL connection params from environment variables."""
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "funding_db"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }


def _ensure_pg_schema(cur: Any) -> None:
    """Create the startup_funding table and indexes if missing."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS startup_funding
        (
          id VARCHAR(100) PRIMARY KEY,
          startup_name VARCHAR(300) NOT NULL,
          funding_amount_raw VARCHAR(200),
          funding_amount_usd_mn FLOAT,
          funding_round VARCHAR(100),
          sector VARCHAR(100),
          investor_names TEXT,
          city VARCHAR(100),
          date_published VARCHAR(20),
          days_since_funding INTEGER,
          date_was_estimated BOOLEAN DEFAULT FALSE,
          article_url VARCHAR(1000) UNIQUE,
          source VARCHAR(50),
          lead_score INTEGER DEFAULT 1,
          lead_priority VARCHAR(20) DEFAULT 'Unknown',
          scraped_at TIMESTAMP
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sector ON startup_funding(sector);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_score ON startup_funding(lead_score);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_date ON startup_funding(date_published);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_priority ON startup_funding(lead_priority);")


def load_to_postgres(cleaned_csv_path: str) -> Tuple[int, int]:
    """Load cleaned CSV to PostgreSQL with upsert-do-nothing on article_url."""
    df = pd.read_csv(cleaned_csv_path)
    needed = [
        "id",
        "startup_name",
        "funding_amount_raw",
        "funding_amount_usd_mn",
        "funding_round",
        "sector",
        "investor_names",
        "city",
        "date_published",
        "days_since_funding",
        "date_was_estimated",
        "article_url",
        "source",
        "lead_score",
        "lead_priority",
        "scraped_at",
    ]
    for c in needed:
        if c not in df.columns:
            df[c] = None

    rows = [
        (
            str(r["id"]),
            str(r["startup_name"]),
            None if pd.isna(r["funding_amount_raw"]) else str(r["funding_amount_raw"]),
            None if pd.isna(r["funding_amount_usd_mn"]) else float(r["funding_amount_usd_mn"]),
            None if pd.isna(r["funding_round"]) else str(r["funding_round"]),
            None if pd.isna(r["sector"]) else str(r["sector"]),
            None if pd.isna(r["investor_names"]) else str(r["investor_names"]),
            None if pd.isna(r["city"]) else str(r["city"]),
            None if pd.isna(r["date_published"]) else str(r["date_published"]),
            None if pd.isna(r["days_since_funding"]) else int(r["days_since_funding"]),
            bool(r["date_was_estimated"]) if not pd.isna(r["date_was_estimated"]) else False,
            None if pd.isna(r["article_url"]) else str(r["article_url"]),
            None if pd.isna(r["source"]) else str(r["source"]),
            None if pd.isna(r["lead_score"]) else int(r["lead_score"]),
            None if pd.isna(r["lead_priority"]) else str(r["lead_priority"]),
            pd.to_datetime(r["scraped_at"], errors="coerce").to_pydatetime()
            if not pd.isna(r["scraped_at"])
            else datetime.now(),
        )
        for _, r in df.iterrows()
    ]

    inserted = 0
    skipped = 0
    conn = psycopg2.connect(**_pg_conn_params())
    try:
        with conn:
            with conn.cursor() as cur:
                _ensure_pg_schema(cur)
                insert_sql = """
                    INSERT INTO startup_funding (
                      id, startup_name, funding_amount_raw, funding_amount_usd_mn,
                      funding_round, sector, investor_names, city, date_published,
                      days_since_funding, date_was_estimated, article_url, source,
                      lead_score, lead_priority, scraped_at
                    )
                    VALUES (
                      %s, %s, %s, %s,
                      %s, %s, %s, %s, %s,
                      %s, %s, %s, %s,
                      %s, %s, %s
                    )
                    ON CONFLICT (article_url) DO NOTHING;
                """
                cur.executemany(insert_sql, rows)
                # rowcount after executemany is a bit inconsistent, so this is a best-effort count
                if cur.rowcount and cur.rowcount > 0:
                    inserted = int(cur.rowcount)
                    skipped = max(0, len(rows) - inserted)
                else:
                    # fallback: check how many of our URLs exist after insert
                    urls = [r[11] for r in rows if r[11]]
                    if urls:
                        cur.execute("SELECT COUNT(*) FROM startup_funding WHERE article_url = ANY(%s);", (urls,))
                        present = int(cur.fetchone()[0])
                        inserted = min(present, len(rows))
                        skipped = max(0, len(rows) - inserted)
                    else:
                        inserted = 0
                        skipped = len(rows)
    finally:
        conn.close()
    return inserted, skipped


def load_to_mongo(raw_json_path: str) -> int:
    """Upsert raw JSON documents into MongoDB for audit trail."""
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    client = pymongo.MongoClient(mongo_uri)
    db = client["funding_tracker"]
    col = db["raw_fundings"]

    raw_text = Path(raw_json_path).read_text(encoding="utf-8")
    records: List[Dict[str, Any]] = json.loads(raw_text) if raw_text.strip() else []
    upserted = 0

    for rec in records:
        if not isinstance(rec, dict):
            continue
        rec = dict(rec)
        rec["loaded_at"] = datetime.now()
        article_url = rec.get("article_url")
        if not article_url:
            continue
        res = col.update_one({"article_url": article_url}, {"$set": rec}, upsert=True)
        # res.upserted_id is set only on insert; count upserts as processed.
        if res.acknowledged:
            upserted += 1

    client.close()
    return upserted


def main() -> None:
    """Run loader to PostgreSQL and MongoDB and print summary."""
    setup_logging()
    start = time.time()

    cleaned_csv = "data/cleaned/cleaned_funding.csv"
    raw_json = "data/raw/raw_funding.json"

    inserted_pg, skipped_pg = load_to_postgres(cleaned_csv)
    upserted_mongo = load_to_mongo(raw_json)

    elapsed = round(time.time() - start, 2)
    logging.info("=== LOADING COMPLETE ===")
    logging.info("PostgreSQL: %s inserted, %s skipped", inserted_pg, skipped_pg)
    logging.info("MongoDB: %s upserted", upserted_mongo)
    logging.info("Time taken: %ss", elapsed)


if __name__ == "__main__":
    if os.path.basename(os.getcwd()) != "funding-tracker" and os.path.isdir("funding-tracker"):
        os.chdir("funding-tracker")
    from pathlib import Path

    main()
