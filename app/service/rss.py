import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx
from dateutil import parser as date_parser


@dataclass(frozen=True)
class FeedEpisode:
    guid: str
    title: str
    description: str | None
    published_at: datetime
    duration_seconds: int | None
    episode_url: str | None
    audio_url: str | None
    audio_content_type: str | None
    participants: list[str] = field(default_factory=list)
    transcript_links: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeedResult:
    title: str | None
    website_url: str | None
    etag: str | None
    last_modified: str | None
    not_modified: bool
    episodes: list[FeedEpisode]


class RSSClient:
    def __init__(self, user_agent: str, client: httpx.Client | None = None):
        self.client = client or httpx.Client(
            follow_redirects=True, timeout=30, headers={"User-Agent": user_agent}
        )

    def fetch(self, url: str, etag: str | None = None, modified: str | None = None) -> FeedResult:
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if modified:
            headers["If-Modified-Since"] = modified
        response = self.client.get(url, headers=headers)
        if response.status_code == 304:
            return FeedResult(None, None, etag, modified, True, [])
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            raise RuntimeError(f"Invalid RSS feed: {parsed.bozo_exception}")
        episodes = [self._episode(entry) for entry in parsed.entries]
        return FeedResult(
            title=parsed.feed.get("title"),
            website_url=parsed.feed.get("link"),
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
            not_modified=False,
            episodes=episodes,
        )

    def _episode(self, entry: Any) -> FeedEpisode:
        title = str(entry.get("title") or "Untitled episode").strip()
        episode_url = entry.get("link")
        published_raw = entry.get("published") or entry.get("updated")
        published_at = (
            date_parser.parse(published_raw).astimezone(UTC)
            if published_raw
            else datetime.now(UTC)
        )
        audio_url = None
        audio_content_type = None
        for enclosure in entry.get("enclosures", []):
            content_type = enclosure.get("type", "")
            if content_type.startswith("audio/") or not audio_url:
                audio_url = enclosure.get("href") or enclosure.get("url")
                audio_content_type = content_type or None
                if content_type.startswith("audio/"):
                    break
        guid = str(entry.get("id") or "").strip()
        if not guid:
            basis = "|".join([episode_url or "", audio_url or "", title, published_at.isoformat()])
            guid = f"derived:{hashlib.sha256(basis.encode()).hexdigest()}"
        participants = []
        for author in entry.get("authors", []):
            name = author.get("name")
            if name and name not in participants:
                participants.append(name)
        author = entry.get("author")
        if author and author not in participants:
            participants.append(author)
        return FeedEpisode(
            guid=guid,
            title=title,
            description=entry.get("summary") or entry.get("description"),
            published_at=published_at,
            duration_seconds=self._duration(entry.get("itunes_duration")),
            episode_url=episode_url,
            audio_url=audio_url,
            audio_content_type=audio_content_type,
            participants=participants,
            transcript_links=self._transcript_links(entry),
            metadata={
                "tags": [
                    tag.get("term") for tag in entry.get("tags", []) if tag.get("term")
                ]
            },
        )

    @staticmethod
    def _duration(raw: Any) -> int | None:
        if raw is None:
            return None
        if isinstance(raw, int):
            return raw
        value = str(raw).strip()
        if value.isdigit():
            return int(value)
        try:
            parts = [int(part) for part in value.split(":")]
        except ValueError:
            return None
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        return None

    @staticmethod
    def _transcript_links(entry: Any) -> list[dict[str, Any]]:
        candidates = entry.get("podcast_transcript") or entry.get("podcast_transcripts") or []
        if isinstance(candidates, dict):
            candidates = [candidates]
        links = []
        for candidate in candidates if isinstance(candidates, list) else []:
            if isinstance(candidate, dict):
                links.append(dict(candidate))
        for link in entry.get("links", []):
            rel = str(link.get("rel", "")).lower()
            content_type = str(link.get("type", "")).lower()
            if "transcript" in rel or any(kind in content_type for kind in ("vtt", "srt")):
                links.append(dict(link))
        return links
