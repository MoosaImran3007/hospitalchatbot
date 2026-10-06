from pydantic import BaseModel


class SaveConversationRequest(BaseModel):
    conversation_id: str