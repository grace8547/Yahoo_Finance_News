from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./stock_news.db")
    audio_dir: Path = Path(os.getenv("AUDIO_DIR", "audio"))
    default_tickers: list[str] = None  # type: ignore[assignment]
    news_limit: int = int(os.getenv("NEWS_LIMIT", "12"))
    ollama_enabled: bool = os.getenv("OLLAMA_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    ollama_timeout_seconds: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "45"))
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_tts_model: str = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    openai_tts_voice: str = os.getenv("OPENAI_TTS_VOICE", "alloy")
    piper_model_path: Path = Path(os.getenv("PIPER_MODEL_PATH", "/app/voices/en_US-lessac-medium.onnx"))

    def __post_init__(self) -> None:
        if self.default_tickers is None:
            tickers = os.getenv("DEFAULT_TICKERS", "AAPL,NVDA,MU")
            object.__setattr__(self, "default_tickers", [t.strip().upper() for t in tickers.split(",") if t.strip()])


settings = Settings()
