from __future__ import annotations

import asyncio
import re
from typing import Final
from urllib.parse import parse_qs, urlparse

from .common import JsonDict, ToolDef, err, listify_strings, now_ms, ok, parse_int, validate_fetch_url

PLUGIN_ID: Final = "mythosaur.transcript"
PLUGIN_SOURCE: Final = "transcript"
_YOUTUBE_HOSTS: Final = frozenset(
    {
        "youtu.be",
        "www.youtu.be",
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
    }
)
_VIDEO_ID_PATTERN: Final = re.compile(r"^[A-Za-z0-9_-]{11}$")
_DEFAULT_LANGUAGES: Final = ("en",)


class UnsupportedTranscriptUrl(ValueError):
    """Raised when a URL is valid but unsupported by this transcript plugin."""


class EmptyTranscriptError(ValueError):
    """Raised when transcript retrieval succeeds but returns no readable text."""


def _youtube_transcript_api():
    from youtube_transcript_api import YouTubeTranscriptApi

    return YouTubeTranscriptApi()


def _youtube_error_classes() -> dict[str, type[BaseException]]:
    from youtube_transcript_api._errors import (
        CouldNotRetrieveTranscript,
        InvalidVideoId,
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
        VideoUnplayable,
    )

    return {
        "CouldNotRetrieveTranscript": CouldNotRetrieveTranscript,
        "InvalidVideoId": InvalidVideoId,
        "NoTranscriptFound": NoTranscriptFound,
        "TranscriptsDisabled": TranscriptsDisabled,
        "VideoUnavailable": VideoUnavailable,
        "VideoUnplayable": VideoUnplayable,
    }


def _canonical_youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _extract_youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in _YOUTUBE_HOSTS:
        return None

    candidate = ""
    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/").split("/", 1)[0]
    elif parsed.path == "/watch":
        candidate = parse_qs(parsed.query).get("v", [""])[0]
    else:
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"embed", "live", "shorts", "v"}:
            candidate = parts[1]

    candidate = candidate.strip()
    return candidate if _VIDEO_ID_PATTERN.match(candidate) else None


def _clean_transcript_segments(raw_segments: list[dict[str, object]]) -> str:
    chunks: list[str] = []
    for segment in raw_segments:
        text = re.sub(r"\s+", " ", str(segment.get("text") or "")).strip()
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def _clip_text(text: str, *, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    clipped = text[:max_chars].rstrip()
    last_space = clipped.rfind(" ")
    if last_space >= max_chars // 2:
        clipped = clipped[:last_space].rstrip()
    return clipped, True


def _first_available_transcript(transcript_list):
    return next(iter(transcript_list), None)


def _transcript_is_translatable(transcript) -> bool:
    checker = getattr(transcript, "is_translatable", None)
    return bool(checker()) if callable(checker) else bool(checker)


def _select_transcript(api, video_id: str, languages: tuple[str, ...]):
    errors = _youtube_error_classes()
    no_transcript_found = errors["NoTranscriptFound"]
    transcript_list = api.list(video_id)

    for finder_name in (
        "find_manually_created_transcript",
        "find_generated_transcript",
        "find_transcript",
    ):
        finder = getattr(transcript_list, finder_name, None)
        if not callable(finder):
            continue
        try:
            return finder(languages)
        except no_transcript_found:
            continue

    transcript = _first_available_transcript(transcript_list)
    if transcript is None:
        raise no_transcript_found(video_id, languages, transcript_list)

    preferred = languages[0] if languages else ""
    if preferred and _transcript_is_translatable(transcript):
        try:
            return transcript.translate(preferred)
        except Exception:
            pass
    return transcript


def _fetch_transcript_payload_sync(
    *,
    url: str,
    languages: tuple[str, ...],
    preserve_formatting: bool,
    max_chars: int,
) -> dict[str, object]:
    video_id = _extract_youtube_video_id(url)
    if not video_id:
        raise UnsupportedTranscriptUrl("only YouTube video URLs are supported right now")

    api = _youtube_transcript_api()
    transcript = _select_transcript(api, video_id, languages)
    fetched = transcript.fetch(preserve_formatting=preserve_formatting)
    raw_segments = fetched.to_raw_data()
    text = _clean_transcript_segments(raw_segments)
    if not text:
        raise EmptyTranscriptError("transcript was empty")

    clipped_text, truncated = _clip_text(text, max_chars=max_chars)
    return {
        "source_type": "video_transcript",
        "title": "",
        "canonical_url": _canonical_youtube_url(video_id),
        "text": clipped_text,
        "truncated": truncated,
        "metadata": {
            "provider": "youtube",
            "video_id": video_id,
            "language": fetched.language,
            "language_code": fetched.language_code,
            "is_generated": fetched.is_generated,
            "requested_languages": list(languages),
            "preserve_formatting": preserve_formatting,
            "segment_count": len(raw_segments),
            "text_length": len(clipped_text),
            "word_count": len(clipped_text.split()),
        },
    }


async def _extract_transcript(arguments: JsonDict) -> JsonDict:
    started = now_ms()
    url = str(arguments.get("url") or "").strip()
    if not url:
        return err("extract_transcript", "missing_url", "url is required", PLUGIN_SOURCE, started)
    try:
        validate_fetch_url(url)
    except ValueError as exc:
        return err("extract_transcript", "blocked_url", str(exc), PLUGIN_SOURCE, started)

    try:
        errors = _youtube_error_classes()
    except ImportError as exc:
        return err("extract_transcript", "missing_dependency", str(exc), PLUGIN_SOURCE, started)

    languages = tuple(listify_strings(arguments.get("languages")) or list(_DEFAULT_LANGUAGES))
    preserve_formatting = bool(arguments.get("preserve_formatting", False))
    max_chars = parse_int(arguments.get("max_chars"), default=12_000, minimum=500, maximum=50_000)

    try:
        payload = await asyncio.to_thread(
            _fetch_transcript_payload_sync,
            url=url,
            languages=languages,
            preserve_formatting=preserve_formatting,
            max_chars=max_chars,
        )
    except UnsupportedTranscriptUrl as exc:
        return err("extract_transcript", "unsupported_url", str(exc), PLUGIN_SOURCE, started)
    except EmptyTranscriptError as exc:
        return err("extract_transcript", "empty_transcript", str(exc), PLUGIN_SOURCE, started)
    except errors["InvalidVideoId"] as exc:
        return err("extract_transcript", "invalid_video_id", str(exc), PLUGIN_SOURCE, started)
    except (errors["VideoUnavailable"], errors["VideoUnplayable"]) as exc:
        return err("extract_transcript", "video_unavailable", str(exc), PLUGIN_SOURCE, started)
    except (errors["NoTranscriptFound"], errors["TranscriptsDisabled"]) as exc:
        return err("extract_transcript", "transcript_unavailable", str(exc), PLUGIN_SOURCE, started)
    except errors["CouldNotRetrieveTranscript"] as exc:
        return err("extract_transcript", "transcript_retrieval_failed", str(exc), PLUGIN_SOURCE, started)
    except Exception as exc:
        return err("extract_transcript", "transcript_retrieval_failed", str(exc), PLUGIN_SOURCE, started)

    return ok("extract_transcript", payload, PLUGIN_SOURCE, started)


def get_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="extract_transcript",
            plugin_id=PLUGIN_ID,
            description="Extract a normalized transcript from a supported video URL (currently YouTube).",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "url": {"type": "string"},
                    "languages": {"type": "array", "items": {"type": "string"}},
                    "preserve_formatting": {"type": "boolean", "default": False},
                    "max_chars": {"type": "integer", "minimum": 500, "maximum": 50_000},
                },
                "required": ["url"],
            },
            handler=_extract_transcript,
            aliases=["osaurus.extract_transcript"],
            is_async=True,
        )
    ]
