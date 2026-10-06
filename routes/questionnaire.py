import json

from fastapi import APIRouter, Depends, HTTPException

from database import get_db
from auth.dependencies import get_current_user

from models.questionnaire import QuestionnaireSubmitRequest

from services.assessment_service import (
    generate_assessment_report
)

from services.kb_service import (
    upload_document_to_kb
)


router = APIRouter(
    prefix="/questionnaire"
)


# ============================================================
# QUESTIONNAIRE STATUS
# ============================================================

@router.get("/status")
def get_questionnaire_status(
    current_user: dict = Depends(get_current_user)
):
    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute(
            """
            SELECT
                completed,
                completed_at
            FROM questionnaire_submissions
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (current_user["id"],)
        )

        submission = cursor.fetchone()

        if not submission:
            return {
                "success": True,
                "completed": False,
                "completed_at": None
            }

        return {
            "success": True,
            "completed": submission[0],
            "completed_at": submission[1]
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# GET ACTIVE QUESTIONNAIRE
# ============================================================

@router.get("")
def get_questionnaire(
    current_user: dict = Depends(get_current_user)
):
    db = get_db()
    cursor = db.cursor()

    try:

        # ----------------------------------------------------
        # Get active questionnaire
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                title,
                version
            FROM questionnaires
            WHERE is_active = TRUE
            ORDER BY version DESC
            LIMIT 1
            """
        )

        questionnaire = cursor.fetchone()

        if not questionnaire:
            raise HTTPException(
                status_code=404,
                detail="No active questionnaire found"
            )

        questionnaire_id = questionnaire[0]

        # ----------------------------------------------------
        # Get questions + options
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                q.id,
                q.question_text,
                q.question_type,
                q.display_order,

                qo.id,
                qo.option_text,
                qo.display_order

            FROM questions q

            LEFT JOIN question_options qo
                ON qo.question_id = q.id

            WHERE q.questionnaire_id = %s

            ORDER BY
                q.display_order ASC,
                qo.display_order ASC
            """,
            (questionnaire_id,)
        )

        rows = cursor.fetchall()

        # ----------------------------------------------------
        # Build questions
        # ----------------------------------------------------

        questions = {}

        for row in rows:

            question_id = str(row[0])

            if question_id not in questions:

                questions[question_id] = {
                    "id": question_id,
                    "question_text": row[1],
                    "question_type": row[2],
                    "display_order": row[3],
                    "options": []
                }

            # Option exists
            if row[4] is not None:

                questions[question_id]["options"].append(
                    {
                        "id": str(row[4]),
                        "option_text": row[5],
                        "display_order": row[6]
                    }
                )

        return {
            "success": True,
            "questionnaire": {
                "id": str(questionnaire[0]),
                "title": questionnaire[1],
                "version": questionnaire[2],
                "questions": list(
                    questions.values()
                )
            }
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# SUBMIT QUESTIONNAIRE
# ============================================================

@router.post("/submit")
def submit_questionnaire(
    request: QuestionnaireSubmitRequest,
    current_user: dict = Depends(get_current_user)
):

    user_id = current_user["id"]

    db = get_db()
    cursor = db.cursor()

    try:

        # ----------------------------------------------------
        # 1. Validate questionnaire
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                title,
                version
            FROM questionnaires
            WHERE id = %s
              AND is_active = TRUE
            """,
            (request.questionnaire_id,)
        )

        questionnaire = cursor.fetchone()

        if not questionnaire:
            raise HTTPException(
                status_code=404,
                detail="Questionnaire not found or inactive"
            )

        # ----------------------------------------------------
        # 2. Check existing submission
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                completed
            FROM questionnaire_submissions
            WHERE user_id = %s
              AND questionnaire_id = %s
            """,
            (
                user_id,
                request.questionnaire_id
            )
        )

        existing_submission = cursor.fetchone()

        # Already completed
        if existing_submission and existing_submission[1]:

            raise HTTPException(
                status_code=400,
                detail="Questionnaire has already been completed"
            )

        # ----------------------------------------------------
        # 3. Get questions
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                question_text,
                question_type,
                display_order
            FROM questions
            WHERE questionnaire_id = %s
            ORDER BY display_order ASC
            """,
            (request.questionnaire_id,)
        )

        questions = cursor.fetchall()

        if not questions:

            raise HTTPException(
                status_code=400,
                detail="Questionnaire has no questions"
            )

        # ----------------------------------------------------
        # 4. Validate question IDs
        # ----------------------------------------------------

        question_ids = {
            str(question[0])
            for question in questions
        }

        submitted_question_ids = {
            str(answer.question_id)
            for answer in request.answers
        }

        # Missing
        missing_questions = (
            question_ids - submitted_question_ids
        )

        if missing_questions:

            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Some questions were not answered",
                    "missing_question_ids": list(
                        missing_questions
                    )
                }
            )

        # Invalid
        invalid_questions = (
            submitted_question_ids - question_ids
        )

        if invalid_questions:

            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Invalid question IDs submitted",
                    "invalid_question_ids": list(
                        invalid_questions
                    )
                }
            )

        # Duplicate question IDs
        if len(request.answers) != len(
            submitted_question_ids
        ):

            raise HTTPException(
                status_code=400,
                detail="Duplicate question IDs are not allowed"
            )

        # ----------------------------------------------------
        # 5. Create or reuse submission
        # ----------------------------------------------------

        if existing_submission:

            submission_id = existing_submission[0]

            # Remove previous answers if this is
            # an incomplete retry.
            cursor.execute(
                """
                DELETE FROM questionnaire_answers
                WHERE submission_id = %s
                """,
                (submission_id,)
            )

        else:

            cursor.execute(
                """
                INSERT INTO questionnaire_submissions (
                    user_id,
                    questionnaire_id,
                    completed
                )
                VALUES (%s, %s, FALSE)
                RETURNING id
                """,
                (
                    user_id,
                    request.questionnaire_id
                )
            )

            submission_id = cursor.fetchone()[0]

        # ----------------------------------------------------
        # 6. Prepare question map
        # ----------------------------------------------------

        question_map = {
            str(question[0]): {
                "question": question[1],
                "question_type": question[2]
            }
            for question in questions
        }

        # ----------------------------------------------------
        # 7. Save answers
        # ----------------------------------------------------

        for submitted_answer in request.answers:

            question_id = str(
                submitted_answer.question_id
            )

            cursor.execute(
                """
                INSERT INTO questionnaire_answers (
                    submission_id,
                    user_id,
                    question_id,
                    answer
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    submission_id,
                    user_id,
                    question_id,
                    submitted_answer.answer
                )
            )

        # ----------------------------------------------------
        # 8. Prepare Q&A for Dify
        # ----------------------------------------------------

        questions_and_answers = []

        for submitted_answer in request.answers:

            question_id = str(
                submitted_answer.question_id
            )

            questions_and_answers.append(
                {
                    "question_id": question_id,
                    "question": question_map[question_id]["question"],
                    "answer": submitted_answer.answer
                }
            )

        # ----------------------------------------------------
        # 9. Generate assessment report
        # ----------------------------------------------------

        report_result = generate_assessment_report(
            user_id=user_id,
            questions_and_answers=questions_and_answers
        )

        if not report_result:
            raise HTTPException(
                status_code=502,
                detail="Assessment report generation failed"
            )

        report_data = report_result.get("report")

        if report_data is None:
            raise HTTPException(
                status_code=502,
                detail="Assessment report was not returned"
            )

        workflow_run_id = report_result.get(
            "workflow_run_id"
        )

        # ----------------------------------------------------
        # 10. Save report in PostgreSQL
        # ----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO assessment_reports (
                user_id,
                submission_id,
                report
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (submission_id)
            DO UPDATE SET
                report = EXCLUDED.report
            RETURNING id
            """,
            (
                user_id,
                submission_id,
                json.dumps(report_data)
            )
        )

        report_id = cursor.fetchone()[0]

        # ----------------------------------------------------
        # 11. Create assessment document
        # ----------------------------------------------------

        assessment_document = {
            "user_id": user_id,
            "questionnaire_id": request.questionnaire_id,
            "submission_id": str(submission_id),
            "questions_and_answers": questions_and_answers,
            "assessment_report": report_data
        }

        # JSON content inside .txt file
        assessment_content = json.dumps(
            assessment_document,
            indent=2,
            ensure_ascii=False
        ).encode("utf-8")

        filename = (
            f"assessment_{user_id}.txt"
        )

        # ----------------------------------------------------
        # 12. Upload assessment to Dify KB
        # ----------------------------------------------------

        kb_result = upload_document_to_kb(
            user_id=user_id,
            filename=filename,
            file_content=assessment_content,
            content_type="text/plain"
        )

        if not kb_result:
            raise HTTPException(
                status_code=502,
                detail="Assessment document could not be uploaded to Dify Knowledge Base"
            )

        # ----------------------------------------------------
        # 13. Mark questionnaire completed
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE questionnaire_submissions
            SET
                completed = TRUE,
                completed_at = NOW()
            WHERE id = %s
            """,
            (submission_id,)
        )

        # ----------------------------------------------------
        # 14. Commit everything
        # ----------------------------------------------------

        db.commit()

        # ----------------------------------------------------
        # 15. Return response
        # ----------------------------------------------------

        return {
            "success": True,
            "message": "Questionnaire completed successfully",

            "submission_id": str(
                submission_id
            ),

            "report_id": str(
                report_id
            ),

            "report": report_data,

            "workflow_run_id": workflow_run_id,

            "kb": {
                "document_id": kb_result.get(
                    "document_id"
                ),

                "batch_id": kb_result.get(
                    "batch_id"
                ),

                "indexing_status": kb_result.get(
                    "indexing_status"
                ),

                "segment_count": kb_result.get(
                    "segment_count"
                )
            }
        }

    except HTTPException:

        db.rollback()
        raise

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Could not complete questionnaire",
                "error": str(e)
            }
        )

    finally:

        cursor.close()
        db.close()