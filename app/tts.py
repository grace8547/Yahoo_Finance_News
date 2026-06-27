from __future__ import annotations

import math
from pathlib import Path
import shutil
import subprocess
import wave

from app.config import settings


class AudioGenerator:
    def generate(self, podcast_id: int, ticker: str, script: str) -> Path:
        settings.audio_dir.mkdir(parents=True, exist_ok=True)
        mp3_path = settings.audio_dir / f"podcast_{podcast_id}_{ticker.lower()}.mp3"
        if settings.openai_api_key:
            try:
                return self._generate_openai(script, mp3_path)
            except Exception:
                pass
        wav_path = settings.audio_dir / f"podcast_{podcast_id}_{ticker.lower()}.wav"
        if settings.piper_model_path.exists() and shutil.which("piper"):
            return self._generate_piper(script, wav_path)
        if shutil.which("espeak-ng"):
            return self._generate_espeak(script, wav_path)
        return self._generate_placeholder(script, wav_path)

    def _generate_openai(self, script: str, output_path: Path) -> Path:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        with client.audio.speech.with_streaming_response.create(
            model=settings.openai_tts_model,
            voice=settings.openai_tts_voice,
            input=script,
        ) as response:
            response.stream_to_file(output_path)
        return output_path

    def _generate_placeholder(self, script: str, output_path: Path) -> Path:
        write_beep_wav(output_path)
        transcript_path = output_path.with_suffix(".txt")
        transcript_path.write_text(script, encoding="utf-8")
        return output_path

    def _generate_espeak(self, script: str, output_path: Path) -> Path:
        transcript_path = output_path.with_suffix(".txt")
        transcript_path.write_text(script, encoding="utf-8")
        subprocess.run(
            ["espeak-ng", "-w", str(output_path), "-s", "155", "-v", "en-us", script],
            check=True,
            timeout=120,
        )
        return output_path

    def _generate_piper(self, script: str, output_path: Path) -> Path:
        transcript_path = output_path.with_suffix(".txt")
        transcript_path.write_text(script, encoding="utf-8")
        subprocess.run(
            [
                "piper",
                "--model",
                str(settings.piper_model_path),
                "--output_file",
                str(output_path),
            ],
            input=script,
            text=True,
            check=True,
            timeout=180,
        )
        return output_path


def wav_duration_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            return frames / float(rate)
    except Exception:
        return 0.0


def write_beep_wav(output_path: Path, duration_seconds: float = 2.0) -> None:
    sample_rate = 16_000
    frequency_hz = 440
    amplitude = 8_000
    total_samples = int(sample_rate * duration_seconds)

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = bytearray()
        for index in range(total_samples):
            sample = int(amplitude * math.sin(2 * math.pi * frequency_hz * index / sample_rate))
            frames.extend(sample.to_bytes(2, byteorder="little", signed=True))
        wav_file.writeframes(bytes(frames))
