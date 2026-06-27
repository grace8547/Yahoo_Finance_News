from __future__ import annotations

import json
import re

import requests

from app.config import settings
from app.models import Article


class Briefing:
    def __init__(self, bullets: list[str], script: str) -> None:
        self.bullets = bullets
        self.script = script


class BriefingGenerator:
    def generate(self, ticker: str, articles: list[Article]) -> Briefing:
        if settings.ollama_enabled:
            try:
                return self._generate_with_ollama(ticker, articles)
            except Exception:
                pass
        return self._generate_extractive(ticker, articles)

    def _generate_with_ollama(self, ticker: str, articles: list[Article]) -> Briefing:
        source_packet = [
            {
                "title": article.title,
                "source": article.source,
                "published_at": article.published_at.isoformat(),
                "url": article.url,
                "text": clean_for_summary(article.raw_text or article.title)[:800],
            }
            for article in rank_articles(articles)[:5]
        ]
        prompt = (
            "Create a grounded stock-news audio briefing. Use only the supplied sources. "
            "Return JSON with keys bullets and script. bullets must contain exactly 5 concise bullets. "
            "script should be a clear two-minute podcast script that cites source names naturally and avoids investment advice.\n\n"
            f"Ticker: {ticker}\nSources:\n{json.dumps(source_packet, ensure_ascii=True)}"
        )
        response = requests.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.2, "num_ctx": 2048, "num_predict": 450},
            },
            timeout=settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        data = json.loads(response.json().get("response") or "{}")
        bullets = [str(item) for item in data.get("bullets", [])][:5]
        script = str(data.get("script", "")).strip()
        if not bullets or not script:
            raise ValueError("Ollama response did not include bullets and script")
        return Briefing(bullets=bullets, script=script)

    def _generate_extractive(self, ticker: str, articles: list[Article]) -> Briefing:
        ranked = rank_articles(articles)[:5]
        bullets = [summarize_article(article) for article in ranked]
        script_lines = [
            f"Welcome to today's {ticker.upper()} stock news briefing.",
            "This automated episode is grounded in the source articles collected by the pipeline.",
        ]
        for idx, article in enumerate(ranked, start=1):
            source = article.source or "Yahoo Finance"
            script_lines.append(f"Story {idx}, from {source}: {summarize_article(article)}")
        script_lines.append(
            "That is the latest source-grounded briefing. Review the linked articles before making any investing decision."
        )
        return Briefing(bullets=bullets, script="\n\n".join(script_lines))


def rank_articles(articles: list[Article]) -> list[Article]:
    return sorted(
        articles,
        key=lambda article: (
            len(article.raw_text or ""),
            article.published_at,
        ),
        reverse=True,
    )


def summarize_article(article: Article) -> str:
    text = clean_for_summary(article.raw_text or article.title)
    first_sentence = re.split(r"(?<=[.!?])\s+", text)[0]
    if len(first_sentence) < 40 and article.title:
        first_sentence = article.title
    return first_sentence[:260].rstrip()


def clean_for_summary(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text or "No article text was available."
