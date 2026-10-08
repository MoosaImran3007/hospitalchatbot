import os

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Header

from models.memory import MemorySearchRequest
from mem0_service import search_memory


load_dotenv()

router = APIRouter()

DIFY_INTERNAL_API_KEY = os.getenv("DIFY_INTERNAL_API_KEY")


# ============================================================
# SEARCH USER MEMORIES
# ============================================================

@router.post("/mem0/search")
def mem0_search(
    request: MemorySearchRequest,
    x_internal_api_key: str | None = Header(default=None)
):
    """
    Internal endpoint used by the Dify workflow.

    Dify authenticates using the internal API key.
    The user_id comes from the trusted Dify workflow input.
    """

    # ========================================================
    # 1. Validate internal Dify authentication
    # ========================================================

    if not DIFY_INTERNAL_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="DIFY_INTERNAL_API_KEY is not configured"
        )

    if x_internal_api_key != DIFY_INTERNAL_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid internal API key"
        )

    # ========================================================
    # 2. Get user ID from Dify request
    # ========================================================

    user_id = request.user_id

    query = request.query.strip()

    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="user_id is required"
        )

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty"
        )

    print("\n" + "=" * 70)
    print("MEM0 SEARCH REQUEST")
    print("=" * 70)
    print("USER ID:", user_id)
    print("QUERY:", query)

    # ========================================================
    # 3. Search Mem0 for THIS user
    # ========================================================

    try:

        result = search_memory(
            user_id=str(user_id),
            query=query,
        )

        print("\nMEM0 SEARCH COMPLETE")
        print(result)

    except Exception as e:

        print("\nMEM0 SEARCH FAILED")
        print(str(e))

        raise HTTPException(
            status_code=502,
            detail={
                "message": "Mem0 search failed",
                "error": str(e),
            },
        )

    # ========================================================
    # 4. Extract memories
    # ========================================================

    memories = []

    if isinstance(result, dict):

        for item in result.get("results", []):

            if isinstance(item, dict):

                memory = item.get("memory")

                if memory:
                    memories.append(memory)

    # ========================================================
    # 5. Response
    # ========================================================

    return {
        "success": True,
        "user_id": str(user_id),
        "query": query,
        "memories": memories,
    }