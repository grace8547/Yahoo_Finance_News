FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends espeak-ng \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/voices \
    && python -c "from urllib.request import urlretrieve; base='https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/'; urlretrieve(base + 'en_US-lessac-medium.onnx', '/app/voices/en_US-lessac-medium.onnx'); urlretrieve(base + 'en_US-lessac-medium.onnx.json', '/app/voices/en_US-lessac-medium.onnx.json')"

COPY app ./app

RUN mkdir -p /data /app/audio

ENV DATABASE_URL=sqlite:////data/stock_news.db
ENV AUDIO_DIR=/app/audio
ENV OLLAMA_ENABLED=false
ENV OLLAMA_BASE_URL=http://ollama:11434
ENV OLLAMA_MODEL=qwen3:8b
ENV OLLAMA_TIMEOUT_SECONDS=45
ENV PIPER_MODEL_PATH=/app/voices/en_US-lessac-medium.onnx

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
