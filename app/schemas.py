from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    title: str
    url: str
    source: str | None
    published_at: datetime


class PodcastOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    date: date
    title: str
    script: str
    audio_url: str | None
    status: str
    created_at: datetime


class GenerateRequest(BaseModel):
    tickers: list[str]
    limit: int | None = None
