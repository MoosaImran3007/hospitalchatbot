from dotenv import load_dotenv
from fastapi import FastAPI

from routes.chat import router as chat_router
from routes.memory import router as memory_router
from routes.knowledge_base import router as kb_router
from routes.assessment import router as assessment_router
from routes.history import router as history_router
from routes.auth import router as auth_router
from routes.conversations import router as conversations_router
from routes.questionnaire import router as questionnaire_router


load_dotenv()


app = FastAPI()

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(memory_router)
app.include_router(kb_router)
app.include_router(assessment_router)
app.include_router(history_router)
app.include_router(conversations_router)
app.include_router(questionnaire_router)