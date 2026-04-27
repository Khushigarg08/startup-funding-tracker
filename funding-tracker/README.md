# 🚀 Indian Startup Funding Intelligence Tool
> Automatically tracks newly funded Indian startups as B2B leads

## 🌐 Live Demo
- **Dashboard:** https://funding-tracker-frontend.onrender.com
- **API:** https://funding-tracker-backend.onrender.com/api/health

## 📌 Problem Statement

Businesses (SaaS companies, agencies, recruiters) need to identify newly funded Indian startups as high-intent leads. This tool automatically scrapes, cleans, stores, scores, and serves Indian startup funding announcements from YourStory and Inc42 in a searchable React dashboard.

## 👤 Who Uses This (3 B2B personas)

- SaaS founder looking for high-budget early customers
- Recruiter targeting fast-growing startups
- VC analyst tracking competitor investment activity

## 🏗️ Architecture

```
YourStory/Inc42
     ↓
BeautifulSoup Scraper ──(if blocked)──→ Selenium Fallback
     ↓
Raw JSON → MongoDB (audit trail)
     ↓
Pandas Cleaner
     ↓
Random Forest ML Scorer
     ↓
Cleaned CSV → PostgreSQL (structured queries)
     ↓
Node.js + Express REST API
     ↓
React.js Dashboard
     ↑
APScheduler (every 24h, Asia/Kolkata timezone)
```

## 🛠️ Tech Stack

| Tool | Purpose | Why chosen |
|------|---------|------------|
| Python (requests + BeautifulSoup4) | Primary scraping | Fast to build/maintain for single-domain scraping |
| Selenium (headless Chrome) | Fallback scraping | Handles JS-rendered pages and request blocking (403/429) |
| pandas + numpy | Cleaning + feature engineering | Standard, reliable ETL tooling for tabular pipelines |
| PostgreSQL | Clean structured storage | Strong querying, filtering, pagination, analytics |
| MongoDB | Raw unstructured storage | Schema-flexible audit trail + reprocessing capability |
| scikit-learn Random Forest | Lead scoring | Simple, robust baseline for mixed feature types |
| Node.js + Express | REST API | Lightweight backend for dashboard queries |
| React (CRA) + axios + recharts | Dashboard | Fast UI iteration, simple data fetching, charts |
| APScheduler | Automation | Production-friendly interval scheduling in Python |
| Render | Deployment | Simple multi-service deployment (DB + API + static site) |

## 📁 Project Structure (full tree)

```
funding-tracker/
├── scraper/
│   ├── yourstory_scraper.py
│   ├── selenium_scraper.py
│   ├── cleaner.py
│   ├── loader.py
│   ├── ml_scorer.py
│   ├── scheduler.py
│   └── requirements.txt
├── data/
│   ├── raw/
│   │   └── raw_funding.json
│   ├── cleaned/
│   │   └── cleaned_funding.csv
│   └── model/
│       └── lead_scorer.pkl
├── backend/
│   ├── server.js
│   ├── db.js
│   ├── routes/
│   │   └── startups.js
│   ├── .env.example
│   └── package.json
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── index.js
│   │   ├── App.js
│   │   ├── App.css
│   │   └── components/
│   │       ├── StatsBar.js
│   │       ├── StatsBar.css
│   │       ├── Filters.js
│   │       ├── Filters.css
│   │       ├── StartupTable.js
│   │       ├── StartupTable.css
│   │       ├── Charts.js
│   │       └── Charts.css
│   ├── .env
│   └── package.json
├── cleaning_notes.md
├── render.yaml
└── README.md
```

## ⚙️ Local Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL running locally
- MongoDB running locally (or Atlas URI)
- Google Chrome (for Selenium fallback)

### 1. Clone repository

```bash
git clone https://github.com/Khushigarg08/startup-funding-tracker.git
cd startup-funding-tracker/funding-tracker
```

### 2. Setup Python environment

```bash
cd funding-tracker
python -m venv .venv

# Windows PowerShell
.\\.venv\\Scripts\\Activate.ps1

pip install -r scraper/requirements.txt
```

### 3. Setup PostgreSQL database

Create a database (example uses `funding_db`) and ensure credentials match your `.env`.

```bash
psql -U postgres
CREATE DATABASE funding_db;
\\q
```

### 4. Setup MongoDB

Run MongoDB locally or use MongoDB Atlas. For local:

```bash
mongod
```

### 5. Configure environment variables

Create `backend/.env` from `backend/.env.example` and set values:

```bash
cp backend/.env.example backend/.env
```

Set MongoDB too (used by Python loader):

```bash
# backend/.env (example)
MONGO_URI=mongodb://localhost:27017
```

### 6. Run the pipeline (first time)

From `funding-tracker/`:

```bash
python scraper/yourstory_scraper.py
python scraper/cleaner.py
python scraper/ml_scorer.py
python scraper/loader.py
```

### 7. Start backend API

```bash
cd backend
npm install
npm run dev
```

Backend runs on `http://localhost:8000`.

### 8. Start React frontend

```bash
cd frontend
npm install
npm start
```

Frontend runs on `http://localhost:3000`.

### 9. (Optional) Start scheduler for automation

```bash
cd funding-tracker
python scraper/scheduler.py
```

## 🔌 API Reference

### 1) Health

- Method: `GET`
- URL: `/api/health`

```bash
curl http://localhost:8000/api/health
```

Example response:

```json
{
  "status": "ok",
  "timestamp": "2026-04-25T18:30:00.000Z",
  "db_connected": true
}
```

### 2) Filters

- Method: `GET`
- URL: `/api/filters`

```bash
curl http://localhost:8000/api/filters
```

### 3) Stats

- Method: `GET`
- URL: `/api/stats`

```bash
curl http://localhost:8000/api/stats
```

### 4) Startups list (with filters + pagination)

- Method: `GET`
- URL: `/api/startups`
- Query params:
  - `sector`
  - `funding_round`
  - `city`
  - `min_score`
  - `lead_priority`
  - `page` (default 1)
  - `page_size` (default 20)

```bash
curl "http://localhost:8000/api/startups?sector=Fintech&min_score=5&page=1&page_size=20"
```

### 5) Startup by id

- Method: `GET`
- URL: `/api/startups/:id`

```bash
curl http://localhost:8000/api/startups/<id>
```

## 🤖 ML Lead Scoring

- **Algorithm:** Random Forest classifier (scikit-learn)
- **Why RF over XGBoost (here):** dataset is small (hundreds of scraped records), RF is simpler and robust; XGBoost shines at larger scale.
- **Features used:** `funding_amount_usd_mn`, `days_since_funding`, one-hot `sector`, one-hot `funding_round`
- **Output:**
  - `lead_priority`: High / Medium / Low
  - `lead_score`: 0–10 derived from \(P(\text{High}) \times 10\)
- **Bootstrap label generation:** initial labels are rule-derived to bootstrap training (no human labels yet).
- **Limitation:** labels are not ground truth; best improved via user feedback loop over time.

## 🗄️ Database Design

### PostgreSQL (structured)

Table: `startup_funding`

```sql
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
```

### MongoDB (raw documents)

Database: `funding_tracker`  
Collection: `raw_fundings`

Example document shape:

```json
{
  "startup_name": "Example Startup",
  "funding_amount": "US$ 5 Mn",
  "funding_round": "Seed",
  "sector": "Fintech",
  "investor_names": "Investor A, Investor B",
  "city": "Bangalore",
  "date_published": "2026-04-01",
  "article_url": "https://yourstory.com/...",
  "source": "yourstory",
  "loaded_at": "2026-04-25T18:30:00.000Z"
}
```

## ⚡ Automation

The scheduler runs every **24 hours** using `BlockingScheduler` in **Asia/Kolkata** timezone and executes:

1. `scraper/yourstory_scraper.py`
2. `scraper/cleaner.py`
3. `scraper/ml_scorer.py`
4. `scraper/loader.py`

If the scraper step fails, it retries using `scraper/selenium_scraper.py`.

## 🌐 Deployment (Render)

1. Push the repo to GitHub.
2. In Render, create a new Blueprint and point it to `render.yaml`.
3. Ensure environment variables are set (Render auto-wires Postgres).
4. Configure `MONGO_URI` with MongoDB Atlas connection string (recommended).
5. Deploy; frontend will call backend via `REACT_APP_API_URL`.

## ⚖️ Trade-offs & Limitations

- Rate limiting / blocking from YourStory is possible (handled via random delay + Selenium fallback).
- Currency conversion uses a fixed heuristic rate for INR→USD Mn (documented in `cleaning_notes.md`).
- ML labels are bootstrap rule-derived, not human validated.
- No authentication/authorization on the API (intended as a demo project).

## 🗺️ Future Improvements

- Add email alerts for High priority leads
- CRM integration (Salesforce/HubSpot API)
- Switch to Scrapy for scale if expanding domains and crawl volume
- Active learning loop to improve ML labels with user feedback

