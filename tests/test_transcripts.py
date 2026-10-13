import httpx

from app.config.app_config import AppConfig
from app.model.entities import TranscriptSource
from app.service.transcripts import TranscriptResolver


def config() -> AppConfig:
    return AppConfig(_env_file=None, transcript_min_words=3)


def test_podcasting20_is_preferred_over_publisher() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("transcript.txt"):
            return httpx.Response(200, text="This is the complete public transcript.")
        raise AssertionError("Publisher page should not be fetched")

    resolver = TranscriptResolver(
        config(), httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    )
    result = resolver.resolve_public(
        [{"url": "https://cdn.example/transcript.txt", "type": "text/plain"}],
        "https://www.npr.org/episode",
    )

    assert result is not None
    assert result.source == TranscriptSource.podcasting20


def test_partial_transcript_is_rejected() -> None:
    resolver = TranscriptResolver(
        AppConfig(_env_file=None, transcript_min_words=10),
        httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, text="Too short"))
        ),
    )
    assert resolver.resolve_public(
        [{"url": "https://example.com/transcript.txt", "type": "text/plain"}], None
    ) is None

