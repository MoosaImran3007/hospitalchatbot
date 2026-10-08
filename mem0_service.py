
import os

from dotenv import load_dotenv
from mem0 import MemoryClient


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

MEM0_API_KEY = os.getenv("MEM0_API_KEY")

if not MEM0_API_KEY:
    raise RuntimeError(
        "MEM0_API_KEY is not set"
    )


# ============================================================
# MEM0 CLIENT
# ============================================================

mem0_client = MemoryClient(
    api_key=MEM0_API_KEY
)


# ============================================================
# SEARCH MEMORY
# ============================================================

def search_memory(
    user_id: str,
    query: str,
):
    """
    Search memories belonging only to the specified user.
    """

    if not user_id:
        raise ValueError(
            "user_id is required"
        )

    if not query or not query.strip():
        raise ValueError(
            "query cannot be empty"
        )

    return mem0_client.search(
        query.strip(),
        filters={
            "user_id": str(user_id)
        },
    )


# ============================================================
# ADD MEMORY
# ============================================================

def add_memory(
    user_id: str,
    query: str,
    response: str,
):
    """
    Store a user/assistant interaction in Mem0
    under the authenticated user's ID.
    """

    if not user_id:
        raise ValueError(
            "user_id is required"
        )

    if not query or not query.strip():
        raise ValueError(
            "query cannot be empty"
        )

    if not response or not response.strip():
        raise ValueError(
            "response cannot be empty"
        )

    messages = [
        {
            "role": "user",
            "content": query.strip(),
        },
        {
            "role": "assistant",
            "content": response.strip(),
        },
    ]

    return mem0_client.add(
        messages,
        user_id=str(user_id),
    )
