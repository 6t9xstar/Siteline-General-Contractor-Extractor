# Siteline General Contractor Extractor

## Goal
Extract every general-contractor detail page from siteline.com, then capture each contractor's public website URL when available.

## Inputs
- `siteline.txt`: master list of Siteline listing pages (state or pagination URLs).
- Optional: resume checkpoint file to avoid re-processing previously scraped pages.

## High-Level Flow
1. **Seed queue** with URLs from `siteline.txt`.
2. **Listing crawler**
   - Fetch each listing page.
   - Parse contractor detail links (pattern `/general-contractor/contractor/{slug}`).
   - Enqueue unseen detail links, and discover pagination links for deeper crawling.
3. **Detail crawler**
   - Visit each contractor detail page.
   - Extract fields: company name, address, phone, Siteline profile URL, and website link (if present).
4. **Website resolver**
   - Normalize extracted website URLs (ensure scheme, strip tracking params).
   - If a website is missing, mark for manual follow-up.
5. **Exporter**
   - Write structured results (CSV/JSONL) with deduplicated contractors.

## Key Design Decisions
- **Lightweight + fast:** use asynchronous HTTP client (e.g., `httpx` or `aiohttp`) with bounded concurrency.
- **Robust parsing:** use `selectolax`/`BeautifulSoup` for HTML; fall back to regex if DOM changes.
- **Persistence:** maintain a simple SQLite/JSON state file to avoid duplicate requests and support restarts.
- **Rate limiting:** configurable delay + retry/backoff for non-200 responses.

## Data Schema (CSV Columns)
| Column | Description |
| --- | --- |
| `contractor_name` | Display name on Siteline |
| `siteline_url` | Contractor detail page |
| `website_url` | External site (if provided) |
| `address` | Mailing/office address |
| `phone` | Contact number |
| `source_state_page` | Listing page where contractor was discovered |
| `last_seen` | Timestamp of extraction |

## Next Steps
1. Implement crawler skeleton (URL queue, HTTP client, persistence layer).
2. Build parsers for listing + detail pages with unit tests using saved HTML fixtures.
3. Add CLI entry point (e.g., `python plan1_scraper.py --input siteline.txt --out data/plan1.csv`).
