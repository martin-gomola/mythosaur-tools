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


def test_notebooklm_capability_disabled(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_NOTEBOOKLM_ENABLED", "false")
    result = notebooklm_tools._auth_status({})
    assert result["status"] == "error"
    assert result["error"]["code"] == "capability_disabled"
