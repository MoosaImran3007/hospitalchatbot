from pydantic import BaseModel


# ============================================================
# QUESTIONNAIRE OPTION
# ============================================================

class QuestionnaireOption(BaseModel):
    id: str
    option_text: str
    display_order: int


# ============================================================
# QUESTIONNAIRE QUESTION
# ============================================================

class QuestionnaireQuestion(BaseModel):
    id: str
    question_text: str
    question_type: str
    display_order: int
    options: list[QuestionnaireOption]


# ============================================================
# QUESTIONNAIRE RESPONSE
# ============================================================

class QuestionnaireResponse(BaseModel):
    id: str
    title: str
    version: int
    questions: list[QuestionnaireQuestion]


# ============================================================
# QUESTIONNAIRE ANSWER
# ============================================================

class QuestionnaireAnswer(BaseModel):
    question_id: str
    answer: str


# ============================================================
# QUESTIONNAIRE SUBMISSION
# ============================================================

class QuestionnaireSubmitRequest(BaseModel):
    questionnaire_id: str
    answers: list[QuestionnaireAnswer]