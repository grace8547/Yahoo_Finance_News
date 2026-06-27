from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from typing import Iterable, Optional
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Article, Stock

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


def article_hash(item: NewsItem) -> str:
    base = f"{item.url.split('?')[0].rstrip('/').lower()}|{item.title.strip().lower()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


class YahooFinanceIngestor:
    def __init__(self) -> None:
        self.session = requests.Session()

    def fetch(self, tickers: list[str]) -> list[NewsItem]:
        items: list[NewsItem] = []
        for ticker in tickers:
            raw_items = fetch_yahoo_news_for_ticker(self.session, ticker.upper())
            items.extend(extract_items(ticker.upper(), raw_items, self.session))
        return items


def fetch_yahoo_news_for_ticker(session: requests.Session, ticker: str) -> list[dict]:
    url = "https://feeds.finance.yahoo.com/rss/2.0/headline"
    params = {"s": ticker, "region": "US", "lang": "en-US"}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/rss+xml,application/xml,text/xml,*/*",
        "Referer": f"https://finance.yahoo.com/quote/{ticker}/",
    }
    response = session.get(url, params=params, headers=headers, timeout=20)
    response.raise_for_status()
    root = ET.fromstring(response.text)

    items: list[dict] = []
    for item in root.findall(".//item"):
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "description": (item.findtext("description") or "").strip(),
                "pubDate": (item.findtext("pubDate") or "").strip(),
                "source": (item.findtext("source") or "").strip(),
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
            items.append(
                NewsItem(
                    ticker=ticker,
                    title=title.strip(),
                    summary=summary.strip(),
                    url=url,
                    source=source.strip(),
                    published_at=published_at,
                    article_text=fetch_article_text(session, url),
                )
            )
    return items


def fetch_article_text(session: requests.Session, url: str) -> str:
    try:
        response = session.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
            },
            timeout=25,
        )
        response.raise_for_status()
    except Exception:
        return ""

    soup = BeautifulSoup(response.text, "html.parser")
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


def parse_dt(value: object) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000.0
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    if isinstance(value, str):
        if date_parser is not None:
            try:
                parsed = date_parser.parse(value)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
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


def get_or_create_stock(db: Session, ticker: str) -> Stock:
    ticker = ticker.upper()
    stock = db.scalar(select(Stock).where(Stock.ticker == ticker))
    if stock:
        return stock
    stock = Stock(ticker=ticker)
    db.add(stock)
    db.flush()
    return stock


def store_articles(db: Session, items: list[NewsItem]) -> list[Article]:
    stored: list[Article] = []
    for item in items:
        content_hash = article_hash(item)
        existing = db.scalar(select(Article).where(Article.content_hash == content_hash))
        if existing:
            stored.append(existing)
            continue

        stock = get_or_create_stock(db, item.ticker)
        article = Article(
            stock_id=stock.id,
            ticker=item.ticker.upper(),
            title=item.title,
            url=item.url,
            source=item.source or "Yahoo Finance",
            published_at=item.published_at,
            content_hash=content_hash,
            raw_text=item.article_text or item.summary,
        )
        db.add(article)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(select(Article).where(Article.content_hash == content_hash))
            if existing:
                stored.append(existing)
            continue
        stored.append(article)
    return stored
