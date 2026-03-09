import subprocess

from services.mcp_server.plugins import notebooklm_tools


def test_notebooklm_auth_status_authenticated(monkeypatch):
    monkeypatch.setattr(notebooklm_tools, "_binary_exists", lambda: True)
    monkeypatch.setattr(
        notebooklm_tools,
        "_run_command",
        lambda cmd, timeout_seconds: subprocess.CompletedProcess(cmd, 0, "authenticated", ""),
    )

    result = notebooklm_tools._auth_status({"profile": "mythosaur"})

    assert result["status"] == "ok"
    assert result["data"]["authenticated"] is True
    assert result["data"]["profile"] == "mythosaur"


def test_notebooklm_auth_status_needs_login(monkeypatch):
    monkeypatch.setattr(notebooklm_tools, "_binary_exists", lambda: True)
    monkeypatch.setattr(
        notebooklm_tools,
        "_run_command",
        lambda cmd, timeout_seconds: subprocess.CompletedProcess(cmd, 2, "", "Profile not found"),
    )

    result = notebooklm_tools._auth_status({})

    assert result["status"] == "ok"
    assert result["data"]["authenticated"] is False
    assert result["data"]["needs_login"] is True
    assert "Profile not found" in result["data"]["message"]


def test_notebooklm_list_notebooks(monkeypatch):
    monkeypatch.setattr(
        notebooklm_tools,
        "_run_json_command",
        lambda *args, **kwargs: (
            {
                "notebooks": [
                    {"id": "nb1", "title": "Research", "source_count": 3},
                    {"id": "nb2", "title": "Ops", "source_count": 2},
                ],
                "count": 2,
                "owned_count": 2,
                "shared_count": 0,
                "shared_by_me_count": 0,
            },
            None,
        ),
    )

    result = notebooklm_tools._list_notebooks({"max_results": 1})

    assert result["status"] == "ok"
    assert result["data"]["returned_count"] == 1
    assert result["data"]["total_count"] == 2
    assert result["data"]["notebooks"][0]["title"] == "Research"


def test_notebooklm_query_notebook(monkeypatch):
    monkeypatch.setattr(
        notebooklm_tools,
        "_run_json_command",
        lambda *args, **kwargs: (
            {
                "answer": "Three takeaways.",
                "conversation_id": "conv1",
                "sources_used": [{"id": "src1"}],
                "citations": {"src1": [1, 2]},
            },
            None,
        ),
    )

    result = notebooklm_tools._query_notebook({"notebook_id": "nb1", "question": "Summarize this notebook"})

    assert result["status"] == "ok"
    assert result["data"]["notebook_id"] == "nb1"
    assert result["data"]["answer"] == "Three takeaways."
    assert result["data"]["conversation_id"] == "conv1"


def test_notebooklm_query_notebook_requires_inputs():
    result = notebooklm_tools._query_notebook({"notebook_id": "", "question": ""})

    assert result["status"] == "error"
    assert result["error"]["code"] == "missing_args"


def test_notebooklm_create_notebook(monkeypatch):
    monkeypatch.setattr(
        notebooklm_tools,
        "_run_json_command",
        lambda *args, **kwargs: (
            {"notebook_id": "nb-new", "title": "Research", "url": "https://notebooklm.google.com/notebook/nb-new"},
            None,
        ),
    )

    result = notebooklm_tools._create_notebook({"title": "Research"})

    assert result["status"] == "ok"
    assert result["data"]["notebook_id"] == "nb-new"
    assert result["data"]["title"] == "Research"


def test_notebooklm_create_notebook_requires_title():
    result = notebooklm_tools._create_notebook({"title": ""})

    assert result["status"] == "error"
    assert result["error"]["code"] == "missing_args"


def test_notebooklm_list_sources(monkeypatch):
    monkeypatch.setattr(
        notebooklm_tools,
        "_run_json_command",
        lambda *args, **kwargs: (
            {
                "sources": [
                    {"id": "src1", "title": "Article A", "type": "url"},
                    {"id": "src2", "title": "Notes", "type": "text"},
                ]
            },
            None,
        ),
    )

    result = notebooklm_tools._list_sources({"notebook_id": "nb1"})

    assert result["status"] == "ok"
    assert result["data"]["source_count"] == 2
    assert result["data"]["sources"][0]["id"] == "src1"


def test_notebooklm_list_sources_requires_notebook_id():
    result = notebooklm_tools._list_sources({"notebook_id": ""})

    assert result["status"] == "error"
    assert result["error"]["code"] == "missing_args"


def test_notebooklm_add_source(monkeypatch):
    monkeypatch.setattr(
        notebooklm_tools,
        "_run_json_command",
        lambda *args, **kwargs: (
            {"source_id": "src-new", "title": "My Article", "status": "added"},
            None,
        ),
    )

    result = notebooklm_tools._add_source({
        "notebook_id": "nb1",
        "source_type": "url",
        "source_value": "https://example.com/article",
    })

    assert result["status"] == "ok"
    assert result["data"]["source_id"] == "src-new"
    assert result["data"]["source_type"] == "url"


def test_notebooklm_add_source_requires_all_fields():
    result = notebooklm_tools._add_source({"notebook_id": "nb1", "source_type": "", "source_value": ""})

    assert result["status"] == "error"
    assert result["error"]["code"] == "missing_args"


def test_notebooklm_add_source_rejects_bad_type():
    result = notebooklm_tools._add_source({
        "notebook_id": "nb1",
        "source_type": "podcast",
        "source_value": "something",
    })

    assert result["status"] == "error"
    assert result["error"]["code"] == "invalid_source_type"


def test_notebooklm_create_studio_content(monkeypatch):
    monkeypatch.setattr(
        notebooklm_tools,
        "_run_json_command",
        lambda *args, **kwargs: (
            {"artifact_id": "art1", "status": "generating", "url": ""},
            None,
        ),
    )

    result = notebooklm_tools._create_studio_content({
        "notebook_id": "nb1",
        "content_type": "audio",
        "instructions": "Focus on key findings",
    })

    assert result["status"] == "ok"
    assert result["data"]["artifact_id"] == "art1"
    assert result["data"]["content_type"] == "audio"


def test_notebooklm_create_studio_content_requires_notebook_id():
    result = notebooklm_tools._create_studio_content({"notebook_id": ""})

    assert result["status"] == "error"
    assert result["error"]["code"] == "missing_args"


def test_notebooklm_create_studio_content_rejects_bad_type():
    result = notebooklm_tools._create_studio_content({
        "notebook_id": "nb1",
        "content_type": "movie",
    })

    assert result["status"] == "error"
    assert result["error"]["code"] == "invalid_content_type"


def test_notebooklm_download_artifact(monkeypatch):
    monkeypatch.setattr(
        notebooklm_tools,
        "_run_json_command",
        lambda *args, **kwargs: (
            {"file_path": "/tmp/podcast.mp3", "file_size": 1024000, "status": "downloaded"},
            None,
        ),
    )

    result = notebooklm_tools._download_artifact({
        "notebook_id": "nb1",
        "artifact_id": "art1",
        "artifact_type": "audio",
    })

    assert result["status"] == "ok"
    assert result["data"]["file_path"] == "/tmp/podcast.mp3"
    assert result["data"]["artifact_type"] == "audio"


def test_notebooklm_download_artifact_requires_fields():
    result = notebooklm_tools._download_artifact({"notebook_id": "", "artifact_id": ""})

    assert result["status"] == "error"
    assert result["error"]["code"] == "missing_args"


def test_notebooklm_share(monkeypatch):
    monkeypatch.setattr(
        notebooklm_tools,
        "_run_json_command",
        lambda *args, **kwargs: (
            {"url": "https://notebooklm.google.com/share/abc", "status": "shared"},
            None,
        ),
    )

    result = notebooklm_tools._share_notebook({"notebook_id": "nb1", "share_type": "public"})

    assert result["status"] == "ok"
    assert result["data"]["share_type"] == "public"
    assert "notebooklm.google.com" in result["data"]["url"]


def test_notebooklm_share_requires_notebook_id():
    result = notebooklm_tools._share_notebook({"notebook_id": ""})

    assert result["status"] == "error"
    assert result["error"]["code"] == "missing_args"


def test_notebooklm_share_rejects_bad_type():
    result = notebooklm_tools._share_notebook({"notebook_id": "nb1", "share_type": "secret"})

    assert result["status"] == "error"
    assert result["error"]["code"] == "invalid_share_type"


def test_notebooklm_capability_disabled(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_NOTEBOOKLM_ENABLED", "false")
    result = notebooklm_tools._auth_status({})
    assert result["status"] == "error"
    assert result["error"]["code"] == "capability_disabled"


def test_notebooklm_new_tools_disabled(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_NOTEBOOKLM_ENABLED", "false")

    assert notebooklm_tools._create_notebook({"title": "X"})["error"]["code"] == "capability_disabled"
    assert notebooklm_tools._list_sources({"notebook_id": "X"})["error"]["code"] == "capability_disabled"
    assert notebooklm_tools._add_source({"notebook_id": "X", "source_type": "url", "source_value": "X"})["error"]["code"] == "capability_disabled"
    assert notebooklm_tools._create_studio_content({"notebook_id": "X"})["error"]["code"] == "capability_disabled"
    assert notebooklm_tools._download_artifact({"notebook_id": "X", "artifact_id": "X"})["error"]["code"] == "capability_disabled"
    assert notebooklm_tools._share_notebook({"notebook_id": "X"})["error"]["code"] == "capability_disabled"
