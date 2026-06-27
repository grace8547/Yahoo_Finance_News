from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(150), nullable=True)

    articles: Mapped[list["Article"]] = relationship(back_populates="stock")


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_articles_content_hash"),
        Index("ix_articles_ticker_published_at", "ticker", "published_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int | None] = mapped_column(ForeignKey("stocks.id"), nullable=True)
    ticker: Mapped[str] = mapped_column(String(12), index=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    stock: Mapped[Stock | None] = relationship(back_populates="articles")
    summary: Mapped["Summary | None"] = relationship(back_populates="article")


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), unique=True, index=True)
    summary_text: Mapped[str] = mapped_column(Text)
    sentiment: Mapped[str] = mapped_column(String(30), default="neutral")
    importance_score: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    article: Mapped[Article] = relationship(back_populates="summary")


class Podcast(Base):
    __tablename__ = "podcasts"
    __table_args__ = (Index("ix_podcasts_ticker_date", "ticker", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(12), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(255))
    script: Mapped[str] = mapped_column(Text)
    audio_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
