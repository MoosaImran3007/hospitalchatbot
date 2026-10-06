
from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import get_current_user
from models.assessment import AssessmentReportRequest
from services.assessment_service import generate_assessment_report


router = APIRouter()


# ============================================================
# GENERATE ASSESSMENT REPORT
# ============================================================

@router.post("/assessment/report")
def generate_report(
    request: AssessmentReportRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate an assessment report for the authenticated user.

    user_id comes from the JWT.
    The client cannot provide another user's ID.
    """

    user_id = current_user["id"]

    questions_and_answers = request.questions_and_answers

    if not questions_and_answers:
        raise HTTPException(
            status_code=400,
            detail="questions_and_answers cannot be empty"
        )

    try:
        result = generate_assessment_report(
            user_id=str(user_id),
            questions_and_answers=questions_and_answers
        )

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Assessment report generation failed",
                "error": str(e)
            }
        )

    return {
        "success": True,
        "user_id": str(user_id),
        "report": result["report"],
        "workflow_run_id": result["workflow_run_id"]
    }
