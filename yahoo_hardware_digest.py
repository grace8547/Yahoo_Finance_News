from __future__ import annotations

import argparse
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

try:
    from dateutil import parser as date_parser
except Exception:  # pragma: no cover
    date_parser = None


@dataclass(frozen=True)
class NewsItem:
    ticker: str
    title: str
    summary: str
    url: str
    source: str
    published_at: datetime
    article_text: str = ""


@dataclass(frozen=True)
class NewsBatch:
    items: list[NewsItem]
    archive_path: str = ""


sector_industry_map = {
    11: {
        "sector": "Technology",
        "industry": "Semiconductors",
        "tickers": ["NVDA", "AVGO", "AMD", "INTC", "QCOM", "MU", "TSM", "ASML", "MRVL", "ARM"],
    },
    12: {
        "sector": "Technology",
        "industry": "Computer Hardware",
        "tickers": ["AAPL", "DELL", "HPQ", "SMCI", "WDC", "STX", "LOGI", "NTAP", "ANET", "CSCO"],
    },
    13: {
        "sector": "Technology",
        "industry": "Semiconductor Equipment & Materials",
        "tickers": ["AMAT", "LRCX", "KLAC", "TER", "ONTO", "ACLS", "CAMT", "UCTT", "FORM", "MKSI"],
    },
    14: {
        "sector": "Technology",
        "industry": "Communication Equipment",
        "tickers": ["CSCO", "ANET", "JNPR", "CIEN", "NOK", "ERIC", "MSI", "HPE", "NTGR", "AVGO"],
    },
}


class NewsFetchAgent:
    def __init__(self, tickers: list[str], limit: int = 30, archive_dir: str = "daily_articles"):
        self.tickers = tickers
        self.limit = limit
        self.archive_dir = Path(archive_dir)
        self.session = requests.Session()

    def run(self) -> NewsBatch:
        items: list[NewsItem] = []
        for ticker in self.tickers:
            raw = fetch_yahoo_news_for_ticker(self.session, ticker)
            items.extend(extract_items(ticker, raw, self.session))
            time.sleep(0.5)
        items = summarize_items(items, limit=self.limit)
        archive_path = write_daily_archive(items, self.archive_dir)
        return NewsBatch(items=items, archive_path=str(archive_path))


class NewsSummarizeAgent:
    def run(self, batch: NewsBatch) -> str:
        return build_digest(batch.items, batch.archive_path)


def parse_dt(value: object) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 10_000_000_000:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        if date_parser is not None:
            try:
                dt = date_parser.parse(value)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except Exception:
                pass
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_yahoo_news_for_ticker(session: requests.Session, ticker: str) -> list[dict]:
    url = "https://feeds.finance.yahoo.com/rss/2.0/headline"
    params = {"s": ticker, "region": "US", "lang": "en-US"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml,application/xml,text/xml,*/*",
        "Referer": f"https://finance.yahoo.com/quote/{ticker}/",
    }
    resp = session.get(url, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    items: list[dict] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        source = (item.findtext("source") or "").strip()
        items.append(
            {
                "title": title,
                "link": link,
                "description": description,
                "pubDate": pub_date,
                "source": source,
            }
        )
    return items


def extract_items(ticker: str, raw_items: Iterable[dict], session: Optional[requests.Session] = None) -> list[NewsItem]:
    items: list[NewsItem] = []
    session = session or requests.Session()
    for item in raw_items:
        title = item.get("title") or item.get("headline") or ""
        url = item.get("link") or item.get("url") or ""
        summary = clean_text(item.get("summary") or item.get("description") or item.get("snippet") or "")
        source = clean_text(item.get("source") or "")
        published_at = parse_dt(item.get("pubDate")) or datetime.now(timezone.utc)
        if title and url:
            article_text = fetch_article_text(session, url)
            items.append(
                NewsItem(
                    ticker=ticker,
                    title=title.strip(),
                    summary=summary.strip(),
                    url=url,
                    source=source.strip(),
                    published_at=published_at,
                    article_text=article_text,
                )
            )
    return items


def fetch_article_text(session: requests.Session, url: str) -> str:
    try:
        resp = session.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            },
            timeout=25,
        )
        resp.raise_for_status()
    except Exception:
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")
    article = soup.find("article") or soup.body or soup

    paragraphs = []
    for tag in article.find_all(["p", "h2", "h3"]):
        text = clean_text(tag.get_text(" ", strip=True))
        if text:
            paragraphs.append(text)

    if not paragraphs:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            return clean_text(meta_desc["content"])

    return "\n\n".join(paragraphs[:60]).strip()


def summarize_items(items: list[NewsItem], limit: int = 30) -> list[NewsItem]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    seen: set[str] = set()
    filtered: list[NewsItem] = []
    for item in sorted(items, key=lambda x: x.published_at, reverse=True):
        if item.published_at < cutoff:
            continue
        key = canonical_key(item)
        if key in seen:
            continue
        seen.add(key)
        filtered.append(item)
        if len(filtered) >= limit:
            break
    return filtered


def build_digest(items: list[NewsItem], archive_path: str = "") -> str:
    lines = [
        "# Yahoo Finance Computer Hardware Digest",
        f"_Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
    ]
    if archive_path:
        lines.append(f"Archive: `{archive_path}`")
        lines.append("")
    if not items:
        lines.append("No Yahoo Finance news items were found in the last 24 hours.")
        return "\n".join(lines)
    for idx, item in enumerate(items, start=1):
        ts = item.published_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        source = f" ({item.source})" if item.source else ""
        article_text = item.article_text.strip()
        if article_text:
            paragraph = (
                f"[{item.ticker}] {item.title}. "
                f"{clean_text(item.summary) or 'Full article captured for personal analysis.'} "
                f"Source{source}: {ts}. "
                f"Link: {item.url}"
            )
            lines.append(f"{idx}. {paragraph}")
            lines.append("")
            lines.append("   Full article:")
            lines.append("")
            for block in article_text.split("\n\n"):
                lines.append(f"   {block}")
            lines.append("")
        else:
            summary_text = item.summary or item.title
            paragraph = f"[{item.ticker}] {summary_text}. Source{source}: {ts}. Link: {item.url}"
            lines.append(f"{idx}. {paragraph}")
    return "\n".join(lines)


def canonical_key(item: NewsItem) -> str:
    base = item.url.split("?")[0].rstrip("/").lower()
    title = re.sub(r"\s+", " ", item.title.lower()).strip()
    return f"{base}|{title}"


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:80] or "article"


def write_daily_archive(items: list[NewsItem], archive_dir: Path) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = archive_dir / f"{date_str}_computer_hardware_digest.md"
    existing_keys: set[str] = set()
    if out_path.exists():
        existing_keys = load_existing_archive_keys(out_path)

    lines = [
        "# Yahoo Finance Computer Hardware Archive",
        f"_Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
    ]
    for idx, item in enumerate(items, start=1):
        key = canonical_key(item)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        ts = item.published_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines.extend(
            [
                f"## {idx}. {item.title}",
                f"- Ticker: {item.ticker}",
                f"- Source: {item.source or 'Yahoo Finance'}",
                f"- Time: {ts}",
                f"- URL: {item.url}",
                "",
                item.summary or "",
                "",
                "### Full Article",
                "",
                item.article_text.strip() or "_Full text could not be extracted._",
                "",
                "---",
                "",
            ]
        )
    out_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return out_path


def load_existing_archive_keys(path: Path) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return set()
    keys: set[str] = set()
    for match in re.finditer(r"^##\s+\d+\.\s+(.*)$", text, flags=re.MULTILINE):
        keys.add(match.group(1).strip().lower())
    return keys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pull Yahoo Finance sector news from the last 24 hours."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Maximum number of stories to include.",
    )
    parser.add_argument(
        "--archive-dir",
        default="daily_articles",
        help="Directory to store the per-day Markdown archive.",
    )
    parser.add_argument(
        "--sector-industry",
        type=int,
        required=True,
        help="Sector-industry label, e.g. 12 for Technology / Computer Hardware.",
    )
    args = parser.parse_args()

    if args.sector_industry not in sector_industry_map:
        raise SystemExit(f"Label {args.sector_industry} not found in sector_industry_map")
    entry = sector_industry_map[args.sector_industry]
    sector = entry["sector"]
    industry = entry["industry"]
    tickers = entry["tickers"]
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output_filename = build_output_filename(date_str, sector, industry)
    output_path = Path(args.archive_dir) / output_filename

    fetch_agent = NewsFetchAgent(
        tickers=tickers,
        limit=args.limit,
        archive_dir=args.archive_dir,
    )
    summarize_agent = NewsSummarizeAgent()
    digest = summarize_agent.run(fetch_agent.run())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(digest)
        f.write("\n")
    return 0


def build_output_filename(date_str: str, sector: str, industry: str) -> str:
    def clean(value: str) -> str:
        value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
        value = re.sub(r"\s+", "_", value.strip())
        value = re.sub(r"_+", "_", value)
        return value or "Unknown"
    return f"{date_str}_{clean(sector)}_{clean(industry)}_digest.md"


if __name__ == "__main__":
    raise SystemExit(main())
