import httpx

from app.service.rss import RSSClient

RSS = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel><title>Example</title><link>https://example.com</link>
    <item><title>Episode one</title><guid>ep-1</guid>
      <pubDate>Sun, 07 Sep 2025 10:00:00 GMT</pubDate>
      <itunes:duration>01:02:03</itunes:duration>
      <enclosure url="https://example.com/audio.mp3" type="audio/mpeg" />
      <podcast:transcript url="https://example.com/transcript.vtt" type="text/vtt" />
    </item>
  </channel>
</rss>"""


def test_parses_episode_and_conditional_headers() -> None:
    seen_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, content=RSS, headers={"etag": '"abc"'})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = RSSClient("test", client).fetch("https://example.com/feed", etag='"old"')

    assert seen_headers["if-none-match"] == '"old"'
    assert result.title == "Example"
    assert result.etag == '"abc"'
    assert result.episodes[0].duration_seconds == 3723
    assert result.episodes[0].audio_url == "https://example.com/audio.mp3"
    assert result.episodes[0].transcript_links[0]["url"] == "https://example.com/transcript.vtt"


def test_handles_not_modified() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(304)))
    result = RSSClient("test", client).fetch("https://example.com/feed", etag='"abc"')
    assert result.not_modified
    assert result.episodes == []
