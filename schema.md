# Schema

## stocks

- `id`
- `ticker`
- `company_name`
- `sector`
- `industry`

## articles

- `id`
- `stock_id`
- `ticker`
- `title`
- `url`
- `source`
- `published_at`
- `content_hash`
- `raw_text`
- `created_at`

## summaries

- `id`
- `article_id`
- `summary_text`
- `sentiment`
- `importance_score`
- `created_at`

## podcasts

- `id`
- `ticker`
- `date`
- `title`
- `script`
- `audio_url`
- `status`
- `created_at`

## Notes

- `content_hash` should be unique or indexed for deduplication.
- `ticker` should be indexed for retrieval.
- `published_at` should be indexed for time-based queries.

