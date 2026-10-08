import json

from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import get_current_user
from database import get_db
from services.kb_service import upload_document_to_kb,delete_document_from_kb

router = APIRouter()

@router.post("/kb/generate-user-file")
def generate_user_kb_file(
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]

    db = get_db()
    cursor = db.cursor()

    try:
        # 1. Get user's questions + answers
        cursor.execute(
            """
            SELECT
                qa.question_id,
                q.question_text,
                qa.answer
            FROM questionnaire_answers qa
            JOIN questions q
                ON q.id = qa.question_id
            WHERE qa.user_id = %s
            ORDER BY q.display_order ASC
            """,
            (user_id,)
        )

        answers = cursor.fetchall()

        if not answers:
            raise HTTPException(
                status_code=404,
                detail="No questionnaire answers found for this user"
            )

        questions_and_answers = [
            {
                "question_id": str(row[0]),
                "question": row[1],
                "answer": row[2]
            }
            for row in answers
        ]

        # 2. Get user's assessment report
        cursor.execute(
            """
            SELECT
                id,
                submission_id,
                report
            FROM assessment_reports
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,)
        )

        report_row = cursor.fetchone()

        if not report_row:
            raise HTTPException(
                status_code=404,
                detail="No assessment report found for this user"
            )

        report_id = str(report_row[0])
        submission_id = str(report_row[1])
        report_data = report_row[2]

        # 3. Create the document
        assessment_document = {
            "user_id": str(user_id),
            "submission_id": submission_id,
            "questions_and_answers": questions_and_answers,
            "assessment_report": report_data
        }

        # 4. Convert document to text
        assessment_content = json.dumps(
            assessment_document,
            indent=2,
            ensure_ascii=False
        ).encode("utf-8")

        filename = f"assessment_{user_id}.txt"

        # 5. Upload to Dify Knowledge Base
        kb_result = upload_document_to_kb(
            user_id=user_id,
            filename=filename,
            file_content=assessment_content,
            content_type="text/plain"
        )

        if not kb_result:
            raise HTTPException(
                status_code=502,
                detail="Could not upload assessment file to Dify Knowledge Base"
            )

        # 6. Get Dify document ID
        dify_document_id = kb_result.get("document_id")

        if not dify_document_id:
            raise HTTPException(
                status_code=502,
                detail="Dify did not return a document ID"
            )

        # 7. Save Dify document ID in PostgreSQL
        cursor.execute(
            """
            INSERT INTO user_kb_documents (
                user_id,
                dify_document_id,
                filename
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id)
            DO UPDATE SET
                dify_document_id = EXCLUDED.dify_document_id,
                filename = EXCLUDED.filename,
                updated_at = NOW()
            """,
            (
                user_id,
                dify_document_id,
                filename
            )
        )

        db.commit()

        # 8. Return result
        return {
            "success": True,
            "message": "User assessment file uploaded successfully",
            "user_id": str(user_id),
            "report_id": report_id,
            "dify_document_id": dify_document_id,
            "document": kb_result
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Could not generate user assessment file",
                "error": str(e)
            }
        )

    finally:
        cursor.close()
        db.close()
@router.put("/kb/update-user-file")
def update_user_kb_file(
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]

    db = get_db()
    cursor = db.cursor()

    try:
        # 1. Get the existing Dify document ID
        cursor.execute(
            """
            SELECT dify_document_id
            FROM user_kb_documents
            WHERE user_id = %s
            """,
            (user_id,)
        )

        old_document_row = cursor.fetchone()

        if not old_document_row:
            raise HTTPException(
                status_code=404,
                detail="No existing KB document found for this user"
            )

        old_document_id = old_document_row[0]

        # 2. Delete the existing document from Dify
        delete_result = delete_document_from_kb(old_document_id)

        # 3. Get user's questions + answers
        cursor.execute(
            """
            SELECT
                qa.question_id,
                q.question_text,
                qa.answer
            FROM questionnaire_answers qa
            JOIN questions q
                ON q.id = qa.question_id
            WHERE qa.user_id = %s
            ORDER BY q.display_order ASC
            """,
            (user_id,)
        )

        answers = cursor.fetchall()

        if not answers:
            raise HTTPException(
                status_code=404,
                detail="No questionnaire answers found for this user"
            )

        questions_and_answers = [
            {
                "question_id": str(row[0]),
                "question": row[1],
                "answer": row[2]
            }
            for row in answers
        ]

        # 4. Get latest assessment report
        cursor.execute(
            """
            SELECT
                id,
                submission_id,
                report
            FROM assessment_reports
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,)
        )

        report_row = cursor.fetchone()

        if not report_row:
            raise HTTPException(
                status_code=404,
                detail="No assessment report found for this user"
            )

        report_id = str(report_row[0])
        submission_id = str(report_row[1])
        report_data = report_row[2]

        # 5. Create the new assessment document
        assessment_document = {
            "user_id": str(user_id),
            "submission_id": submission_id,
            "questions_and_answers": questions_and_answers,
            "assessment_report": report_data
        }

        # 6. Convert document to bytes
        assessment_content = json.dumps(
            assessment_document,
            indent=2,
            ensure_ascii=False
        ).encode("utf-8")

        filename = f"assessment_{user_id}.txt"

        # 7. Upload NEW document to Dify
        kb_result = upload_document_to_kb(
            user_id=user_id,
            filename=filename,
            file_content=assessment_content,
            content_type="text/plain"
        )

        if not kb_result:
            raise HTTPException(
                status_code=502,
                detail="Could not upload updated assessment file to Dify"
            )

        # 8. Get NEW Dify document ID
        new_document_id = kb_result.get("document_id")

        if not new_document_id:
            raise HTTPException(
                status_code=502,
                detail="Dify did not return a document ID"
            )

        # 9. Update PostgreSQL with NEW document ID
        cursor.execute(
            """
            UPDATE user_kb_documents
            SET
                dify_document_id = %s,
                filename = %s,
                updated_at = NOW()
            WHERE user_id = %s
            """,
            (
                new_document_id,
                filename,
                user_id
            )
        )

        db.commit()

        # 10. Return result
        return {
            "success": True,
            "message": "User assessment KB document updated successfully",
            "user_id": str(user_id),
            "report_id": report_id,
            "old_document_id": old_document_id,
            "new_document_id": new_document_id,
            "deleted_old_document": delete_result
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Could not update user assessment KB document",
                "error": str(e)
            }
        )

    finally:
        cursor.close()
        db.close()