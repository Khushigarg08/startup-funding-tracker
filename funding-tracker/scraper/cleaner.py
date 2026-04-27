"""
What this file does: takes the raw scraped JSON and turns it into a cleaned CSV with consistent columns

How I built this: I kept the cleaning steps as separate functions so I could debug one thing at a time (amounts were the worst).
Whenever parsing fails I prefer filling something + keeping a flag, instead of crashing the whole pipeline.

Things I learned while writing this:
- funding amounts in news articles have too many formats to handle perfectly
- dates are messy too, so having an "estimated" flag is super useful later
- pandas makes this easy, but you still need to be careful with NaN vs empty strings
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd


def setup_logging() -> None:
    """Configure logging for the cleaning pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_raw_data(path: str) -> pd.DataFrame:
    """Load raw JSON into a DataFrame."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Raw data file not found at: {path}")
    if p.stat().st_size == 0:
        raise FileNotFoundError(f"Raw data file is empty at: {path}")

    raw = json.loads(p.read_text(encoding="utf-8"))
    if not raw:
        raise FileNotFoundError(f"Raw data contains no records at: {path}")

    df = pd.DataFrame(raw)
    return df


def parse_funding_amount(raw: str) -> float | None:
    """Parse raw funding amount string to USD millions."""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    s = s.replace(",", "")
    if s in {"", "undisclosed", "not disclosed", "n/a", "na"}:
        return None

    # funding strings look like "US$ 2 Mn", "₹40 Cr", "Undisclosed" etc, so first just grab the number part
    num_match = re.search(r"([\d.]+)", s)
    if not num_match:
        return None
    try:
        value = float(num_match.group(1))
    except ValueError:
        return None

    is_usd = ("$" in s) or ("us$" in s)
    is_inr = ("₹" in s) or ("inr" in s) or ("rs" in s)

    # USD cases are relatively clean compared to INR ones
    if is_usd:
        if "bn" in s or "billion" in s:
            return round(value * 1000.0, 2)
        if "mn" in s or "million" in s:
            return round(value, 2)
        # if "$X" without unit, I'm assuming it's in millions (not perfect but better than dropping)
        return round(value, 2)

    # INR conversions: I just hardcoded 1 Cr ≈ 0.12 USD Mn (documented in cleaning_notes.md)
    if is_inr:
        if "cr" in s or "crore" in s:
            return round(value * 0.12, 2)
        if "lakh" in s:
            # lakh amounts were super inconsistent and tiny, so I just treat them as missing
            return None
        # if "₹X" without unit, most headlines meant crore
        return round(value * 0.12, 2)

    # if currency is unknown, I'd rather return None than make up a conversion
    return None


def parse_date(raw: str) -> Tuple[str, bool]:
    """Parse raw date string to YYYY-MM-DD and return estimated flag."""
    if raw is None:
        return datetime.now().strftime("%Y-%m-%d"), True
    s = str(raw).strip()
    if not s:
        return datetime.now().strftime("%Y-%m-%d"), True

    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d"), False
        except Exception:
            continue
    return datetime.now().strftime("%Y-%m-%d"), True


SECTOR_MAP: Dict[str, str] = {
    "fintech": "Fintech",
    "payments": "Fintech",
    "banking": "Fintech",
    "insur": "Fintech",
    "lending": "Fintech",
    "saas": "SaaS",
    "software": "SaaS",
    "enterprise": "SaaS",
    "b2b": "SaaS",
    "health": "Healthtech",
    "medtech": "Healthtech",
    "pharma": "Healthtech",
    "hospital": "Healthtech",
    "ai": "AI/ML",
    "ml": "AI/ML",
    "artificial intelligence": "AI/ML",
    "machine learning": "AI/ML",
    "edtech": "Edtech",
    "education": "Edtech",
    "e-learning": "Edtech",
    "ecommerce": "E-commerce",
    "e-commerce": "E-commerce",
    "marketplace": "E-commerce",
    "retail": "E-commerce",
    "consumer": "Consumer",
    "d2c": "Consumer",
    "food": "Foodtech",
    "foodtech": "Foodtech",
    "restaurant": "Foodtech",
    "delivery": "Foodtech",
    "logistics": "Logistics",
    "supply": "Logistics",
    "wareh": "Logistics",
    "mobility": "Mobility",
    "transport": "Mobility",
    "ev": "Mobility",
    "ride": "Mobility",
    "travel": "Travel",
    "hospitality": "Travel",
    "proptech": "Proptech",
    "real estate": "Proptech",
    "realestate": "Proptech",
    "climate": "Climate",
    "clean": "Climate",
    "energy": "Climate",
    "agri": "Agritech",
    "agritech": "Agritech",
    "farming": "Agritech",
    "gaming": "Gaming",
    "games": "Gaming",
    "media": "Media",
    "content": "Media",
}


def normalize_sector(raw: str) -> str:
    """Normalize sector string using SECTOR_MAP."""
    s = str(raw or "").strip().lower()
    if not s:
        return "Other"
    for key, mapped in SECTOR_MAP.items():
        if key in s:
            return mapped
    return "Other"


def normalize_city(city: str) -> str:
    """Normalize city variants to canonical forms."""
    s = str(city or "").strip()
    if not s:
        return "Unknown"
    mapping = {
        "Bengaluru": "Bangalore",
        "Gurugram": "Gurgaon",
        "New Delhi": "Delhi",
        "Delhi NCR": "Delhi",
        "NCR": "Delhi",
    }
    return mapping.get(s, s)


def fill_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing values with sensible defaults."""
    df = df.copy()
    df.replace("", np.nan, inplace=True)
    df["investor_names"] = df.get("investor_names").fillna("Unknown")
    df["city"] = df.get("city").fillna("Unknown")
    df["funding_round"] = df.get("funding_round").fillna("Undisclosed")
    df["startup_name"] = df.get("startup_name").fillna("Unknown Startup")
    return df


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate records on (startup_name, date_published)."""
    before = len(df)
    df2 = df.drop_duplicates(subset=["startup_name", "date_published"], keep="first").copy()
    dropped = before - len(df2)
    logging.info("Deduplication: dropped %s duplicate rows", dropped)
    return df2


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived features for scoring and analytics."""
    df = df.copy()
    today = datetime.now().date()

    days: list[int] = []
    for d in df["date_published"].astype(str).tolist():
        try:
            dt = datetime.strptime(d, "%Y-%m-%d").date()
            days.append((today - dt).days)
        except Exception:
            days.append(999)
    df["days_since_funding"] = days
    df["scraped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df["lead_score"] = 0
    df["lead_priority"] = "Unknown"
    return df


def _ensure_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure required columns exist before transformation."""
    df = df.copy()
    required = [
        "startup_name",
        "funding_amount",
        "funding_round",
        "sector",
        "investor_names",
        "city",
        "date_published",
        "article_url",
        "source",
    ]
    for c in required:
        if c not in df.columns:
            df[c] = np.nan
    return df


def run_cleaning_pipeline() -> None:
    """Execute end-to-end cleaning pipeline and save cleaned CSV."""
    setup_logging()
    logging.info("Starting cleaning pipeline...")

    raw_path = "data/raw/raw_funding.json"
    out_dir = Path("data/cleaned")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cleaned_funding.csv"

    logging.info("Step 1/7: load raw JSON")
    df = load_raw_data(raw_path)
    df = _ensure_required_columns(df)
    logging.info("Loaded %s raw records", len(df))

    logging.info("Step 2/7: parse funding amounts")
    df["funding_amount_raw"] = df["funding_amount"].astype(str)
    df["funding_amount_usd_mn"] = df["funding_amount_raw"].apply(parse_funding_amount)

    logging.info("Step 3/7: parse dates")
    parsed = df["date_published"].astype(str).apply(parse_date)
    df["date_published"] = parsed.apply(lambda x: x[0])
    df["date_was_estimated"] = parsed.apply(lambda x: x[1])

    logging.info("Step 4/7: normalize sector and city")
    df["sector"] = df["sector"].apply(normalize_sector)
    df["city"] = df["city"].apply(normalize_city)

    logging.info("Step 5/7: fill missing values")
    df = fill_missing(df)

    logging.info("Step 6/7: deduplicate")
    df = deduplicate(df)

    logging.info("Step 7/7: add features and final schema")
    df = add_features(df)
    df["id"] = [str(uuid.uuid4()) for _ in range(len(df))]

    final_cols = [
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
    for c in final_cols:
        if c not in df.columns:
            df[c] = np.nan
    df = df[final_cols].copy()

    df.to_csv(out_path, index=False)

    logging.info("=== CLEANING COMPLETE ===")
    logging.info("Output: %s", str(out_path))
    logging.info("Rows: %s", len(df))
    logging.info("Non-null funding_amount_usd_mn: %s", int(df["funding_amount_usd_mn"].notna().sum()))
    logging.info("Estimated dates: %s", int(df["date_was_estimated"].sum()))


if __name__ == "__main__":
    if os.path.basename(os.getcwd()) != "funding-tracker" and Path("funding-tracker").exists():
        os.chdir("funding-tracker")
    run_cleaning_pipeline()
