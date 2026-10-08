# GENERATE
# ├── successful generation                  ✅
# ├── no questionnaire answers              ✅
# ├── no assessment report                  ✅
# ├── Dify upload failure                   ✅
# ├── Dify doesn't return document ID       ✅
# └── database failure                      ✅

# UPDATE
# ├── successful update                     ✅
# ├── no existing KB document               ✅
# ├── no questionnaire answers              ✅
# ├── no assessment report                  ✅
# ├── Dify upload failure                   ✅
# ├── new document ID missing               ✅
# └── database failure                      ✅
# Tests for Knowledge Base API routes:
#
# Generate User KB File:
# 1. Successfully generates and uploads a user's assessment file
# 2. Handles missing questionnaire answers
# 3. Handles missing assessment report
# 4. Handles Dify upload failure
# 5. Handles missing Dify document ID
# 6. Handles database error during generation
#
# Update User KB File:
# 7. Successfully updates an existing KB document
# 8. Handles missing existing KB document
# 9. Handles missing questionnaire answers
# 10. Handles missing assessment report
# 11. Handles Dify upload failure
# 12. Handles missing new Dify document ID
# 13. Handles database error during update
import json
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from routes import knowledge_base as kb_route


USER = {
    "id": "123",
    "email": "test@example.com",
    "role": "user"
}


def make_db():
    db = MagicMock()
    cursor = MagicMock()

    db.cursor.return_value = cursor

    return db, cursor


# ============================================================
# GENERATE USER FILE
# ============================================================

def test_generate_user_kb_file_success(monkeypatch):

    db, cursor = make_db()

    # First query = questionnaire answers
    cursor.fetchall.return_value = [
        ("q1", "What is your age?", "25"),
        ("q2", "Do you smoke?", "No"),
    ]

    # Second query = assessment report
    cursor.fetchone.return_value = (
        "report-123",
        "submission-123",
        {"summary": "Healthy"}
    )

    monkeypatch.setattr(
        kb_route,
        "get_db",
        lambda: db
    )

    monkeypatch.setattr(
        kb_route,
        "upload_document_to_kb",
        lambda **kwargs: {
            "document_id": "dify-doc-123",
            "batch_id": "batch-123"
        }
    )

    result = kb_route.generate_user_kb_file(USER)

    assert result["success"] is True
    assert result["user_id"] == "123"
    assert result["report_id"] == "report-123"
    assert result["dify_document_id"] == "dify-doc-123"

    assert result["document"]["document_id"] == "dify-doc-123"

    db.commit.assert_called_once()

    assert cursor.execute.call_count == 3


def test_generate_user_kb_file_no_answers(monkeypatch):

    db, cursor = make_db()

    cursor.fetchall.return_value = []

    monkeypatch.setattr(
        kb_route,
        "get_db",
        lambda: db
    )

    with pytest.raises(HTTPException) as exc:

        kb_route.generate_user_kb_file(USER)

    assert exc.value.status_code == 404

    assert exc.value.detail == (
        "No questionnaire answers found for this user"
    )

    db.rollback.assert_called_once()


def test_generate_user_kb_file_no_report(monkeypatch):

    db, cursor = make_db()

    cursor.fetchall.return_value = [
        ("q1", "Question", "Answer")
    ]

    cursor.fetchone.return_value = None

    monkeypatch.setattr(
        kb_route,
        "get_db",
        lambda: db
    )

    with pytest.raises(HTTPException) as exc:

        kb_route.generate_user_kb_file(USER)

    assert exc.value.status_code == 404

    assert exc.value.detail == (
        "No assessment report found for this user"
    )

    db.rollback.assert_called_once()


def test_generate_user_kb_file_upload_failure(monkeypatch):

    db, cursor = make_db()

    cursor.fetchall.return_value = [
        ("q1", "Question", "Answer")
    ]

    cursor.fetchone.return_value = (
        "report-123",
        "submission-123",
        {"summary": "Healthy"}
    )

    monkeypatch.setattr(
        kb_route,
        "get_db",
        lambda: db
    )

    monkeypatch.setattr(
        kb_route,
        "upload_document_to_kb",
        lambda **kwargs: None
    )

    with pytest.raises(HTTPException) as exc:

        kb_route.generate_user_kb_file(USER)

    assert exc.value.status_code == 502

    assert exc.value.detail == (
        "Could not upload assessment file to Dify Knowledge Base"
    )

    db.rollback.assert_called_once()


def test_generate_user_kb_file_missing_document_id(
    monkeypatch
):

    db, cursor = make_db()

    cursor.fetchall.return_value = [
        ("q1", "Question", "Answer")
    ]

    cursor.fetchone.return_value = (
        "report-123",
        "submission-123",
        {"summary": "Healthy"}
    )

    monkeypatch.setattr(
        kb_route,
        "get_db",
        lambda: db
    )

    monkeypatch.setattr(
        kb_route,
        "upload_document_to_kb",
        lambda **kwargs: {
            "batch_id": "batch-123"
        }
    )

    with pytest.raises(HTTPException) as exc:

        kb_route.generate_user_kb_file(USER)

    assert exc.value.status_code == 502

    assert exc.value.detail == (
        "Dify did not return a document ID"
    )

    db.rollback.assert_called_once()


def test_generate_user_kb_file_database_error(
    monkeypatch
):

    db, cursor = make_db()

    cursor.fetchall.side_effect = Exception(
        "Database connection failed"
    )

    monkeypatch.setattr(
        kb_route,
        "get_db",
        lambda: db
    )

    with pytest.raises(HTTPException) as exc:

        kb_route.generate_user_kb_file(USER)

    assert exc.value.status_code == 500

    assert exc.value.detail["message"] == (
        "Could not generate user assessment file"
    )

    assert (
        exc.value.detail["error"]
        == "Database connection failed"
    )

    db.rollback.assert_called_once()


# ============================================================
# UPDATE USER FILE
# ============================================================

def test_update_user_kb_file_success(monkeypatch):

    db, cursor = make_db()

    # First fetch = old Dify document
    # Second fetch = assessment report
    cursor.fetchone.side_effect = [
        ("old-dify-doc",),
        (
            "report-123",
            "submission-123",
            {"summary": "Updated report"}
        )
    ]

    cursor.fetchall.return_value = [
        ("q1", "Question 1", "Answer 1"),
        ("q2", "Question 2", "Answer 2"),
    ]

    monkeypatch.setattr(
        kb_route,
        "get_db",
        lambda: db
    )

    monkeypatch.setattr(
        kb_route,
        "delete_document_from_kb",
        lambda document_id: {
            "success": True,
            "document_id": document_id
        }
    )

    monkeypatch.setattr(
        kb_route,
        "upload_document_to_kb",
        lambda **kwargs: {
            "document_id": "new-dify-doc"
        }
    )

    result = kb_route.update_user_kb_file(USER)

    assert result["success"] is True
    assert result["user_id"] == "123"
    assert result["report_id"] == "report-123"
    assert result["old_document_id"] == "old-dify-doc"
    assert result["new_document_id"] == "new-dify-doc"

    assert result["deleted_old_document"]["success"] is True

    db.commit.assert_called_once()

    assert cursor.execute.call_count == 4


def test_update_user_kb_file_no_existing_document(
    monkeypatch
):

    db, cursor = make_db()

    cursor.fetchone.return_value = None

    monkeypatch.setattr(
        kb_route,
        "get_db",
        lambda: db
    )

    with pytest.raises(HTTPException) as exc:

        kb_route.update_user_kb_file(USER)

    assert exc.value.status_code == 404

    assert exc.value.detail == (
        "No existing KB document found for this user"
    )

    db.rollback.assert_called_once()


def test_update_user_kb_file_no_answers(monkeypatch):

    db, cursor = make_db()

    cursor.fetchone.return_value = ("old-dify-doc",)

    cursor.fetchall.return_value = []

    monkeypatch.setattr(
        kb_route,
        "get_db",
        lambda: db
    )

    monkeypatch.setattr(
        kb_route,
        "delete_document_from_kb",
        lambda document_id: {
            "success": True
        }
    )

    with pytest.raises(HTTPException) as exc:

        kb_route.update_user_kb_file(USER)

    assert exc.value.status_code == 404

    assert exc.value.detail == (
        "No questionnaire answers found for this user"
    )

    db.rollback.assert_called_once()


def test_update_user_kb_file_no_report(monkeypatch):

    db, cursor = make_db()

    cursor.fetchone.side_effect = [
        ("old-dify-doc",),
        None
    ]

    cursor.fetchall.return_value = [
        ("q1", "Question", "Answer")
    ]

    monkeypatch.setattr(
        kb_route,
        "get_db",
        lambda: db
    )

    monkeypatch.setattr(
        kb_route,
        "delete_document_from_kb",
        lambda document_id: {
            "success": True
        }
    )

    with pytest.raises(HTTPException) as exc:

        kb_route.update_user_kb_file(USER)

    assert exc.value.status_code == 404

    assert exc.value.detail == (
        "No assessment report found for this user"
    )

    db.rollback.assert_called_once()


def test_update_user_kb_file_upload_failure(
    monkeypatch
):

    db, cursor = make_db()

    cursor.fetchone.side_effect = [
        ("old-dify-doc",),
        (
            "report-123",
            "submission-123",
            {"summary": "Report"}
        )
    ]

    cursor.fetchall.return_value = [
        ("q1", "Question", "Answer")
    ]

    monkeypatch.setattr(
        kb_route,
        "get_db",
        lambda: db
    )

    monkeypatch.setattr(
        kb_route,
        "delete_document_from_kb",
        lambda document_id: {
            "success": True
        }
    )

    monkeypatch.setattr(
        kb_route,
        "upload_document_to_kb",
        lambda **kwargs: None
    )

    with pytest.raises(HTTPException) as exc:

        kb_route.update_user_kb_file(USER)

    assert exc.value.status_code == 502

    assert exc.value.detail == (
        "Could not upload updated assessment file to Dify"
    )

    db.rollback.assert_called_once()


def test_update_user_kb_file_missing_new_document_id(
    monkeypatch
):

    db, cursor = make_db()

    cursor.fetchone.side_effect = [
        ("old-dify-doc",),
        (
            "report-123",
            "submission-123",
            {"summary": "Report"}
        )
    ]

    cursor.fetchall.return_value = [
        ("q1", "Question", "Answer")
    ]

    monkeypatch.setattr(
        kb_route,
        "get_db",
        lambda: db
    )

    monkeypatch.setattr(
        kb_route,
        "delete_document_from_kb",
        lambda document_id: {
            "success": True
        }
    )

    monkeypatch.setattr(
        kb_route,
        "upload_document_to_kb",
        lambda **kwargs: {
            "batch_id": "batch-123"
        }
    )

    with pytest.raises(HTTPException) as exc:

        kb_route.update_user_kb_file(USER)

    assert exc.value.status_code == 502

    assert exc.value.detail == (
        "Dify did not return a document ID"
    )

    db.rollback.assert_called_once()


def test_update_user_kb_file_database_error(
    monkeypatch
):

    db, cursor = make_db()

    cursor.fetchone.side_effect = Exception(
        "Database connection failed"
    )

    monkeypatch.setattr(
        kb_route,
        "get_db",
        lambda: db
    )

    with pytest.raises(HTTPException) as exc:

        kb_route.update_user_kb_file(USER)

    assert exc.value.status_code == 500

    assert exc.value.detail["message"] == (
        "Could not update user assessment KB document"
    )

    assert (
        exc.value.detail["error"]
        == "Database connection failed"
    )

    db.rollback.assert_called_once()