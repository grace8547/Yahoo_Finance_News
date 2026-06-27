from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler

from app.config import settings
from app.database import init_db, session_scope
from app.pipeline import DailyPodcastPipeline


def run_job() -> None:
    init_db()
    with session_scope() as db:
        DailyPodcastPipeline().run(db, settings.default_tickers, settings.news_limit)


def main() -> None:
    scheduler = BlockingScheduler(timezone="America/Los_Angeles")
    scheduler.add_job(run_job, "interval", hours=24, id="daily_stock_podcast", replace_existing=True)
    run_job()
    scheduler.start()


if __name__ == "__main__":
    main()
