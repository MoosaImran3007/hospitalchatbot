
from pydantic import BaseModel


class AssessmentReportRequest(BaseModel):
    questions_and_answers: list
