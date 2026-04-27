# Data Cleaning Decisions

## Overview — why cleaning matters

Scraped funding news is messy: amounts appear in multiple currencies and units, dates are inconsistent, sectors are free-text, and some fields are missing or duplicated across syndications. This project cleans raw scraped JSON into a stable, queryable dataset that can power reliable filtering, analytics, and ML scoring.

## Decision 1: Funding Amount Standardization

**Problem:** Funding amounts appear as strings like `US$ 5 Mn`, `₹ 120 Cr`, `Rs. 50 crore`, `Undisclosed`, etc.  
**Decision:** Convert into a single numeric field `funding_amount_usd_mn` (USD millions) using heuristic rules.  
**Reason:** Numeric USD Mn enables sorting, aggregations, thresholds, and ML features.

## Decision 2: Date parsing (7+ format attempts + estimated flag)

**Problem:** Articles can expose dates via `<time datetime>`, meta tags, or plain text formats.  
**Decision:** Try multiple formats; if parsing fails, set today’s date and mark `date_was_estimated=True`.  
**Reason:** The pipeline must never break due to date format drift; estimated flag keeps auditability.

## Decision 3: Sector normalization (25+ string variations → 10 categories)

**Problem:** Sector tags are inconsistent (`FinTech`, `payments`, `lending`, `enterprise software`, etc.).  
**Decision:** Map common substrings to canonical categories (e.g., `payments` → `Fintech`). Unknowns → `Other`.  
**Reason:** Stable categories improve filter UX and reduce feature sparsity for ML.

## Decision 4: City normalization (variant spellings)

**Problem:** Same city can appear as variants (`Bengaluru` vs `Bangalore`, `Gurugram` vs `Gurgaon`).  
**Decision:** Normalize a small set of high-frequency variants to canonical names.  
**Reason:** Prevents split counts and improves filter consistency.

## Decision 5: Missing value strategy (why "Unknown" not dropped)

**Problem:** Many articles omit city/investors/round.  
**Decision:** Fill missing with explicit values (`Unknown`, `Undisclosed`) instead of dropping rows.  
**Reason:** Dropping rows biases the dataset and removes potentially valuable leads; explicit missing categories keep the record usable.

## Decision 6: Deduplication (why we use startup+date not URL alone)

**Problem:** URLs can differ due to tracking parameters or republishing, but represent the same announcement.  
**Decision:** Deduplicate on `(startup_name, date_published)` in the cleaner.  
**Reason:** Keeps one record per announcement while still allowing raw JSON to preserve variations in MongoDB.

## Decision 7: Feature engineering (days_since_funding derivation)

**Problem:** Recency is crucial for lead intent.  
**Decision:** Add `days_since_funding` computed as \(today - date\). If parsing fails → `999`.  
**Reason:** Recency directly influences both ML and dashboard ranking.

## Decision 8: Bootstrap label generation (why rule-based labels for ML training)

**Problem:** No human-labeled lead outcomes exist initially.  
**Decision:** Generate initial `High/Medium/Low` labels from domain rules, then train a model on those labels.  
**Reason:** Provides a practical starting point; model can be improved later with real feedback.

## Summary Table

| Step | Records Affected | Action Taken |
|------|------------------|-------------|
| Funding parsing | Funding strings | Convert to `funding_amount_usd_mn` (USD Mn) |
| Date parsing | Date strings | Parse multiple formats; set `date_was_estimated` on failure |
| Sector normalization | Sector strings | Map variations to canonical categories |
| City normalization | City strings | Normalize common spelling variants |
| Missing values | Null/empty fields | Fill with `Unknown` / `Undisclosed` |
| Deduplication | Duplicates | Drop duplicates on `(startup_name, date_published)` |
| Feature engineering | All rows | Add `days_since_funding`, `scraped_at`, placeholders |
| Bootstrap labels | Training data | Rule-based `High/Medium/Low` for initial ML model |

