# pload_document_to_kb()
# We tested:
# - ✅ Missing DIFY_KB_API_KEY
# - ✅ Missing DIFY_KB_DATASET_ID
# - ✅ Missing user_id
# - ✅ Missing filename
# - ✅ Empty document
# - ✅ Successful document upload
# - ✅ Dify upload HTTP error
# - ✅ Upload timeout
# - ✅ Dify connection error
# - ✅ Invalid JSON from Dify during upload
# - ✅ Missing document ID
# - ✅ Indexing failure
# - ✅ Indexing API HTTP error
# - ✅ Invalid JSON while checking indexing status
# - ✅ Creating the user_id metadata field
# - ✅ Metadata creation HTTP error
# - ✅ Metadata update HTTP error
# - ✅ Metadata verification HTTP error
# - ✅ Invalid JSON during metadata verification
# - ✅ Wrong user_id returned during metadata verification
# delete_document_from_kb()
# We tested:
# - ✅ Missing API key
# - ✅ Missing dataset ID
# - ✅ Missing document ID
# - ✅ Successful deletion with HTTP 200
# - ✅ Successful deletion with HTTP 204
# - ✅ Dify deletion HTTP error

# Tests for Dify Knowledge Base service:
#
# Upload document:
# 1. Missing DIFY_KB_API_KEY
# 2. Missing DIFY_KB_DATASET_ID
# 3. Missing user ID
# 4. Missing filename
# 5. Empty document
# 6. Successful document upload
# 7. Dify upload HTTP error
# 8. Upload timeout
# 9. Dify connection error
# 10. Invalid JSON from Dify during upload
# 11. Missing document ID
#
# Indexing:
# 12. Indexing error
# 13. Indexing status HTTP error
# 14. Invalid JSON during indexing status check
#
# Metadata:
# 15. Creates user_id metadata field when needed
# 16. Metadata creation HTTP error
# 17. Metadata update error
# 18. Metadata verification HTTP error
# 19. Invalid JSON during metadata verification
# 20. Wrong user_id in metadata
#
# Delete document:
# 21. Missing DIFY_KB_API_KEY
# 22. Missing DIFY_KB_DATASET_ID
# 23. Missing document ID
# 24. Successful deletion with HTTP 200
# 25. Successful deletion with HTTP 204
# 26. Dify deletion HTTP error

from unittest.mock import MagicMock

import pytest
import requests

from services import kb_service


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def mock_response(status_code=200, json_data=None, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.json.return_value = json_data
    return response


def valid_upload_flow(session):
    """
    Configure the mocked Dify API responses for a successful
    upload + indexing + metadata flow.
    """

    session.post.side_effect = [
        # 1. Upload document
        mock_response(
            201,
            {
                "document": {
                    "id": "dify-doc-123"
                },
                "batch": "batch-123"
            }
        ),

        # 2. Update document metadata
        mock_response(200, {})
    ]

    session.get.side_effect = [
        # 1. Indexing status
        mock_response(
            200,
            {
                "indexing_status": "completed",
                "segment_count": 5
            }
        ),

        # 2. Existing metadata
        mock_response(
            200,
            {
                "doc_metadata": [
                    {
                        "id": "metadata-123",
                        "name": "user_id",
                        "type": "string"
                    }
                ]
            }
        ),

        # 3. Verify metadata
        mock_response(
            200,
            {
                "indexing_status": "completed",
                "segment_count": 5,
                "doc_metadata": [
                    {
                        "id": "metadata-123",
                        "name": "user_id",
                        "value": "123"
                    }
                ]
            }
        )
    ]


# ---------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------

def test_upload_missing_api_key(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", None)

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b"hello"
        )

    assert str(exc.value) == "DIFY_KB_API_KEY is not configured"


def test_upload_missing_dataset_id(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", None)

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b"hello"
        )

    assert str(exc.value) == "DIFY_KB_DATASET_ID is not configured"


def test_upload_missing_user_id(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "",
            "test.txt",
            b"hello"
        )

    assert str(exc.value) == "user_id is required"


def test_upload_missing_filename(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "",
            b"hello"
        )

    assert str(exc.value) == "Filename is required"


def test_upload_empty_document(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b""
        )

    assert str(exc.value) == "Document is empty"


# ---------------------------------------------------------
# Upload API
# ---------------------------------------------------------

def test_upload_success(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    session = MagicMock()
    valid_upload_flow(session)

    monkeypatch.setattr(
        kb_service.requests,
        "Session",
        lambda: session
    )

    result = kb_service.upload_document_to_kb(
        user_id="123",
        filename="assessment_123.txt",
        file_content=b"hello world"
    )

    assert result["success"] is True
    assert result["user_id"] == "123"
    assert result["filename"] == "assessment_123.txt"
    assert result["document_id"] == "dify-doc-123"
    assert result["batch_id"] == "batch-123"
    assert result["indexing_status"] == "completed"
    assert result["segment_count"] == 5

    session.close.assert_called_once()


def test_upload_http_error(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    session = MagicMock()

    session.post.return_value = mock_response(
        400,
        {},
        "Bad Request"
    )

    monkeypatch.setattr(
        kb_service.requests,
        "Session",
        lambda: session
    )

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b"hello"
        )

    assert "Dify KB upload failed (HTTP 400)" in str(exc.value)
    session.close.assert_called_once()


def test_upload_timeout(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    session = MagicMock()

    session.post.side_effect = requests.Timeout()

    monkeypatch.setattr(
        kb_service.requests,
        "Session",
        lambda: session
    )

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b"hello"
        )

    assert str(exc.value) == "Dify Knowledge Base upload timed out"
    session.close.assert_called_once()


def test_upload_connection_error(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    session = MagicMock()

    session.post.side_effect = requests.ConnectionError(
        "Connection refused"
    )

    monkeypatch.setattr(
        kb_service.requests,
        "Session",
        lambda: session
    )

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b"hello"
        )

    assert "Could not connect to Dify Knowledge Base" in str(exc.value)
    session.close.assert_called_once()


def test_upload_invalid_json(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    session = MagicMock()

    response = mock_response(201)
    response.json.side_effect = ValueError()

    session.post.return_value = response

    monkeypatch.setattr(
        kb_service.requests,
        "Session",
        lambda: session
    )

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b"hello"
        )

    assert str(exc.value) == (
        "Dify returned an invalid JSON response during upload"
    )

    session.close.assert_called_once()


def test_upload_missing_document_id(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    session = MagicMock()

    session.post.return_value = mock_response(
        201,
        {
            "document": {},
            "batch": "batch-123"
        }
    )

    monkeypatch.setattr(
        kb_service.requests,
        "Session",
        lambda: session
    )

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b"hello"
        )

    assert str(exc.value) == "Dify did not return a document ID"
    session.close.assert_called_once()


# ---------------------------------------------------------
# Indexing
# ---------------------------------------------------------

def test_upload_indexing_error(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    session = MagicMock()

    session.post.return_value = mock_response(
        201,
        {
            "document": {
                "id": "doc-123"
            },
            "batch": "batch-123"
        }
    )

    session.get.return_value = mock_response(
        200,
        {
            "indexing_status": "error",
            "error": "Indexing failed"
        }
    )

    monkeypatch.setattr(
        kb_service.requests,
        "Session",
        lambda: session
    )

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b"hello"
        )

    assert "Dify document indexing failed" in str(exc.value)
    session.close.assert_called_once()


def test_upload_indexing_status_http_error(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    session = MagicMock()

    session.post.return_value = mock_response(
        201,
        {
            "document": {
                "id": "doc-123"
            },
            "batch": "batch-123"
        }
    )

    session.get.return_value = mock_response(
        500,
        {},
        "Internal Server Error"
    )

    monkeypatch.setattr(
        kb_service.requests,
        "Session",
        lambda: session
    )

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b"hello"
        )

    assert "Could not check Dify document status (HTTP 500)" in str(
        exc.value
    )

    session.close.assert_called_once()


def test_upload_indexing_invalid_json(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    session = MagicMock()

    session.post.return_value = mock_response(
        201,
        {
            "document": {
                "id": "doc-123"
            }
        }
    )

    response = mock_response(200)
    response.json.side_effect = ValueError()

    session.get.return_value = response

    monkeypatch.setattr(
        kb_service.requests,
        "Session",
        lambda: session
    )

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b"hello"
        )

    assert str(exc.value) == (
        "Dify returned invalid JSON while checking document status"
    )

    session.close.assert_called_once()


# ---------------------------------------------------------
# Metadata
# ---------------------------------------------------------

def test_upload_creates_metadata_field(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    session = MagicMock()

    session.post.side_effect = [
        # Upload
        mock_response(
            201,
            {
                "document": {
                    "id": "doc-123"
                },
                "batch": "batch-123"
            }
        ),

        # Create metadata field
        mock_response(
            201,
            {
                "id": "metadata-123",
                "name": "user_id",
                "type": "string"
            }
        ),

        # Update metadata
        mock_response(200, {})
    ]

    session.get.side_effect = [
        # Indexing
        mock_response(
            200,
            {
                "indexing_status": "completed"
            }
        ),

        # Existing metadata
        mock_response(
            200,
            {
                "doc_metadata": []
            }
        ),

        # Verify
        mock_response(
            200,
            {
                "indexing_status": "completed",
                "segment_count": 3,
                "doc_metadata": [
                    {
                        "id": "metadata-123",
                        "name": "user_id",
                        "value": "123"
                    }
                ]
            }
        )
    ]

    monkeypatch.setattr(
        kb_service.requests,
        "Session",
        lambda: session
    )

    result = kb_service.upload_document_to_kb(
        "123",
        "test.txt",
        b"hello"
    )

    assert result["success"] is True
    assert result["document_id"] == "doc-123"

    # Three POST calls:
    # upload + create metadata + update metadata
    assert session.post.call_count == 3

    session.close.assert_called_once()


def test_upload_metadata_creation_http_error(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    session = MagicMock()

    session.post.side_effect = [
        mock_response(
            201,
            {
                "document": {
                    "id": "doc-123"
                }
            }
        ),
        mock_response(
            400,
            {},
            "Cannot create metadata"
        )
    ]

    session.get.side_effect = [
        mock_response(
            200,
            {
                "indexing_status": "completed"
            }
        ),
        mock_response(
            200,
            {
                "doc_metadata": []
            }
        )
    ]

    monkeypatch.setattr(
        kb_service.requests,
        "Session",
        lambda: session
    )

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b"hello"
        )

    assert "Could not create user_id metadata field" in str(exc.value)

    session.close.assert_called_once()


def test_upload_metadata_update_error(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    session = MagicMock()

    session.post.side_effect = [
        mock_response(
            201,
            {
                "document": {
                    "id": "doc-123"
                }
            }
        ),
        mock_response(
            500,
            {},
            "Metadata update failed"
        )
    ]

    session.get.side_effect = [
        mock_response(
            200,
            {
                "indexing_status": "completed"
            }
        ),
        mock_response(
            200,
            {
                "doc_metadata": [
                    {
                        "id": "metadata-123",
                        "name": "user_id"
                    }
                ]
            }
        )
    ]

    monkeypatch.setattr(
        kb_service.requests,
        "Session",
        lambda: session
    )

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b"hello"
        )

    assert "Could not assign user_id metadata" in str(exc.value)

    session.close.assert_called_once()


# ---------------------------------------------------------
# Metadata verification
# ---------------------------------------------------------

def test_upload_metadata_verification_http_error(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    session = MagicMock()

    valid_upload_flow(session)

    # Replace final verification GET
    session.get.side_effect = [
        mock_response(
            200,
            {
                "indexing_status": "completed"
            }
        ),
        mock_response(
            200,
            {
                "doc_metadata": [
                    {
                        "id": "metadata-123",
                        "name": "user_id"
                    }
                ]
            }
        ),
        mock_response(
            500,
            {},
            "Verification failed"
        )
    ]

    monkeypatch.setattr(
        kb_service.requests,
        "Session",
        lambda: session
    )

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b"hello"
        )

    assert "Could not verify document metadata" in str(exc.value)

    session.close.assert_called_once()


def test_upload_metadata_verification_invalid_json(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    session = MagicMock()

    session.post.side_effect = [
        mock_response(
            201,
            {
                "document": {
                    "id": "doc-123"
                }
            }
        ),
        mock_response(200, {})
    ]

    invalid_response = mock_response(200)
    invalid_response.json.side_effect = ValueError()

    session.get.side_effect = [
        mock_response(
            200,
            {
                "indexing_status": "completed"
            }
        ),
        mock_response(
            200,
            {
                "doc_metadata": [
                    {
                        "id": "metadata-123",
                        "name": "user_id"
                    }
                ]
            }
        ),
        invalid_response
    ]

    monkeypatch.setattr(
        kb_service.requests,
        "Session",
        lambda: session
    )

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b"hello"
        )

    assert str(exc.value) == (
        "Dify returned invalid JSON during metadata verification"
    )

    session.close.assert_called_once()


def test_upload_wrong_user_id_metadata(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    session = MagicMock()

    session.post.side_effect = [
        mock_response(
            201,
            {
                "document": {
                    "id": "doc-123"
                }
            }
        ),
        mock_response(200, {})
    ]

    session.get.side_effect = [
        mock_response(
            200,
            {
                "indexing_status": "completed"
            }
        ),
        mock_response(
            200,
            {
                "doc_metadata": [
                    {
                        "id": "metadata-123",
                        "name": "user_id"
                    }
                ]
            }
        ),
        mock_response(
            200,
            {
                "indexing_status": "completed",
                "doc_metadata": [
                    {
                        "id": "metadata-123",
                        "name": "user_id",
                        "value": "999"
                    }
                ]
            }
        )
    ]

    monkeypatch.setattr(
        kb_service.requests,
        "Session",
        lambda: session
    )

    with pytest.raises(Exception) as exc:
        kb_service.upload_document_to_kb(
            "123",
            "test.txt",
            b"hello"
        )

    assert str(exc.value) == "user_id metadata verification failed"

    session.close.assert_called_once()


# ---------------------------------------------------------
# Delete document
# ---------------------------------------------------------

def test_delete_missing_api_key(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", None)

    with pytest.raises(ValueError) as exc:
        kb_service.delete_document_from_kb("doc-123")

    assert str(exc.value) == "DIFY_KB_API_KEY is not configured"


def test_delete_missing_dataset_id(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", None)

    with pytest.raises(ValueError) as exc:
        kb_service.delete_document_from_kb("doc-123")

    assert str(exc.value) == "DIFY_KB_DATASET_ID is not configured"


def test_delete_missing_document_id(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    with pytest.raises(ValueError) as exc:
        kb_service.delete_document_from_kb("")

    assert str(exc.value) == "Document ID is required"


def test_delete_success_200(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    response = mock_response(200, {})

    delete_mock = MagicMock(return_value=response)

    monkeypatch.setattr(
        kb_service.requests,
        "delete",
        delete_mock
    )

    result = kb_service.delete_document_from_kb("doc-123")

    assert result["success"] is True
    assert result["document_id"] == "doc-123"

    delete_mock.assert_called_once()

    args, kwargs = delete_mock.call_args

    assert "doc-123" in args[0]
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["timeout"] == 30


def test_delete_success_204(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    response = mock_response(204, {})

    monkeypatch.setattr(
        kb_service.requests,
        "delete",
        MagicMock(return_value=response)
    )

    result = kb_service.delete_document_from_kb("doc-123")

    assert result["success"] is True
    assert result["document_id"] == "doc-123"


def test_delete_http_error(monkeypatch):
    monkeypatch.setattr(kb_service, "DIFY_KB_API_KEY", "test-key")
    monkeypatch.setattr(kb_service, "DIFY_KB_DATASET_ID", "dataset-123")

    response = mock_response(
        404,
        {},
        "Document not found"
    )

    monkeypatch.setattr(
        kb_service.requests,
        "delete",
        MagicMock(return_value=response)
    )

    with pytest.raises(RuntimeError) as exc:
        kb_service.delete_document_from_kb("doc-123")

    assert "Failed to delete Dify document" in str(exc.value)
    assert "404" in str(exc.value)
    assert "Document not found" in str(exc.value)
