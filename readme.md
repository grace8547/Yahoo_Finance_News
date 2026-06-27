# AI Stock News Podcast Generator

Daily pipeline that collects stock-related news, stores and deduplicates articles, summarizes them with an LLM, generates an audio briefing, and serves podcasts through an API/UI.

## MVP Goal

Build a small, reliable daily system that:

1. Pulls stock news for a set of tickers or a sector/industry bucket.
2. Stores raw articles and deduplicates them.
3. Summarizes the news into a short briefing script.
4. Converts the script into audio.
5. Serves the result through a simple API.

## Suggested Stack

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- APScheduler or Celery
- Ollama for local script generation
- TTS service for audio
- Local filesystem or S3/GCS for mp3 storage

## MVP Scope

### In scope

- Daily news ingestion
- Article deduplication
- LLM-generated summary
- Podcast script generation
- TTS audio generation
- API to list and fetch podcasts

### Out of scope for MVP

- Fine-tuning
- Social login
- Advanced recommendation system
- Multi-user personalization
- Full notebook-style editorial workflow

## Core API

- `GET /podcasts`
- `GET /podcasts/{id}`
- `GET /podcasts/{id}/audio`
- `GET /tickers/{ticker}/podcasts/latest`

## Run the MVP

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the API and UI:

```bash
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`, enter tickers such as `AAPL,NVDA,MU`, and click
Generate. The app stores articles in `stock_news.db` and audio files in `audio/`.

Run the daily scheduler:

```bash
python -m app.scheduler
```

## Run with Docker and Ollama

This setup runs FastAPI and Ollama as separate services. Ollama model files live
in the `ollama-models` Docker volume, so rebuilding the app image does not
redownload the model.

Start Ollama first:

```bash
docker compose up -d ollama
```

Pull the default local LLM once:

```bash
docker compose --profile setup run --rm ollama-pull
```

Build and start the API/UI:

```bash
docker compose up --build app
```

Open `http://127.0.0.1:8000`.

To use a different Ollama model:

```bash
OLLAMA_MODEL=llama3.1:8b docker compose --profile setup run --rm ollama-pull
OLLAMA_MODEL=llama3.1:8b docker compose up --build app
```

Useful checks:

```bash
docker compose ps
docker compose exec ollama ollama list
docker compose logs -f app
```

The app container talks to Ollama at `http://ollama:11434`, which is the Docker
Compose service name. From your host machine, Ollama is also available at
`http://127.0.0.1:11434`.

## Configuration

- `DATABASE_URL`: defaults to `sqlite:///./stock_news.db`; set this to a
  PostgreSQL SQLAlchemy URL for production.
- `DEFAULT_TICKERS`: comma-separated tickers for scheduled runs.
- `NEWS_LIMIT`: maximum recent articles per ticker.
- `OLLAMA_ENABLED`: defaults to `false` for fast local testing; set to `true`
  to use Ollama script generation.
- `OLLAMA_BASE_URL`: defaults to `http://127.0.0.1:11434`.
- `OLLAMA_MODEL`: defaults to `qwen3:8b`.
- `OLLAMA_TIMEOUT_SECONDS`: defaults to `45`.
- `OPENAI_API_KEY`: optional; only used if you later choose OpenAI TTS.
- `OPENAI_TTS_MODEL`: optional OpenAI TTS model, defaults to `gpt-4o-mini-tts`.
- `OPENAI_TTS_VOICE`: optional OpenAI TTS voice, defaults to `alloy`.

With `OLLAMA_ENABLED=false`, or without a running Ollama server, the app still runs with extractive summaries.
Without `OPENAI_API_KEY`, the app writes a placeholder MP3 plus a transcript next
to the audio file. This keeps the MVP demoable locally without paid API tokens.

## Implementation Notes

- Yahoo Finance RSS ingestion is self-contained in `app/ingestion.py`.
- Deduplication uses a SHA-256 hash of canonical URL plus title.
- The database schema includes stocks, articles, summaries, and podcasts.
- Source links are exposed through `GET /podcasts/{id}/sources`.
- NotebookLM is best treated as an optional/manual comparison unless the
  NotebookLM Enterprise preview API is available for the deployment target.
