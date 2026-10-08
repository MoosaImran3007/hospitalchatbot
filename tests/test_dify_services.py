# stream_chat()
# │
# ├── Empty query                         ✅
# ├── Missing DIFY_API_KEY               ✅
# ├── Missing DIFY_API_URL               ✅
# ├── Empty conversation ID              ✅
# ├── Unauthorized conversation         ✅
# │
# ├── Successful Dify stream             ✅
# ├── Dify HTTP error                    ✅
# ├── Dify timeout                       ✅
# ├── Dify connection error              ✅
# ├── Malformed JSON                     ✅
# ├── Dify error event                   ✅
# │
# ├── New conversation saved             ✅
# ├── Existing conversation updated      ✅
# │
# ├── Mem0 failure                       ✅
# └── Unexpected exception               ✅
# Tests for Dify chat streaming service:
#
# 1. Empty query is rejected
# 2. Missing DIFY_API_KEY is handled
# 3. Missing DIFY_API_URL is handled
# 4. Whitespace-only conversation ID is rejected
# 5. Conversation belonging to another user is rejected
# 6. Successful Dify streaming response is processed
# 7. Dify HTTP error is handled
# 8. Dify request timeout is handled
# 9. Dify connection error is handled
# 10. Malformed Dify JSON is ignored safely
# 11. Dify error event is handled
# 12. New conversation is saved to the database
# 13. Existing conversation timestamp is updated
# 14. Mem0 failure does not break the chat
# 15. Unexpected exception is handled
import json

from models.chat import ChatRequest
from services import dify_services


def test_stream_chat_rejects_empty_query():

    request = ChatRequest(
        query="",
        conversation_id=None
    )

    current_user = {
        "id": "123",
        "email": "test@example.com",
        "role": "user"
    }

    result = dify_services.stream_chat(
        request,
        current_user
    )

    events = list(result)

    assert len(events) == 1

    assert events[0].startswith("event: error")

    data = json.loads(
        events[0].split("data: ", 1)[1].strip()
    )

    assert data["message"] == "Query cannot be empty"
def test_stream_chat_without_dify_api_key(monkeypatch):

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_KEY",
        None
    )

    request = ChatRequest(
        query="Hello",
        conversation_id=None
    )

    current_user = {
        "id": "123",
        "email": "test@example.com",
        "role": "user"
    }

    result = dify_services.stream_chat(
        request,
        current_user
    )

    events = list(result)

    assert len(events) == 1

    assert events[0].startswith("event: error")

    data = json.loads(
        events[0].split("data: ", 1)[1].strip()
    )

    assert data["message"] == "DIFY_API_KEY is not configured"


def test_stream_chat_without_dify_api_url(monkeypatch):

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_KEY",
        "fake-api-key"
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_URL",
        None
    )

    request = ChatRequest(
        query="Hello",
        conversation_id=None
    )

    current_user = {
        "id": "123",
        "email": "test@example.com",
        "role": "user"
    }

    result = dify_services.stream_chat(
        request,
        current_user
    )

    events = list(result)

    assert len(events) == 1

    assert events[0].startswith("event: error")

    data = json.loads(
        events[0].split("data: ", 1)[1].strip()
    )

    assert data["message"] == "DIFY_API_URL is not configured"
from unittest.mock import MagicMock
def test_stream_chat_rejects_conversation_of_another_user(
    monkeypatch
):

    # Fake database connection
    db = MagicMock()
    cursor = MagicMock()

    # Simulate: conversation was NOT found for this user
    cursor.fetchone.return_value = None

    db.cursor.return_value = cursor

    monkeypatch.setattr(
        dify_services,
        "get_db",
        lambda: db
    )

    # Configuration is valid
    monkeypatch.setattr(
        dify_services,
        "DIFY_API_KEY",
        "fake-api-key"
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_URL",
        "http://fake-dify"
    )

    request = ChatRequest(
        query="Hello",
        conversation_id="conversation-456"
    )

    current_user = {
        "id": "user-123",
        "email": "test@example.com",
        "role": "user"
    }

    result = dify_services.stream_chat(
        request,
        current_user
    )

    events = list(result)

    assert len(events) == 1

    assert events[0].startswith("event: error")

    data = json.loads(
        events[0].split("data: ", 1)[1].strip()
    )

    assert data["message"] == (
        "You do not have access to this conversation"
    )
def test_stream_chat_rejects_empty_conversation_id():

    request = ChatRequest(
        query="Hello",
        conversation_id="   "
    )

    current_user = {
        "id": "123",
        "email": "test@example.com",
        "role": "user"
    }

    result = dify_services.stream_chat(
        request,
        current_user
    )

    events = list(result)

    assert len(events) == 1

    assert events[0].startswith("event: error")

    data = json.loads(
        events[0].split("data: ", 1)[1].strip()
    )

    assert data["message"] == (
        "conversation_id cannot be empty"
    )
def test_stream_chat_processes_dify_message(monkeypatch):

    class FakeDifyResponse:

        status_code = 200

        def iter_lines(self, decode_unicode=True):

            yield (
                'data: {"event":"message",'
                '"conversation_id":"conv-123",'
                '"answer":"Hello "}'
            )

            yield (
                'data: {"event":"message",'
                '"conversation_id":"conv-123",'
                '"answer":"world!"}'
            )

            yield (
                'data: {"event":"message_end",'
                '"conversation_id":"conv-123"}'
            )

        def close(self):
            pass


    def fake_post(*args, **kwargs):

        assert args[0] == dify_services.DIFY_API_URL

        assert kwargs["headers"]["Authorization"] == (
            f"Bearer {dify_services.DIFY_API_KEY}"
        )

        assert kwargs["headers"]["Content-Type"] == (
            "application/json"
        )

        assert kwargs["stream"] is True
        assert kwargs["timeout"] == 120

        assert kwargs["json"]["query"] == "Hello"
        assert kwargs["json"]["user"] == "123"

        return FakeDifyResponse()


    monkeypatch.setattr(
        dify_services.requests,
        "post",
        fake_post
    )

    # Prevent this test from actually writing to PostgreSQL
    monkeypatch.setattr(
        dify_services,
        "get_db",
        lambda: MagicMock()
    )

    # Prevent this test from actually calling Mem0
    monkeypatch.setattr(
        dify_services,
        "add_memory",
        lambda **kwargs: None
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_KEY",
        "fake-api-key"
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_URL",
        "http://fake-dify"
    )

    request = ChatRequest(
        query="Hello",
        conversation_id=None
    )

    current_user = {
        "id": "123",
        "email": "test@example.com",
        "role": "user"
    }

    result = dify_services.stream_chat(
        request,
        current_user
    )

    events = list(result)

    assert len(events) == 3

    assert '"content": "Hello "' in events[0]
    assert '"content": "world!"' in events[1]

    assert events[2].startswith("event: done")
def test_stream_chat_handles_dify_http_error(monkeypatch):

    class FakeDifyResponse:

        status_code = 500

        def json(self):
            return {
                "message": "Internal server error"
            }

        def close(self):
            pass


    def fake_post(*args, **kwargs):
        return FakeDifyResponse()


    monkeypatch.setattr(
        dify_services.requests,
        "post",
        fake_post
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_KEY",
        "fake-api-key"
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_URL",
        "http://fake-dify"
    )

    request = ChatRequest(
        query="Hello",
        conversation_id=None
    )

    current_user = {
        "id": "123",
        "email": "test@example.com",
        "role": "user"
    }

    result = dify_services.stream_chat(
        request,
        current_user
    )

    events = list(result)

    assert len(events) == 1

    assert events[0].startswith("event: error")

    data = json.loads(
        events[0].split("data: ", 1)[1].strip()
    )

    assert data["message"] == "Dify returned an error"
    assert data["status"] == 500
    assert data["response"]["message"] == "Internal server error"
def test_stream_chat_handles_dify_timeout(monkeypatch):

    def fake_post(*args, **kwargs):
        raise dify_services.requests.Timeout(
            "Dify request timed out"
        )

    monkeypatch.setattr(
        dify_services.requests,
        "post",
        fake_post
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_KEY",
        "fake-api-key"
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_URL",
        "http://fake-dify"
    )

    request = ChatRequest(
        query="Hello",
        conversation_id=None
    )

    current_user = {
        "id": "123",
        "email": "test@example.com",
        "role": "user"
    }

    result = dify_services.stream_chat(
        request,
        current_user
    )

    events = list(result)

    assert len(events) == 1

    assert events[0].startswith("event: error")

    data = json.loads(
        events[0].split("data: ", 1)[1].strip()
    )

    assert data["message"] == "Dify request timed out"
from unittest.mock import MagicMock
def test_stream_chat_handles_dify_connection_error(monkeypatch):

    def fake_post(*args, **kwargs):
        raise dify_services.requests.RequestException(
            "Connection failed"
        )

    monkeypatch.setattr(
        dify_services.requests,
        "post",
        fake_post
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_KEY",
        "fake-api-key"
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_URL",
        "http://fake-dify"
    )

    request = ChatRequest(
        query="Hello",
        conversation_id=None
    )

    current_user = {
        "id": "123",
        "email": "test@example.com",
        "role": "user"
    }

    events = list(
        dify_services.stream_chat(
            request,
            current_user
        )
    )

    assert len(events) == 1
    assert events[0].startswith("event: error")

    data = json.loads(
        events[0].split("data: ", 1)[1].strip()
    )

    assert data["message"] == "Could not connect to Dify"
    assert data["error"] == "Connection failed"
def test_stream_chat_ignores_malformed_dify_json(monkeypatch):

    class FakeDifyResponse:

        status_code = 200

        def iter_lines(self, decode_unicode=True):

            yield "data: this-is-not-json"

            yield (
                'data: {"event":"message",'
                '"conversation_id":"conv-123",'
                '"answer":"Hello"}'
            )

            yield (
                'data: {"event":"message_end",'
                '"conversation_id":"conv-123"}'
            )

        def close(self):
            pass

    def fake_post(*args, **kwargs):
        return FakeDifyResponse()

    monkeypatch.setattr(
        dify_services.requests,
        "post",
        fake_post
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_KEY",
        "fake-api-key"
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_URL",
        "http://fake-dify"
    )

    monkeypatch.setattr(
        dify_services,
        "get_db",
        lambda: MagicMock()
    )

    monkeypatch.setattr(
        dify_services,
        "add_memory",
        lambda **kwargs: None
    )

    request = ChatRequest(
        query="Hello",
        conversation_id=None
    )

    current_user = {
        "id": "123",
        "email": "test@example.com",
        "role": "user"
    }

    events = list(
        dify_services.stream_chat(
            request,
            current_user
        )
    )

    assert len(events) == 2

    assert '"content": "Hello"' in events[0]
    assert events[1].startswith("event: done")
def test_stream_chat_handles_dify_error_event(monkeypatch):

    class FakeDifyResponse:

        status_code = 200

        def iter_lines(self, decode_unicode=True):

            yield (
                'data: {"event":"error",'
                '"message":"Workflow failed",'
                '"code":"workflow_error"}'
            )

        def close(self):
            pass

    def fake_post(*args, **kwargs):
        return FakeDifyResponse()

    monkeypatch.setattr(
        dify_services.requests,
        "post",
        fake_post
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_KEY",
        "fake-api-key"
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_URL",
        "http://fake-dify"
    )

    request = ChatRequest(
        query="Hello",
        conversation_id=None
    )

    current_user = {
        "id": "123",
        "email": "test@example.com",
        "role": "user"
    }

    events = list(
        dify_services.stream_chat(
            request,
            current_user
        )
    )

    assert len(events) == 1
    assert events[0].startswith("event: error")

    data = json.loads(
        events[0].split("data: ", 1)[1].strip()
    )

    assert data["error"]["message"] == "Workflow failed"
    assert data["error"]["code"] == "workflow_error"
def test_stream_chat_saves_new_conversation(
    monkeypatch
):

    class FakeDifyResponse:

        status_code = 200

        def iter_lines(self, decode_unicode=True):

            yield (
                'data: {"event":"message",'
                '"conversation_id":"new-conv-123",'
                '"answer":"Hello"}'
            )

            yield (
                'data: {"event":"message_end",'
                '"conversation_id":"new-conv-123"}'
            )

        def close(self):
            pass

    fake_db = MagicMock()
    fake_cursor = MagicMock()

    fake_db.cursor.return_value = fake_cursor

    def fake_post(*args, **kwargs):
        return FakeDifyResponse()

    monkeypatch.setattr(
        dify_services.requests,
        "post",
        fake_post
    )

    monkeypatch.setattr(
        dify_services,
        "get_db",
        lambda: fake_db
    )

    monkeypatch.setattr(
        dify_services,
        "add_memory",
        lambda **kwargs: None
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_KEY",
        "fake-api-key"
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_URL",
        "http://fake-dify"
    )

    request = ChatRequest(
        query="Hello",
        conversation_id=None
    )

    current_user = {
        "id": "123",
        "email": "test@example.com",
        "role": "user"
    }

    events = list(
        dify_services.stream_chat(
            request,
            current_user
        )
    )

    assert events[-1].startswith("event: done")

    fake_cursor.execute.assert_called_once()

    sql = fake_cursor.execute.call_args[0][0]

    assert "INSERT INTO conversations" in sql
    assert "user_id" in sql
    assert "conversation_id" in sql

    fake_db.commit.assert_called_once()
def test_stream_chat_updates_existing_conversation(
    monkeypatch
):

    class FakeDifyResponse:

        status_code = 200

        def iter_lines(self, decode_unicode=True):

            yield (
                'data: {"event":"message",'
                '"conversation_id":"existing-conv",'
                '"answer":"Hello"}'
            )

            yield (
                'data: {"event":"message_end",'
                '"conversation_id":"existing-conv"}'
            )

        def close(self):
            pass

    fake_db = MagicMock()
    fake_cursor = MagicMock()

    fake_cursor.fetchone.return_value = ("database-row",)

    fake_db.cursor.return_value = fake_cursor

    def fake_post(*args, **kwargs):
        return FakeDifyResponse()

    monkeypatch.setattr(
        dify_services.requests,
        "post",
        fake_post
    )

    monkeypatch.setattr(
        dify_services,
        "get_db",
        lambda: fake_db
    )

    monkeypatch.setattr(
        dify_services,
        "add_memory",
        lambda **kwargs: None
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_KEY",
        "fake-api-key"
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_URL",
        "http://fake-dify"
    )

    request = ChatRequest(
        query="Hello",
        conversation_id="existing-conv"
    )

    current_user = {
        "id": "123",
        "email": "test@example.com",
        "role": "user"
    }

    events = list(
        dify_services.stream_chat(
            request,
            current_user
        )
    )

    assert events[-1].startswith("event: done")

    assert fake_cursor.execute.call_count == 2

    update_sql = fake_cursor.execute.call_args_list[1][0][0]

    assert "UPDATE conversations" in update_sql
    assert "updated_at = NOW()" in update_sql

    fake_db.commit.assert_called()
def test_stream_chat_continues_when_mem0_fails(
    monkeypatch
):

    class FakeDifyResponse:

        status_code = 200

        def iter_lines(self, decode_unicode=True):

            yield (
                'data: {"event":"message",'
                '"conversation_id":"conv-123",'
                '"answer":"Hello"}'
            )

            yield (
                'data: {"event":"message_end",'
                '"conversation_id":"conv-123"}'
            )

        def close(self):
            pass

    def fake_post(*args, **kwargs):
        return FakeDifyResponse()

    def failing_memory(**kwargs):
        raise Exception("Mem0 unavailable")

    monkeypatch.setattr(
        dify_services.requests,
        "post",
        fake_post
    )

    monkeypatch.setattr(
        dify_services,
        "get_db",
        lambda: MagicMock()
    )

    monkeypatch.setattr(
        dify_services,
        "add_memory",
        failing_memory
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_KEY",
        "fake-api-key"
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_URL",
        "http://fake-dify"
    )

    request = ChatRequest(
        query="Hello",
        conversation_id=None
    )

    current_user = {
        "id": "123",
        "email": "test@example.com",
        "role": "user"
    }

    events = list(
        dify_services.stream_chat(
            request,
            current_user
        )
    )

    assert events[-1].startswith("event: done")

    data = json.loads(
        events[-1].split("data: ", 1)[1].strip()
    )

    assert data["success"] is True
    assert data["memory_saved"] is False
def test_stream_chat_handles_unexpected_error(
    monkeypatch
):

    def fake_post(*args, **kwargs):
        raise ValueError("Something unexpected happened")

    monkeypatch.setattr(
        dify_services.requests,
        "post",
        fake_post
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_KEY",
        "fake-api-key"
    )

    monkeypatch.setattr(
        dify_services,
        "DIFY_API_URL",
        "http://fake-dify"
    )

    request = ChatRequest(
        query="Hello",
        conversation_id=None
    )

    current_user = {
        "id": "123",
        "email": "test@example.com",
        "role": "user"
    }

    events = list(
        dify_services.stream_chat(
            request,
            current_user
        )
    )

    assert len(events) == 1
    assert events[0].startswith("event: error")

    data = json.loads(
        events[0].split("data: ", 1)[1].strip()
    )

    assert data["message"] == "An unexpected error occurred"
    assert data["error"] == "Something unexpected happened"