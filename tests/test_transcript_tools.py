import asyncio

import services.mcp_server.plugins.transcript_tools as transcript_tools
from services.mcp_server.plugins.transcript_tools import get_tools


def _tool(name: str):
    for tool in get_tools():
        if tool.name == name:
            return tool
    raise AssertionError(f"tool not found: {name}")


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_extract_transcript_missing_url():
    payload = _run(_tool("extract_transcript").handler({}))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "missing_url"


def test_extract_transcript_rejects_unsupported_url():
    payload = _run(_tool("extract_transcript").handler({"url": "https://example.com/video"}))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "unsupported_url"


def test_extract_transcript_returns_normalized_payload(monkeypatch):
    class _FakeFetchedTranscript:
        language = "English"
        language_code = "en"
        is_generated = False

        def to_raw_data(self):
            return [
                {"text": "Mythosaur now uses a normalized transcript path.", "start": 0.0, "duration": 1.0},
                {"text": "It keeps video summaries local-first and auditable.", "start": 1.0, "duration": 1.0},
            ]

    class _FakeTranscript:
        language_code = "en"

        def fetch(self, preserve_formatting: bool = False):
            assert preserve_formatting is False
            return _FakeFetchedTranscript()

        def is_translatable(self):
            return False

    class _FakeTranscriptList:
        def find_manually_created_transcript(self, languages):
            assert tuple(languages) == ("en",)
            return _FakeTranscript()

        def find_generated_transcript(self, languages):
            raise AssertionError("generated fallback should not run when manual transcript exists")

        def find_transcript(self, languages):
            raise AssertionError("generic fallback should not run when manual transcript exists")

        def __iter__(self):
            yield _FakeTranscript()

    class _FakeApi:
        def list(self, video_id: str):
            assert video_id == "abc123XYZ89"
            return _FakeTranscriptList()

    monkeypatch.setattr(transcript_tools, "_youtube_transcript_api", lambda: _FakeApi())

    payload = _run(
        _tool("extract_transcript").handler(
            {"url": "https://youtu.be/abc123XYZ89", "max_chars": 500}
        )
    )

    assert payload["status"] == "ok"
    data = payload["data"]
    assert data["source_type"] == "video_transcript"
    assert data["canonical_url"] == "https://www.youtube.com/watch?v=abc123XYZ89"
    assert data["truncated"] is False
    assert "normalized transcript path" in data["text"]
    assert data["metadata"]["provider"] == "youtube"
    assert data["metadata"]["video_id"] == "abc123XYZ89"
    assert data["metadata"]["language_code"] == "en"


def test_all_transcript_tools_are_async():
    for tool in get_tools():
        assert tool.is_async is True, f"{tool.name} should be async"
