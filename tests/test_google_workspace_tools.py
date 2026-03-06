from services.mcp_server.plugins import google_workspace_tools as google_tools


class _CalendarList:
    def execute(self):
        return {"items": [{"id": "evt1", "summary": "Sync", "start": {"dateTime": "2026-03-06T10:00:00Z"}, "end": {"dateTime": "2026-03-06T11:00:00Z"}}]}


class _CalendarEvents:
    def list(self, **kwargs):
        return _CalendarList()


class _CalendarService:
    def events(self):
        return _CalendarEvents()


class _GmailGet:
    def execute(self):
        return {
            "threadId": "thr1",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Demo"},
                    {"name": "From", "value": "team@example.com"},
                    {"name": "Date", "value": "Fri, 6 Mar 2026 10:00:00 +0000"},
                ]
            },
            "snippet": "hello",
        }


class _GmailMessages:
    def list(self, **kwargs):
        class _Result:
            def execute(self_nonlocal):
                return {"resultSizeEstimate": 1, "messages": [{"id": "msg1"}]}

        return _Result()

    def get(self, **kwargs):
        return _GmailGet()


class _GmailUsers:
    def messages(self):
        return _GmailMessages()


class _GmailService:
    def users(self):
        return _GmailUsers()


class _DriveFiles:
    def list(self, **kwargs):
        class _Result:
            def execute(self_nonlocal):
                return {"files": [{"id": "file1", "name": "Roadmap"}]}

        return _Result()


class _DriveService:
    def files(self):
        return _DriveFiles()


class _SheetsValues:
    def get(self, **kwargs):
        class _Result:
            def execute(self_nonlocal):
                return {"majorDimension": "ROWS", "values": [["A1", "B1"]]}

        return _Result()


class _SheetsSpreadsheets:
    def values(self):
        return _SheetsValues()


class _SheetsService:
    def spreadsheets(self):
        return _SheetsSpreadsheets()


def test_google_calendar_events(monkeypatch):
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _CalendarService())
    result = google_tools._calendar_events(
        {"time_min": "2026-03-06T00:00:00Z", "time_max": "2026-03-07T00:00:00Z"}
    )
    assert result["status"] == "ok"
    assert result["data"]["events"][0]["summary"] == "Sync"


def test_gmail_unread(monkeypatch):
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _GmailService())
    result = google_tools._gmail_unread({"max_results": 5, "include_snippets": True})
    assert result["status"] == "ok"
    assert result["data"]["unread_count"] == 1
    assert result["data"]["messages"][0]["subject"] == "Demo"


def test_google_drive_recent_files(monkeypatch):
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _DriveService())
    result = google_tools._drive_recent_files({"max_results": 5})
    assert result["status"] == "ok"
    assert result["data"]["files"][0]["name"] == "Roadmap"


def test_google_sheets_read_range(monkeypatch):
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _SheetsService())
    result = google_tools._sheets_read_range({"spreadsheet_id": "sheet1", "range": "A1:B1"})
    assert result["status"] == "ok"
    assert result["data"]["values"] == [["A1", "B1"]]
