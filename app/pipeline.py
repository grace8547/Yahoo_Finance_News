from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.ingestion import YahooFinanceIngestor, store_articles
from app.llm import BriefingGenerator, rank_articles
from app.models import Article, Podcast, Summary
from app.tts import AudioGenerator


class DailyPodcastPipeline:
    def __init__(self) -> None:
        self.ingestor = YahooFinanceIngestor()
        self.briefing_generator = BriefingGenerator()
        self.audio_generator = AudioGenerator()

    def run(self, db: Session, tickers: list[str] | None = None, limit: int | None = None) -> list[Podcast]:
        tickers = [ticker.upper() for ticker in (tickers or settings.default_tickers)]
        limit = limit or settings.news_limit
        items = self.ingestor.fetch(tickers)
        store_articles(db, items)
        db.flush()

        podcasts: list[Podcast] = []
        for ticker in tickers:
            articles = recent_articles(db, ticker, limit)
            if not articles:
                continue
            briefing = self.briefing_generator.generate(ticker, articles)
            for article, bullet in zip(rank_articles(articles), briefing.bullets):
                upsert_summary(db, article, bullet)

            podcast = Podcast(
                ticker=ticker,
                date=date.today(),
                title=f"{ticker} Daily Stock News Briefing",
                script=briefing.script,
                status="processing_audio",
            )
            db.add(podcast)
            db.flush()
            audio_path = self.audio_generator.generate(podcast.id, ticker, briefing.script)
            podcast.audio_url = f"/podcasts/{podcast.id}/audio"
            podcast.status = "created"
            podcasts.append(podcast)
        return podcasts


def recent_articles(db: Session, ticker: str, limit: int) -> list[Article]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    stmt = (
        select(Article)
        .where(Article.ticker == ticker.upper(), Article.published_at >= cutoff)
        .order_by(Article.published_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def upsert_summary(db: Session, article: Article, summary_text: str) -> Summary:
    summary = db.scalar(select(Summary).where(Summary.article_id == article.id))
    if summary:
        summary.summary_text = summary_text
        return summary
    summary = Summary(article_id=article.id, summary_text=summary_text, sentiment="neutral", importance_score=0.5)
    db.add(summary)
    return summary
