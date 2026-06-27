from __future__ import annotations

from pathlib import Path
from threading import Lock

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, init_db
from app.models import Article, Podcast
from app.pipeline import DailyPodcastPipeline, recent_articles
from app.schemas import ArticleOut, GenerateRequest, PodcastOut
from app.tts import AudioGenerator, wav_duration_seconds


app = FastAPI(title="AI Stock News Podcast Generator")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
generate_job_lock = Lock()


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    settings.audio_dir.mkdir(parents=True, exist_ok=True)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    index_path = Path("app/static/index.html")
    return index_path.read_text(encoding="utf-8")


@app.post("/jobs/daily", response_model=list[PodcastOut])
def run_daily_job(payload: GenerateRequest, db: Session = Depends(get_db)) -> list[Podcast]:
    if not generate_job_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A podcast generation job is already running")
    try:
        pipeline = DailyPodcastPipeline()
        podcasts = pipeline.run(db, payload.tickers, payload.limit)
        if not podcasts:
            raise HTTPException(status_code=404, detail="No recent articles found for the requested tickers")
        db.commit()
        return podcasts
    finally:
        generate_job_lock.release()


@app.get("/podcasts", response_model=list[PodcastOut])
def list_podcasts(ticker: str | None = None, db: Session = Depends(get_db)) -> list[Podcast]:
    stmt = select(Podcast).order_by(Podcast.created_at.desc()).limit(50)
    if ticker:
        stmt = select(Podcast).where(Podcast.ticker == ticker.upper()).order_by(Podcast.created_at.desc()).limit(50)
    return list(db.scalars(stmt))


@app.get("/podcasts/{podcast_id}", response_model=PodcastOut)
def get_podcast(podcast_id: int, db: Session = Depends(get_db)) -> Podcast:
    podcast = db.get(Podcast, podcast_id)
    if not podcast:
        raise HTTPException(status_code=404, detail="Podcast not found")
    return podcast


@app.delete("/podcasts/{podcast_id}")
def delete_podcast(podcast_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    podcast = db.get(Podcast, podcast_id)
    if not podcast:
        raise HTTPException(status_code=404, detail="Podcast not found")

    delete_audio_files(podcast)
    db.delete(podcast)
    db.commit()
    return {"status": "deleted"}


@app.get("/podcasts/{podcast_id}/sources", response_model=list[ArticleOut])
def get_podcast_sources(podcast_id: int, db: Session = Depends(get_db)) -> list[Article]:
    podcast = db.get(Podcast, podcast_id)
    if not podcast:
        raise HTTPException(status_code=404, detail="Podcast not found")
    return recent_articles(db, podcast.ticker, settings.news_limit)


@app.get("/podcasts/{podcast_id}/audio")
def get_audio(podcast_id: int, db: Session = Depends(get_db)) -> FileResponse:
    podcast = db.get(Podcast, podcast_id)
    if not podcast:
        raise HTTPException(status_code=404, detail="Podcast not found")

    audio_path = playable_audio_path(podcast)
    media_type = "audio/mpeg" if audio_path.suffix == ".mp3" else "audio/wav"
    return FileResponse(audio_path, media_type=media_type)


def playable_audio_path(podcast: Podcast) -> Path:
    base_name = f"podcast_{podcast.id}_{podcast.ticker.lower()}"
    wav_path = settings.audio_dir / f"{base_name}.wav"
    mp3_path = settings.audio_dir / f"{base_name}.mp3"

    if wav_path.exists() and wav_duration_seconds(wav_path) > 3.5:
        return wav_path
    if mp3_path.exists() and mp3_path.stat().st_size > 1_000:
        return mp3_path
    return AudioGenerator().generate(podcast.id, podcast.ticker, podcast.script)


def delete_audio_files(podcast: Podcast) -> None:
    base_name = f"podcast_{podcast.id}_{podcast.ticker.lower()}"
    for suffix in (".wav", ".mp3", ".txt"):
        path = settings.audio_dir / f"{base_name}{suffix}"
        if path.exists():
            path.unlink()


@app.get("/tickers/{ticker}/podcasts/latest", response_model=PodcastOut)
def latest_for_ticker(ticker: str, db: Session = Depends(get_db)) -> Podcast:
    stmt = select(Podcast).where(Podcast.ticker == ticker.upper()).order_by(Podcast.created_at.desc()).limit(1)
    podcast = db.scalar(stmt)
    if not podcast:
        raise HTTPException(status_code=404, detail="No podcast found for ticker")
    return podcast
