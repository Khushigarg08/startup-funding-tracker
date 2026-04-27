"""
What this file does: runs the whole pipeline (scrape → clean → score → load) every 24 hours automatically

How I built this: I used APScheduler BlockingScheduler because it's simple and works fine for one job.
Each step runs as a subprocess so failures are isolated, and if the main scraper fails I try Selenium.

Things I learned while writing this:
- subprocess output is super useful but can be noisy, so I log only the tail
- automation is basically "rerun the scripts on a schedule" but make it resilient
- having a selenium fallback makes the pipeline way less fragile
"""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime
from typing import List, Tuple

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger


def setup_logging() -> None:
    """Configure scheduler logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _tail(s: str, n: int = 500) -> str:
    """Return last n characters of a string."""
    if not s:
        return ""
    return s[-n:]


def run_full_pipeline() -> None:
    """Run all pipeline steps sequentially with Selenium retry on scraper failure."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info("=== PIPELINE STARTED: %s ===", ts)

    steps: List[Tuple[str, str]] = [
        ("Scraper (BeautifulSoup)", "scraper/yourstory_scraper.py"),
        ("Cleaner", "scraper/cleaner.py"),
        ("ML Scorer", "scraper/ml_scorer.py"),
        ("Loader (PostgreSQL + MongoDB)", "scraper/loader.py"),
    ]

    for step_name, script_path in steps:
        logging.info("Starting: %s", step_name)
        result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
        if result.returncode == 0:
            logging.info("✓ %s complete", step_name)
            if result.stdout:
                logging.info(_tail(result.stdout, 500))
        else:
            logging.error("✗ %s FAILED", step_name)
            if result.stderr:
                logging.error(_tail(result.stderr, 500))

            if "Scraper" in step_name:
                logging.info("Attempting Selenium fallback...")
                subprocess.run([sys.executable, "scraper/selenium_scraper.py"])

    ts2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info("=== PIPELINE COMPLETE: %s ===", ts2)
    logging.info("Next run in 24 hours.")


def main() -> None:
    """Initialize scheduler, run immediately, then start interval loop."""
    setup_logging()
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        run_full_pipeline,
        trigger=IntervalTrigger(hours=24),
        id="pipeline",
        replace_existing=True,
    )

    logging.info("Scheduler initialized. Running pipeline immediately...")
    run_full_pipeline()

    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
        logging.info("Scheduler stopped by user.")


if __name__ == "__main__":
    main()
