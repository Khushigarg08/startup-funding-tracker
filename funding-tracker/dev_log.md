# Dev Log — Startup Funding Tracker

## Why I built this
wanted to solve a real problem - sales teams waste hours 
manually searching for funded startups to pitch to.
thought this could be automated completely.

## Day 1 — Scraper
- first tried requests on yourstory, got 403 immediately
- googled around, found out about user-agent rotation
- added fake_useragent library, started working sometimes
- still getting blocked on some pages so added Inc42 as backup
- pagination was confusing at first, turns out its just ?page=N

## Day 2 — Cleaning
- funding amounts were a nightmare, saw formats like:
  "$2 Mn", "Rs 40 Cr", "USD 1.2 Billion", "Undisclosed"
- wrote parse_funding_amount() to handle all cases
- decided to convert everything to USD millions so its comparable
- used 1 Cr = 0.12M USD (checked current rate, hardcoded for now)
- dates were also messy, tried 9 different formats before giving up
  and just using today's date as fallback

## Day 3 — Database decision
- almost just used PostgreSQL for everything
- then realized raw scraped JSON has inconsistent fields
  (some articles have investor names, some dont, some have 
  extra fields I didnt expect)
- MongoDB made sense for the raw stuff, PostgreSQL for clean data
- this is apparently called a "lambda architecture" or just 
  dual database pattern, pretty common in real pipelines

## Day 4 — ML scoring
- no labeled data was the main problem
- solution: generate labels using business rules first,
  train model on those labels
- its not perfect but its better than hardcoded rules because
  the model can pick up patterns I didnt think of
- chose Random Forest over XGBoost because dataset is small
  (~200 records from scraping), RF doesnt overfit as badly

## Day 5 — API and Frontend  
- express was straightforward, used it before in my goodreads project
- pagination in SQL = LIMIT + OFFSET, took me a minute to remember
- recharts was new to me, docs are actually pretty good
- CSV export without any library was fun to figure out
  (just build the string manually and trigger a download)

## Mistakes I made
- forgot to add CORS middleware, frontend couldn't talk to backend
- was string-concatenating SQL queries at first (SQL injection risk!)
  switched to parameterized queries after remembering from DBMS course
- selenium_scraper.py kept failing because ChromeDriver version 
  didn't match Chrome version, webdriver-manager fixes this automatically

## What I'd improve with more time
- add email alerts when high priority leads are found
- get real labeled data by letting users mark leads as good/bad
  then retrain the model on that (active learning)
- switch to Scrapy if scraping more than 5 sites
- add authentication to the API

