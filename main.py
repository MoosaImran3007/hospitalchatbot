from dotenv import load_dotenv
from fastapi import FastAPI

from routes.chat import router as chat_router
from routes.memory import router as memory_router
from routes.knowledge_base import router as kb_router
from routes.token import router as token_router
from routes.history import router as history_router



load_dotenv()


app = FastAPI()
app.include_router(token_router)
app.include_router(chat_router)
app.include_router(memory_router)
app.include_router(kb_router)
app.include_router(history_router)
