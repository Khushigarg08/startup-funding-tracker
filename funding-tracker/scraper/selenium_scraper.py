"""
What this file does: uses Selenium headless Chrome to scrape the same funding pages when requests+BS4 gets blocked

How I built this: I copied the same parsing logic from the BS4 scraper, but instead of requests I load the page in
headless Chrome and wait for <article> to show up (JS takes time to render).

Things I learned while writing this:
- JS-rendered pages look empty in requests, but fine in a real browser
- webdriver-manager saves you from the Chrome/driver version mismatch headache
- always quit the driver in finally, otherwise it leaves zombie chrome processes
"""

from __future__ import annotations

import json
import logging
import os
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.python import ChromeDriverManager

# i reuse the exact same parsing so fallback doesn't change the schema randomly
from scraper.yourstory_scraper import parse_records_from_html, setup_logging


def build_driver() -> webdriver.Chrome:
    """Create and return configured headless Chrome driver."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def scrape_and_save() -> None:
    """Scrape YourStory funding pages using Selenium and save JSON."""
    setup_logging()
    start = time.time()

    base_url = "https://yourstory.com/search/funding"
    template = "https://yourstory.com/search/funding?page={page}"

    records: List[Dict[str, Any]] = []
    pages_attempted = 0
    pages_successful = 0
    pages_failed = 0

    driver = None
    try:
        driver = build_driver()
        for page in range(1, 6):
            pages_attempted += 1
            url = template.format(page=page)
            try:
                driver.get(url)
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "article")))
                time.sleep(2)
                html = driver.page_source
                page_records = parse_records_from_html(html, source="selenium-yourstory", base_url=base_url)
                records.extend(page_records)
                pages_successful += 1
            except Exception:
                pages_failed += 1
                logging.error("Error scraping %s\n%s", url, traceback.format_exc())
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                logging.warning("driver.quit() failed (ignored)")

    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "raw_funding.json"
    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    elapsed = round(time.time() - start, 2)
    logging.info("=== SELENIUM SCRAPE SUMMARY ===")
    logging.info("Pages attempted: %s", pages_attempted)
    logging.info("Pages successful: %s", pages_successful)
    logging.info("Pages failed: %s", pages_failed)
    logging.info("Total records scraped: %s", len(records))
    logging.info("Source used: selenium-yourstory")
    logging.info("Output path: %s", str(out_path))
    logging.info("Time taken: %ss", elapsed)


if __name__ == "__main__":
    if os.path.basename(os.getcwd()) != "funding-tracker" and Path("funding-tracker").exists():
        os.chdir("funding-tracker")
    scrape_and_save()
