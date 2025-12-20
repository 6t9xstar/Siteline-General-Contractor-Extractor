from __future__ import annotations

import argparse
import asyncio
import csv
from collections import OrderedDict
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from extractors.config import ScraperConfig
from extractors.http import AsyncHTTPClient
from extractors.parsing import (
    SitelineContractor,
    extract_siteline_contractor_links,
    parse_siteline_detail_html,
)
from extractors.utils import read_seed_file

LISTING_MARKERS = ("/general-contractor/state/", "/general-contractor?page=")


def partition_seed_urls(urls: Iterable[str]) -> tuple[list[str], list[str]]:
    listings: list[str] = []
    details: list[str] = []
    for url in urls:
        lowered = url.lower()
        if any(marker in lowered for marker in LISTING_MARKERS):
            listings.append(url)
        else:
            details.append(url)
    return listings, details


async def crawl_listing_pages(
    client: AsyncHTTPClient,
    listing_urls: list[str],
    concurrency: int,
) -> OrderedDict[str, str]:
    semaphore = asyncio.Semaphore(concurrency)
    discovered: OrderedDict[str, str] = OrderedDict()

    async def _fetch(url: str) -> None:
        async with semaphore:
            try:
                html = await client.get_text(url)
            except Exception as exc:
                print(f"[listing] ERROR {url}: {exc}")
                return
        links = extract_siteline_contractor_links(html)
        for link in links:
            if link not in discovered:
                discovered[link] = url
        print(f"[listing] {url} -> {len(links)} contractors (total {len(discovered)})")

    await asyncio.gather(*(_fetch(url) for url in listing_urls))
    return discovered


async def crawl_detail_pages(
    client: AsyncHTTPClient,
    detail_sources: OrderedDict[str, str],
    concurrency: int,
) -> list[tuple[str, SitelineContractor, str]]:
    semaphore = asyncio.Semaphore(concurrency)
    results: list[tuple[str, SitelineContractor, str]] = []

    async def _fetch(url: str, source: str) -> None:
        async with semaphore:
            try:
                html = await client.get_text(url)
            except Exception as exc:
                print(f"[detail] ERROR {url}: {exc}")
                return
        contractor = parse_siteline_detail_html(html, url=url)
        results.append((url, contractor, source))
        print(f"[detail] scraped {url}")

    await asyncio.gather(*(_fetch(url, src) for url, src in detail_sources.items()))
    return results


def write_csv(rows: list[dict[str, str | float | int | None]], output_path: Path) -> None:
    columns = [
        "contractor_name",
        "siteline_url",
        "website_url",
        "address",
        "phone",
        "source_state_page",
        "last_seen",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def make_row(url: str, contractor: SitelineContractor, source: str) -> dict[str, str | None]:
    row = {
        "siteline_url": url,
        "source_state_page": source,
        "last_seen": asyncio.get_running_loop().time(),
    }
    row.update(asdict(contractor))
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Siteline contractor extractor (Plan 1)")
    parser.add_argument("--input", type=Path, default=Path("siteline.txt"))
    parser.add_argument("--output", type=Path, default=Path("Plan 1/output.csv"))
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument(
        "--mode",
        choices=["listing-only", "detail-only", "full"],
        default="full",
    )
    return parser.parse_args()


async def run_async(args: argparse.Namespace) -> None:
    config = ScraperConfig(concurrency=args.concurrency, timeout=args.timeout)
    client = AsyncHTTPClient(config)
    try:
        seeds = read_seed_file(args.input)
        listing_seeds, detail_seeds = partition_seed_urls(seeds)
        detail_sources: OrderedDict[str, str] = OrderedDict((url, "manual") for url in detail_seeds)

        if args.mode in ("listing-only", "full") and listing_seeds:
            discovered = await crawl_listing_pages(client, listing_seeds, args.concurrency)
            for url, source in discovered.items():
                detail_sources.setdefault(url, source)
            if args.mode == "listing-only":
                print(f"[done] discovered {len(detail_sources)} contractor URLs")
                return

        if args.mode in ("detail-only", "full") and detail_sources:
            scraped = await crawl_detail_pages(client, detail_sources, args.concurrency)
            rows = [make_row(url, contractor, source) for url, contractor, source in scraped]
            write_csv(rows, args.output)
            print(f"[done] wrote {len(rows)} rows to {args.output}")
        else:
            print("[done] nothing to scrape")
    finally:
        await client.close()


def main() -> None:
    args = parse_args()
    asyncio.run(run_async(args))


if __name__ == "__main__":
    main()
