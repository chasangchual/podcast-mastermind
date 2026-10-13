import sys
import types
from pathlib import Path

from app.config.app_config import AppConfig
from app.model.entities import TranscriptSource
from app.service.transcription import LocalTranscriber


class FakeWhisperModel:
    instances: list["FakeWhisperModel"] = []

    def __init__(self, model: str, **kwargs):
        self.model = model
        self.kwargs = kwargs
        FakeWhisperModel.instances.append(self)

    def transcribe(self, path: str, **kwargs):
        segments = [
            types.SimpleNamespace(text=" Hello there. ", start=0.0, end=1.5),
            types.SimpleNamespace(text="  ", start=1.5, end=2.0),
            types.SimpleNamespace(text="General Kenobi.", start=2.0, end=3.0),
        ]
        return iter(segments), types.SimpleNamespace(language="en")


def test_faster_whisper_backend(monkeypatch) -> None:
    monkeypatch.setitem(
        sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeWhisperModel)
    )
    FakeWhisperModel.instances.clear()
    transcriber = LocalTranscriber(AppConfig(_env_file=None, whisper_model="small"))

    result = transcriber.transcribe(Path("episode.mp3"))
    transcriber.transcribe(Path("episode.mp3"))

    assert result.source == TranscriptSource.local_whisper
    assert result.language == "en"
    assert result.text == "Hello there.\n\nGeneral Kenobi."
    assert result.segments[1] == {
        "text": "General Kenobi.",
        "start": 2.0,
        "end": 3.0,
        "speaker": None,
    }
    assert len(FakeWhisperModel.instances) == 1
    assert FakeWhisperModel.instances[0].kwargs == {
        "device": "cpu",
        "compute_type": "int8",
        "cpu_threads": 0,
    }
