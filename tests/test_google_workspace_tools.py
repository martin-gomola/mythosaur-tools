from pathlib import Path

from services.mcp_server.plugins import google_workspace_tools as google_tools


class _CalendarList:
    def execute(self):
        return {
            "items": [
                {
                    "id": "evt1",
                    "summary": "Sync",
                    "start": {"dateTime": "2026-03-06T10:00:00Z"},
                    "end": {"dateTime": "2026-03-06T11:00:00Z"},
                }
            ]
        }


class _CalendarInsert:
    def execute(self):
        return {
            "id": "evt2",
            "summary": "Daily Briefing",
            "start": {"dateTime": "2026-03-09T08:00:00Z"},
            "end": {"dateTime": "2026-03-09T08:15:00Z"},
            "htmlLink": "https://calendar.google.com/event?eid=evt2",
            "attendees": [{"email": "team@example.com"}],
        }


class _CalendarEvents:
    def list(self, **kwargs):
        return _CalendarList()

    def insert(self, **kwargs):
        return _CalendarInsert()


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


class _GmailSend:
    def execute(self):
        return {"id": "sent1", "threadId": "thr2", "labelIds": ["SENT"]}


class _GmailMessages:
    def list(self, **kwargs):
        class _Result:
            def execute(self_nonlocal):
                return {"resultSizeEstimate": 1, "messages": [{"id": "msg1"}]}

        return _Result()

    def get(self, **kwargs):
        return _GmailGet()

    def send(self, **kwargs):
        return _GmailSend()


class _GmailUsers:
    def messages(self):
        return _GmailMessages()


class _GmailService:
    def users(self):
        return _GmailUsers()


class _DriveList:
    def execute(self):
        return {"files": [{"id": "file1", "name": "Roadmap"}]}


class _DriveCreate:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _DriveFiles:
    def list(self, **kwargs):
        return _DriveList()

    def create(self, **kwargs):
        body = kwargs.get("body") or {}
        if body.get("mimeType") == "application/vnd.google-apps.folder":
            return _DriveCreate(
                {
                    "id": "folder1",
                    "name": body.get("name", ""),
                    "mimeType": body.get("mimeType", ""),
                    "webViewLink": "https://drive.google.com/folder1",
                }
            )
        return _DriveCreate(
            {
                "id": "upload1",
                "name": body.get("name", ""),
                "mimeType": "text/plain",
                "size": "12",
                "webViewLink": "https://drive.google.com/file1",
                "webContentLink": "https://drive.google.com/download/file1",
            }
        )


class _DriveService:
    def files(self):
        return _DriveFiles()


class _SheetsGet:
    def execute(self):
        return {"majorDimension": "ROWS", "values": [["A1", "B1"]]}


class _SheetsUpdate:
    def execute(self):
        return {"updatedRange": "Sheet1!A1:B1", "updatedRows": 1, "updatedColumns": 2, "updatedCells": 2}


class _SheetsAppend:
    def execute(self):
        return {
            "tableRange": "Sheet1!A1:B1",
            "updates": {"updatedRange": "Sheet1!A2:B2", "updatedRows": 1, "updatedColumns": 2, "updatedCells": 2},
        }


class _SheetsValues:
    def get(self, **kwargs):
        return _SheetsGet()

    def update(self, **kwargs):
        return _SheetsUpdate()

    def append(self, **kwargs):
        return _SheetsAppend()


class _SheetsBatchUpdate:
    def execute(self):
        return {"replies": [{"addSheet": {"properties": {"sheetId": 99, "title": "Routes", "index": 1}}}]}


class _SheetsSpreadsheets:
    def values(self):
        return _SheetsValues()

    def batchUpdate(self, **kwargs):
        return _SheetsBatchUpdate()


class _SheetsService:
    def spreadsheets(self):
        return _SheetsSpreadsheets()


class _DocsGet:
    def execute(self):
        return {
            "documentId": "doc1",
            "title": "Ops Notes",
            "revisionId": "rev1",
            "body": {
                "content": [
                    {"paragraph": {"elements": [{"textRun": {"content": "Line one.\n"}}]}},
                    {"paragraph": {"elements": [{"textRun": {"content": "Line two.\n"}}]}},
                ]
            },
        }


class _DocsCreate:
    def execute(self):
        return {"documentId": "doc2", "title": "Daily Briefing", "revisionId": "rev2"}


class _DocsBatchUpdate:
    def execute(self):
        return {"replies": []}


class _DocsDocuments:
    def get(self, **kwargs):
        return _DocsGet()

    def create(self, **kwargs):
        return _DocsCreate()

    def batchUpdate(self, **kwargs):
        return _DocsBatchUpdate()


class _DocsService:
    def documents(self):
        return _DocsDocuments()


class _MediaFileUpload:
    def __init__(self, filename, mimetype=None, resumable=False):
        self.filename = filename
        self.mimetype = mimetype
        self.resumable = resumable


class _MediaInMemoryUpload:
    def __init__(self, body, mimetype=None, resumable=False):
        self.body = body
        self.mimetype = mimetype
        self.resumable = resumable


def test_google_calendar_events(monkeypatch):
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _CalendarService())
    result = google_tools._calendar_events(
        {"time_min": "2026-03-06T00:00:00Z", "time_max": "2026-03-07T00:00:00Z"}
    )
    assert result["status"] == "ok"
    assert result["data"]["events"][0]["summary"] == "Sync"


def test_google_calendar_create_event(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_GOOGLE_CALENDAR_WRITE_ENABLED", "true")
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _CalendarService())
    result = google_tools._calendar_create_event(
        {
            "summary": "Daily Briefing",
            "start_time": "2026-03-09T08:00:00Z",
            "end_time": "2026-03-09T08:15:00Z",
            "attendees": ["team@example.com"],
        }
    )
    assert result["status"] == "ok"
    assert result["data"]["id"] == "evt2"
    assert result["data"]["summary"] == "Daily Briefing"


def test_gmail_unread(monkeypatch):
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _GmailService())
    result = google_tools._gmail_unread({"max_results": 5, "include_snippets": True})
    assert result["status"] == "ok"
    assert result["data"]["unread_count"] == 1
    assert result["data"]["messages"][0]["subject"] == "Demo"


def test_gmail_send(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_GOOGLE_GMAIL_SEND_ENABLED", "true")
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _GmailService())
    result = google_tools._gmail_send(
        {"to": ["person@example.com"], "subject": "Hello", "body_text": "Plain text body"}
    )
    assert result["status"] == "ok"
    assert result["data"]["id"] == "sent1"
    assert result["data"]["subject"] == "Hello"


def test_google_drive_recent_files(monkeypatch):
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _DriveService())
    result = google_tools._drive_recent_files({"max_results": 5})
    assert result["status"] == "ok"
    assert result["data"]["files"][0]["name"] == "Roadmap"


def test_google_drive_create_folder(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_GOOGLE_DRIVE_WRITE_ENABLED", "true")
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _DriveService())
    result = google_tools._drive_create_folder({"folder_name": "Routes"})
    assert result["status"] == "ok"
    assert result["data"]["id"] == "folder1"
    assert result["data"]["name"] == "Routes"


def test_google_drive_upload_file(monkeypatch, tmp_path):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_GOOGLE_DRIVE_WRITE_ENABLED", "true")
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _DriveService())
    monkeypatch.setenv("MYTHOSAUR_TOOLS_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setattr("googleapiclient.http.MediaFileUpload", _MediaFileUpload)
    sample = tmp_path / "sample.txt"
    sample.write_text("hello world", encoding="utf-8")

    result = google_tools._drive_upload_file({"path": "sample.txt"})

    assert result["status"] == "ok"
    assert result["data"]["id"] == "upload1"
    assert result["data"]["source_path"] == str(sample)


def test_google_drive_create_text_file(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_GOOGLE_DRIVE_WRITE_ENABLED", "true")
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _DriveService())
    monkeypatch.setattr("googleapiclient.http.MediaInMemoryUpload", _MediaInMemoryUpload)

    result = google_tools._drive_create_text_file({"file_name": "briefing.md", "content": "# Daily briefing"})

    assert result["status"] == "ok"
    assert result["data"]["id"] == "upload1"
    assert result["data"]["name"] == "briefing.md"
    assert result["data"]["content_bytes"] > 0


def test_google_sheets_read_range(monkeypatch):
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _SheetsService())
    result = google_tools._sheets_read_range({"spreadsheet_id": "sheet1", "range": "A1:B1"})
    assert result["status"] == "ok"
    assert result["data"]["values"] == [["A1", "B1"]]


def test_google_sheets_write_range(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_GOOGLE_SHEETS_WRITE_ENABLED", "true")
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _SheetsService())
    result = google_tools._sheets_write_range(
        {"spreadsheet_id": "sheet1", "range": "Sheet1!A1:B1", "values": [["A", "B"]]}
    )
    assert result["status"] == "ok"
    assert result["data"]["updated_cells"] == 2


def test_google_sheets_append_rows(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_GOOGLE_SHEETS_WRITE_ENABLED", "true")
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _SheetsService())
    result = google_tools._sheets_append_rows(
        {"spreadsheet_id": "sheet1", "range": "Sheet1!A:B", "rows": [["A", "B"]]}
    )
    assert result["status"] == "ok"
    assert result["data"]["updated_rows"] == 1


def test_google_sheets_create_sheet(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_GOOGLE_SHEETS_WRITE_ENABLED", "true")
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _SheetsService())
    result = google_tools._sheets_create_sheet({"spreadsheet_id": "sheet1", "sheet_title": "Routes"})
    assert result["status"] == "ok"
    assert result["data"]["sheet_id"] == 99
    assert result["data"]["sheet_title"] == "Routes"


def test_google_docs_get(monkeypatch):
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _DocsService())
    result = google_tools._docs_get({"document_id": "doc1"})
    assert result["status"] == "ok"
    assert result["data"]["document_id"] == "doc1"
    assert result["data"]["title"] == "Ops Notes"
    assert "Line one." in result["data"]["text"]


def test_google_docs_create(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_GOOGLE_DOCS_WRITE_ENABLED", "true")
    monkeypatch.setattr(google_tools, "_build_service", lambda *args, **kwargs: _DocsService())
    result = google_tools._docs_create({"title": "Daily Briefing", "content": "Status update"})
    assert result["status"] == "ok"
    assert result["data"]["document_id"] == "doc2"
    assert result["data"]["title"] == "Daily Briefing"
    assert result["data"]["content_chars"] == len("Status update")


def test_google_maps_build_route_link():
    result = google_tools._maps_build_route_link(
        {"origin": "Bratislava", "destination": "Vienna", "waypoints": ["Hainburg"], "travel_mode": "driving"}
    )
    assert result["status"] == "ok"
    assert "google.com/maps/dir/" in result["data"]["url"]
    assert "origin=Bratislava" in result["data"]["url"]


def test_google_maps_build_place_link():
    result = google_tools._maps_build_place_link({"query": "Bratislava Castle"})
    assert result["status"] == "ok"
    assert "google.com/maps/search/" in result["data"]["url"]
    assert "Bratislava+Castle" in result["data"]["url"]


def test_google_capability_guard(monkeypatch):
    monkeypatch.setenv("MYTHOSAUR_TOOLS_GOOGLE_GMAIL_SEND_ENABLED", "false")
    result = google_tools._gmail_send(
        {"to": ["person@example.com"], "subject": "Hello", "body_text": "Plain text body"}
    )
    assert result["status"] == "error"
    assert result["error"]["code"] == "capability_disabled"
