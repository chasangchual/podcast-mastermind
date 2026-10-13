import html
import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config.app_config import AppConfig
from app.model.entities import TranscriptSource


@dataclass(frozen=True)
class TranscriptCandidate:
    text: str
    source: TranscriptSource
    url: str | None = None
    language: str | None = None
    segments: list[dict[str, Any]] = field(default_factory=list)


PUBLISHER_SELECTORS: dict[str, tuple[str, ...]] = {
    "npr.org": (".transcript.storytext", "#transcript", "[data-testid='transcript']"),
    "freakonomics.com": (".episode-transcript", ".transcript", "article"),
    "macrovoices.com": (".transcript", ".itemFullText", "article"),
    "fool.com": (".article-content", ".transcript", "article"),
    "theinvestorspodcast.com": (".transcript", ".episode-transcript", "article"),
    "joincolossus.com": (".transcript", "[data-transcript]", "article"),
}


class TranscriptResolver:
    def __init__(self, config: AppConfig, client: httpx.Client | None = None):
        self.config = config
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": config.http_user_agent},
        )

    def resolve_public(
        self, transcript_links: list[dict[str, Any]], episode_url: str | None
    ) -> TranscriptCandidate | None:
        for link in transcript_links:
            try:
                candidate = self._fetch_podcasting20(link)
            except (httpx.HTTPError, ValueError, json.JSONDecodeError):
                candidate = None
            if candidate and self._complete(candidate.text):
                return candidate
        if episode_url:
            try:
                candidate = self._fetch_publisher(episode_url)
            except (httpx.HTTPError, ValueError, json.JSONDecodeError):
                candidate = None
            if candidate and self._complete(candidate.text):
                return candidate
        return None

    def _fetch_podcasting20(self, link: dict[str, Any]) -> TranscriptCandidate | None:
        url = link.get("url") or link.get("href")
        if not url:
            return None
        response = self.client.get(url)
        response.raise_for_status()
        content_type = (link.get("type") or response.headers.get("content-type", "")).lower()
        language = link.get("language")
        if "json" in content_type or url.endswith(".json"):
            payload = response.json()
            segments = payload.get("segments", payload) if isinstance(payload, dict) else payload
            if not isinstance(segments, list):
                return None
            normalized = []
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                text = str(segment.get("body") or segment.get("text") or "").strip()
                if text:
                    normalized.append(
                        {
                            "text": text,
                            "start": segment.get("startTime", segment.get("start")),
                            "end": segment.get("endTime", segment.get("end")),
                            "speaker": segment.get("speaker"),
                        }
                    )
            return TranscriptCandidate(
                text="\n\n".join(item["text"] for item in normalized),
                source=TranscriptSource.podcasting20,
                url=url,
                language=language,
                segments=normalized,
            )
        if "vtt" in content_type or url.endswith(".vtt") or url.endswith(".srt"):
            text = self._strip_captions(response.text)
        elif "html" in content_type:
            text = BeautifulSoup(response.text, "html.parser").get_text("\n", strip=True)
        else:
            text = response.text.strip()
        return TranscriptCandidate(
            text=text,
            source=TranscriptSource.podcasting20,
            url=url,
            language=language,
        )

    def _fetch_publisher(self, url: str) -> TranscriptCandidate | None:
        host = urlparse(url).hostname or ""
        selector_group = next(
            (
                selectors
                for domain, selectors in PUBLISHER_SELECTORS.items()
                if host.endswith(domain)
            ),
            None,
        )
        if selector_group is None:
            return None
        response = self.client.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for selector in selector_group:
            element = soup.select_one(selector)
            if element:
                text = element.get_text("\n", strip=True)
                if self._complete(text):
                    return TranscriptCandidate(
                        text=text, source=TranscriptSource.publisher, url=str(response.url)
                    )
        for script in soup.select("script[type='application/ld+json']"):
            try:
                payload = json.loads(script.string or "")
            except json.JSONDecodeError:
                continue
            records = payload if isinstance(payload, list) else [payload]
            for record in records:
                if not isinstance(record, dict):
                    continue
                value = record.get("transcript") or record.get("articleBody")
                if isinstance(value, str) and self._complete(value):
                    return TranscriptCandidate(
                        text=html.unescape(value),
                        source=TranscriptSource.publisher,
                        url=str(response.url),
                    )
        return None

    def _complete(self, text: str) -> bool:
        return len(re.findall(r"\b\w+\b", text)) >= self.config.transcript_min_words

    @staticmethod
    def _strip_captions(raw: str) -> str:
        lines = []
        previous = None
        for line in raw.splitlines():
            line = line.strip()
            if not line or line == "WEBVTT" or "-->" in line or line.isdigit():
                continue
            clean = BeautifulSoup(line, "html.parser").get_text(" ", strip=True)
            if clean and clean != previous:
                lines.append(clean)
                previous = clean
        return "\n".join(lines)
