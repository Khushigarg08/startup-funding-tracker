"""
What this file does: scrapes funding pages from YourStory (and Inc42 if YourStory blocks) and saves them as raw JSON

How I built this: I started with plain requests + BeautifulSoup, but YourStory kept throwing 403/429 randomly.
Then I added rotating user agents + random delays, and also kept Inc42 as a backup so the pipeline still has data.

Things I learned while writing this:
- sites really do block you just based on headers / request patterns
- fixed sleep is kinda obvious, random delay behaves more like a human
- BeautifulSoup can return None everywhere, so you have to be super defensive
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent


def setup_logging() -> None:
    """Configure root logger format and level."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _rotate_headers(ua: UserAgent) -> Dict[str, str]:
    """Create request headers with rotating User-Agent."""
    return {
        "User-Agent": ua.random,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "close",
    }


def _normalize_startup_name(text: str) -> str:
    """Clean common suffixes from startup names."""
    if not text:
        return "Unknown"
    cleaned = re.sub(r"\s*\|\s*YourStory\s*$", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*-\s*Funding\s*$", "", cleaned.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "Unknown"


def extract_startup_name(card: BeautifulSoup, page_soup: BeautifulSoup) -> str:
    """Extract startup name from a card using multiple fallbacks."""
    for tag_name in ("h2", "h3"):
        t = card.find(tag_name)
        if t and t.get_text(strip=True):
            return _normalize_startup_name(t.get_text(strip=True))

    if page_soup.title and page_soup.title.get_text(strip=True):
        return _normalize_startup_name(page_soup.title.get_text(strip=True))
    return "Unknown"


def extract_funding_amount(card_text: str) -> str:
    """Extract funding amount string using regex."""
    pattern = r"(US\$|INR|₹|\$|Rs\.?)[\s]*([\d,.]+)\s*(Mn|Bn|Cr|Lakh|million|billion|crore)?"
    m = re.search(pattern, card_text, flags=re.IGNORECASE)
    if not m:
        return "Undisclosed"
    currency = m.group(1)
    amount = m.group(2)
    unit = m.group(3) or ""
    raw = f"{currency} {amount} {unit}".strip()
    raw = re.sub(r"\s+", " ", raw)
    return raw


def extract_funding_round(card_text: str) -> str:
    """Extract funding round from known keywords."""
    rounds = [
        "Pre-Seed",
        "Seed",
        "Pre-Series A",
        "Series A",
        "Series B",
        "Series C",
        "Series D",
        "Series E",
        "Bridge",
        "Angel",
        "Venture",
        "Growth",
    ]
    for r in rounds:
        if re.search(rf"\\b{re.escape(r)}\\b", card_text, flags=re.IGNORECASE):
            return r
    return "Undisclosed"


def extract_sector(card: BeautifulSoup, article_url: str) -> str:
    """Extract sector from tag/category elements or URL slug."""
    # Look for elements with class containing tag/category/label/badge
    candidates: List[str] = []
    for el in card.find_all(True):
        classes = " ".join(el.get("class", [])).lower()
        if any(k in classes for k in ("tag", "category", "label", "badge")):
            txt = el.get_text(" ", strip=True)
            if txt and 2 <= len(txt) <= 50:
                candidates.append(txt)
    if candidates:
        return candidates[0]

    # Extract from URL slug (very rough heuristic)
    slug = article_url.lower()
    words = re.split(r"[^a-z0-9]+", slug)
    known = {
        "fintech",
        "saas",
        "healthtech",
        "edtech",
        "ecommerce",
        "logistics",
        "mobility",
        "ai",
        "ml",
        "consumer",
        "banking",
        "insurance",
        "payments",
        "retail",
        "gaming",
        "crypto",
        "blockchain",
        "agritech",
        "foodtech",
        "travel",
        "realestate",
        "proptech",
        "climate",
        "cleantech",
        "energy",
    }
    for w in words:
        if w in known:
            return w.upper() if w in {"ai", "ml"} else w.title()
    return "Unknown"


def extract_investor_names(card_text: str) -> str:
    """Extract investor names by trigger phrases and sentence slicing."""
    triggers = [
        "led by",
        "backed by",
        "participated by",
        "investors include",
        "investment from",
    ]
    lower = card_text.lower()
    for trig in triggers:
        idx = lower.find(trig)
        if idx == -1:
            continue
        start = idx + len(trig)
        tail = card_text[start:]
        # Stop at sentence boundary.
        stop_match = re.search(r"(\\.|\\n)", tail)
        chunk = tail[: stop_match.start()] if stop_match else tail
        chunk = chunk.strip(" :-–—\t")
        if not chunk:
            continue
        chunk = re.sub(r"\s+", " ", chunk)
        # Split on ',' and 'and'
        parts = re.split(r",|\\band\\b", chunk, flags=re.IGNORECASE)
        cleaned = [p.strip() for p in parts if p.strip()]
        if cleaned:
            return ", ".join(cleaned)
    return "Unknown"


def extract_city(card_text: str) -> str:
    """Extract city from known list."""
    cities = [
        "Mumbai",
        "Delhi",
        "Bangalore",
        "Bengaluru",
        "Hyderabad",
        "Chennai",
        "Pune",
        "Kolkata",
        "Ahmedabad",
        "Jaipur",
        "Noida",
        "Gurugram",
        "Gurgaon",
        "Surat",
        "Indore",
        "Chandigarh",
        "Kochi",
        "Lucknow",
    ]
    for c in cities:
        if re.search(rf"\\b{re.escape(c)}\\b", card_text, flags=re.IGNORECASE):
            return c
    return "Unknown"


def extract_date_published(page_soup: BeautifulSoup, card: BeautifulSoup) -> str:
    """Extract date published from time/meta/text patterns."""
    # dates are all over the place depending on page/template, so trying a few options
    t = card.find("time")
    if t and t.get("datetime"):
        return str(t.get("datetime")).strip()

    t2 = page_soup.find("time")
    if t2 and t2.get("datetime"):
        return str(t2.get("datetime")).strip()

    meta = page_soup.find("meta", attrs={"property": "article:published_time"})
    if meta and meta.get("content"):
        return str(meta.get("content")).strip()

    # if structured tags aren't there, last resort: just regex the visible text
    text = card.get_text(" ", strip=True)
    patterns = [
        r"\\b[A-Z][a-z]{2}\\s+\\d{1,2},\\s+\\d{4}\\b",  # Jan 15, 2024
        r"\\b\\d{1,2}\\s+[A-Z][a-z]+\\s+\\d{4}\\b",  # 15 January 2024
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(0)
    return datetime.now().strftime("%Y-%m-%d")


def extract_article_url(card: BeautifulSoup, base_url: str) -> str:
    """Extract and normalize article URL from anchor tag."""
    a = card.find("a", href=True)
    if not a:
        return base_url
    href = str(a.get("href")).strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return f"https://yourstory.com{href}"
    return f"https://yourstory.com/{href.lstrip('/')}"


def _cards_from_soup(soup: BeautifulSoup) -> List[BeautifulSoup]:
    """Return list of article-like cards from a page soup."""
    cards = soup.find_all("article")
    if cards:
        return list(cards)
    # sometimes the page doesn't use <article>, so try some generic "card-ish" divs
    cards = soup.find_all(["div", "section"], class_=re.compile(r"(card|story|article|result)", re.I))
    return list(cards)


def parse_records_from_html(html: str, source: str, base_url: str) -> List[Dict[str, Any]]:
    """Parse records from an HTML page."""
    soup = BeautifulSoup(html, "lxml")
    cards = _cards_from_soup(soup)
    records: List[Dict[str, Any]] = []
    for card in cards:
        card_text = card.get_text(" ", strip=True)
        article_url = extract_article_url(card, base_url=base_url)
        startup_name = extract_startup_name(card, soup)
        rec = {
            "startup_name": startup_name or "Unknown",
            "funding_amount": extract_funding_amount(card_text),
            "funding_round": extract_funding_round(card_text),
            "sector": extract_sector(card, article_url),
            "investor_names": extract_investor_names(card_text),
            "city": extract_city(card_text),
            "date_published": extract_date_published(soup, card),
            "article_url": article_url,
            "source": source,
        }
        # Ensure all required keys present
        for k, fallback in (
            ("startup_name", "Unknown"),
            ("funding_amount", "Undisclosed"),
            ("funding_round", "Undisclosed"),
            ("sector", "Unknown"),
            ("investor_names", "Unknown"),
            ("city", "Unknown"),
            ("date_published", datetime.now().strftime("%Y-%m-%d")),
            ("article_url", base_url),
            ("source", source),
        ):
            if k not in rec or rec[k] in (None, ""):
                rec[k] = fallback
        records.append(rec)
    return records


def fetch_page(session: requests.Session, url: str, headers: Dict[str, str]) -> Tuple[int, str]:
    """Fetch a URL and return (status_code, text)."""
    resp = session.get(url, headers=headers, timeout=10)
    return resp.status_code, resp.text


def scrape_source(base_url: str, page_param_template: str, source: str) -> Tuple[List[Dict[str, Any]], bool, Dict[str, int]]:
    """Scrape pages 1-5 from a source; return (records, needs_selenium, stats)."""
    ua = UserAgent()
    session = requests.Session()
    needs_selenium = False
    stats = {"attempted": 0, "successful": 0, "failed": 0, "blocked": 0}
    records: List[Dict[str, Any]] = []

    for page_num in range(1, 6):
        stats["attempted"] += 1
        page_url = page_param_template.format(page=page_num)
        try:
            headers = _rotate_headers(ua)
            status, html = fetch_page(session, page_url, headers=headers)
            if status == 200:
                stats["successful"] += 1
                records.extend(parse_records_from_html(html, source=source, base_url=base_url))
            elif status in (403, 429):
                stats["blocked"] += 1
                logging.warning("Blocked by server — use Selenium fallback")
                needs_selenium = True
                break
            else:
                stats["failed"] += 1
                logging.warning("Non-200 status %s for %s", status, page_url)
        except Exception:
            stats["failed"] += 1
            logging.error("Error scraping %s\n%s", page_url, traceback.format_exc())
        finally:
            time.sleep(random.uniform(2, 4))

    return records, needs_selenium, stats


def scrape_and_save() -> None:
    """Run scrape (YourStory primary, Inc42 fallback) and save raw JSON."""
    setup_logging()
    start = time.time()

    yourstory_base = "https://yourstory.com/search/funding"
    yourstory_template = "https://yourstory.com/search/funding?page={page}"
    inc42_base = "https://inc42.com/tag/funding/"
    inc42_template = "https://inc42.com/tag/funding/page/{page}/"

    pages_attempted = 0
    pages_successful = 0
    pages_failed = 0
    used_source = "yourstory"

    records, needs_selenium, stats = scrape_source(
        base_url=yourstory_base, page_param_template=yourstory_template, source="yourstory"
    )
    pages_attempted += stats["attempted"]
    pages_successful += stats["successful"]
    pages_failed += stats["failed"] + stats["blocked"]

    if needs_selenium or len(records) < 5:
        used_source = "inc42"
        logging.info("Switched to Inc42 as fallback source")
        inc_records, _, inc_stats = scrape_source(
            base_url=inc42_base, page_param_template=inc42_template, source="inc42"
        )
        pages_attempted += inc_stats["attempted"]
        pages_successful += inc_stats["successful"]
        pages_failed += inc_stats["failed"] + inc_stats["blocked"]
        records = inc_records

    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "raw_funding.json"
    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    elapsed = round(time.time() - start, 2)
    logging.info("=== SCRAPE SUMMARY ===")
    logging.info("Pages attempted: %s", pages_attempted)
    logging.info("Pages successful: %s", pages_successful)
    logging.info("Pages failed: %s", pages_failed)
    logging.info("Total records scraped: %s", len(records))
    logging.info("Source used: %s", used_source)
    logging.info("Output path: %s", str(out_path))
    logging.info("Time taken: %ss", elapsed)


if __name__ == "__main__":
    # i kept running this from different folders and paths broke, so forcing cwd
    if os.path.basename(os.getcwd()) != "funding-tracker" and Path("funding-tracker").exists():
        os.chdir("funding-tracker")
    scrape_and_save()
