"""
What this file does: trains a Random Forest lead-priority model and then scores the cleaned dataset (High/Medium/Low)

How I built this: I didn't have real labels, so I first generated labels using simple business-ish rules (bootstrap),
then trained a RF on one-hot sector/round + numeric features. Model + feature columns are saved with joblib.

Things I learned while writing this:
- without labeled data you still can start with bootstrapped labels (not perfect but works as a baseline)
- saving the feature column list is important, otherwise scoring breaks when categories change
- predict_proba is super handy to convert "High" likelihood into a 0-10 score
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split


def setup_logging() -> None:
    """Configure logging for ML scorer."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def generate_labels(df: pd.DataFrame) -> pd.Series:
    """Generate bootstrap labels for training (High/Medium/Low)."""
    labels: List[str] = []
    for _, row in df.iterrows():
        score = 0
        amt = row.get("funding_amount_usd_mn")
        days = row.get("days_since_funding")
        sector = str(row.get("sector") or "")
        rnd = str(row.get("funding_round") or "")

        if pd.notna(amt) and float(amt) > 10:
            score += 4
        elif pd.notna(amt) and float(amt) >= 1:
            score += 2

        try:
            d = int(days)
        except Exception:
            d = 999
        if d <= 30:
            score += 3
        elif d <= 90:
            score += 1

        if sector in ["Fintech", "SaaS", "Healthtech", "AI/ML"]:
            score += 3

        if rnd in ["Series A", "Series B", "Series C"]:
            score += 2
        elif rnd in ["Seed", "Angel"]:
            score += 1

        if score >= 7:
            labels.append("High")
        elif score >= 4:
            labels.append("Medium")
        else:
            labels.append("Low")
    return pd.Series(labels)


def prepare_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Prepare numeric + one-hot categorical features."""
    work = df.copy()
    work["funding_amount_usd_mn"] = pd.to_numeric(work.get("funding_amount_usd_mn"), errors="coerce").fillna(0)
    work["days_since_funding"] = pd.to_numeric(work.get("days_since_funding"), errors="coerce").fillna(999)

    sector_d = pd.get_dummies(work.get("sector").fillna("Other"), prefix="sector")
    round_d = pd.get_dummies(work.get("funding_round").fillna("Undisclosed"), prefix="round")

    X = pd.concat([work[["funding_amount_usd_mn", "days_since_funding"]], sector_d, round_d], axis=1)
    feature_cols = list(X.columns)
    return X, feature_cols


def train_model(df: pd.DataFrame) -> RandomForestClassifier | None:
    """Train model and persist (model + feature_cols) to disk."""
    setup_logging()
    if len(df) < 10:
        logging.warning("Not enough data to train. Need 10+ records.")
        return None

    y = generate_labels(df)
    X, feature_cols = prepare_features(df)

    stratify = y if len(df) > 15 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=stratify
    )

    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=5,
        random_state=42,
        class_weight="balanced",
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    print(classification_report(y_test, y_pred))

    importances = pd.Series(clf.feature_importances_, index=feature_cols)
    print(importances.sort_values(ascending=False).head(10))

    Path("data/model").mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": clf, "feature_cols": feature_cols}, "data/model/lead_scorer.pkl")
    logging.info("Model saved to data/model/lead_scorer.pkl")
    return clf


def _load_model_bundle(model_path: str = "data/model/lead_scorer.pkl") -> Dict[str, Any]:
    """Load saved model bundle from disk."""
    p = Path(model_path)
    if not p.exists():
        raise FileNotFoundError(f"Model file not found at: {model_path}. Run scraper/ml_scorer.py first.")
    bundle = joblib.load(model_path)
    if not isinstance(bundle, dict) or "model" not in bundle or "feature_cols" not in bundle:
        raise ValueError("Invalid model bundle format in lead_scorer.pkl")
    return bundle


def score_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Score a DataFrame with lead_priority and lead_score columns."""
    bundle = _load_model_bundle()
    model: RandomForestClassifier = bundle["model"]
    feature_cols: List[str] = bundle["feature_cols"]

    X, _ = prepare_features(df)
    for col in feature_cols:
        if col not in X.columns:
            X[col] = 0
    X = X[feature_cols]

    preds = model.predict(X)
    proba = model.predict_proba(X)
    class_index = {c: i for i, c in enumerate(list(model.classes_))}
    high_idx = class_index.get("High", None)

    if high_idx is None:
        scores = np.zeros(len(df), dtype=int)
    else:
        scores = np.rint(proba[:, high_idx] * 10).astype(int)
        scores = np.clip(scores, 0, 10)

    out = df.copy()
    out["lead_priority"] = preds
    out["lead_score"] = scores
    return out


def score_single_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Score a single record dict and return with lead_priority/lead_score."""
    df = pd.DataFrame([record])
    scored = score_dataframe(df).iloc[0].to_dict()
    record_out = dict(record)
    record_out["lead_priority"] = str(scored.get("lead_priority", "Unknown"))
    try:
        record_out["lead_score"] = int(scored.get("lead_score", 0))
    except Exception:
        record_out["lead_score"] = 0
    return record_out


if __name__ == "__main__":
    if os.path.basename(os.getcwd()) != "funding-tracker" and Path("funding-tracker").exists():
        os.chdir("funding-tracker")
    setup_logging()

    df = pd.read_csv("data/cleaned/cleaned_funding.csv")
    train_model(df)
    df = score_dataframe(df)
    df.to_csv("data/cleaned/cleaned_funding.csv", index=False)
    print("Scoring complete.")
