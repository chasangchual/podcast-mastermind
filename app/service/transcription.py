from pathlib import Path
from typing import Any

from app.config.app_config import AppConfig
from app.model.entities import TranscriptSource
from app.service.transcripts import TranscriptCandidate


class LocalTranscriber:
    def __init__(self, config: AppConfig):
        self.config = config
        self._model: Any = None

    def transcribe(self, audio_path: Path) -> TranscriptCandidate:
        if self.config.transcription_backend == "mlx":
            text, segments, language = self._transcribe_mlx(audio_path)
        else:
            segments, language = self._transcribe_faster_whisper(audio_path)
            text = "\n\n".join(segment["text"] for segment in segments)
        if not text:
            raise RuntimeError("Whisper returned an empty transcript")
        return TranscriptCandidate(
            text=text,
            source=TranscriptSource.local_whisper,
            language=language,
            segments=segments,
        )

    def _faster_whisper_model(self) -> Any:
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError(
                    "Local transcription requires: uv sync --extra transcription"
                ) from exc
            self._model = WhisperModel(
                self.config.whisper_model,
                device=self.config.whisper_device,
                compute_type=self.config.whisper_compute_type,
                cpu_threads=self.config.whisper_cpu_threads,
            )
        return self._model

    def _transcribe_faster_whisper(
        self, audio_path: Path
    ) -> tuple[list[dict[str, Any]], str | None]:
        raw_segments, info = self._faster_whisper_model().transcribe(
            str(audio_path), beam_size=self.config.whisper_beam_size, vad_filter=True
        )
        segments = [
            {
                "text": segment.text.strip(),
                "start": segment.start,
                "end": segment.end,
                "speaker": None,
            }
            for segment in raw_segments
            if segment.text.strip()
        ]
        return segments, info.language

    def _transcribe_mlx(
        self, audio_path: Path
    ) -> tuple[str, list[dict[str, Any]], str | None]:
        try:
            import mlx_whisper
        except ImportError as exc:
            raise RuntimeError("MLX transcription requires: uv sync --extra mlx") from exc
        result: dict[str, Any] = mlx_whisper.transcribe(
            str(audio_path), path_or_hf_repo=self.config.whisper_model
        )
        segments = [
            {
                "text": segment.get("text", "").strip(),
                "start": segment.get("start"),
                "end": segment.get("end"),
                "speaker": None,
            }
            for segment in result.get("segments", [])
            if segment.get("text", "").strip()
        ]
        text = result.get("text", "").strip() or "\n\n".join(s["text"] for s in segments)
        return text, segments, result.get("language")
