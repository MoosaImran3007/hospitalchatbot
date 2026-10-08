# Tests for /chat API route:
#
# 1. Chat request with a valid JWT token succeeds
# 2. Chat request without a JWT token is rejected
import pytest
from fastapi.testclient import TestClient

from main import app
from routes import chat as chat_route
from auth.jwt import create_access_token


client = TestClient(app)


def test_chat_with_valid_token(monkeypatch):

    # Fake chatbot stream
    def fake_stream_chat(request, current_user):

        assert request.query == "Hello"
        assert current_user["id"] == "123"
        assert current_user["email"] == "test@example.com"
        assert current_user["role"] == "user"

        yield "Hello from chatbot"


    # Replace real stream_chat() with our fake function
    monkeypatch.setattr(
        chat_route,
        "stream_chat",
        fake_stream_chat
    )


    # Create a real access token
    token = create_access_token(
        user_id="123",
        email="test@example.com",
        role="user"
    )


    # Send request to /chat
    response = client.post(
        "/chat",
        json={
            "query": "Hello"
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )


    assert response.status_code == 200

    assert response.headers["content-type"].startswith(
        "text/event-stream"
    )

    assert response.text == "Hello from chatbot"


def test_chat_without_token():

    response = client.post(
        "/chat",
        json={
            "query": "Hello"
        }
    )

    assert response.status_code == 401