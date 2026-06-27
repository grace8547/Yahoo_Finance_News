# Architecture

## Pipeline

```text
Scheduler
  -> News ingestion
  -> Deduplication
  -> Database storage
  -> LLM summarization
  -> Podcast script generation
  -> TTS audio generation
  -> Audio storage
  -> API/UI
```

## Components

### 1. Scheduler

Runs the pipeline every 24 hours.

Possible tools:
- APScheduler for a simple MVP
- Celery beat if the pipeline grows

### 2. Ingestion

Fetches Yahoo Finance news, RSS, or another news source.

Responsibilities:
- fetch articles
- normalize fields
- compute content hash
- store raw article data

### 3. Storage

Use PostgreSQL for structured records.

Store:
- stocks
- articles
- summaries
- podcasts

### 4. LLM Summarization

Use OpenAI API for inference only at this stage.

Output:
- short bullet summary
- 1 to 2 minute podcast script
- optional source-aware notes

### 5. TTS

Convert the final script into audio.

Options:
- OpenAI TTS
- ElevenLabs
- Google TTS

### 6. API

FastAPI serves podcast metadata and audio.

### 7. UI

A small frontend can show:
- latest episode
- source articles
- ticker filters
- audio player

## Data Flow

1. Scheduler triggers ingestion.
2. Ingestion fetches and stores articles.
3. Deduper filters duplicates.
4. Summarizer writes briefing text.
5. TTS generates MP3.
6. API exposes the podcast.

