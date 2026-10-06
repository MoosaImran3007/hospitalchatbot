from pydantic import BaseModel, Field


class MemorySearchRequest(BaseModel):
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1)