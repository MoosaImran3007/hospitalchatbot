
import requests

from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import get_current_user
from config import DIFY_API_KEY
from database import get_db


router = APIRouter()


# ============================================================
# GET CHAT HISTORY
# ============================================================

@router.get("/chat/history/{conversation_id}")
def get_chat_history(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get the complete Dify chat history for a conversation.

    Security:
    - user_id comes from the JWT.
    - The client cannot provide another user's user_id.
    - PostgreSQL verifies conversation ownership before Dify
      is contacted.
    """

    user_id = current_user["id"]
    conversation_id = conversation_id.strip()

    if not conversation_id:
        raise HTTPException(
            status_code=400,
            detail="conversation_id is required"
        )

    # ========================================================
    # VERIFY CONVERSATION OWNERSHIP
    # ========================================================

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            """
            SELECT id
            FROM conversations
            WHERE user_id = %s
            AND conversation_id = %s
            """,
            (
                user_id,
                conversation_id
            )
        )

        conversation = cursor.fetchone()

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()

    if not conversation:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this conversation"
        )

    # ========================================================
    # VALIDATE DIFY CONFIGURATION
    # ========================================================

    if not DIFY_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="DIFY_API_KEY is not configured"
        )

    # ========================================================
    # GET COMPLETE HISTORY FROM DIFY
    # ========================================================

    all_messages = []
    first_id = None

    try:

        while True:

            params = {
                "user": str(user_id),
                "conversation_id": conversation_id,
                "limit": 100,
            }

            if first_id:
                params["first_id"] = first_id

            response = requests.get(
                "https://api.dify.ai/v1/messages",
                headers={
                    "Authorization": f"Bearer {DIFY_API_KEY}",
                },
                params=params,
                timeout=60,
            )

            # ------------------------------------------------
            # DIFY HTTP ERROR
            # ------------------------------------------------

            if response.status_code != 200:

                try:
                    error_response = response.json()
                except ValueError:
                    error_response = {
                        "message": response.text
                    }

                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": "Dify history request failed",
                        "status": response.status_code,
                        "response": error_response,
                    },
                )

            # ------------------------------------------------
            # PARSE JSON
            # ------------------------------------------------

            try:
                data = response.json()

            except ValueError:

                raise HTTPException(
                    status_code=502,
                    detail="Dify returned invalid JSON"
                )

            # ------------------------------------------------
            # GET MESSAGES
            # ------------------------------------------------

            messages = data.get("data", [])

            if not isinstance(messages, list):
                raise HTTPException(
                    status_code=502,
                    detail="Dify returned invalid message data"
                )

            all_messages.extend(messages)

            # ------------------------------------------------
            # PAGINATION
            # ------------------------------------------------

            if not data.get("has_more"):
                break

            if not messages:
                break

            next_first_id = messages[-1].get("id")

            if not next_first_id:
                break

            # Safety check against infinite pagination loop
            if next_first_id == first_id:
                break

            first_id = next_first_id

    except requests.Timeout:

        raise HTTPException(
            status_code=504,
            detail="Dify history request timed out"
        )

    except requests.RequestException as e:

        raise HTTPException(
            status_code=502,
            detail={
                "message": "Could not connect to Dify",
                "error": str(e),
            },
        )

    # ========================================================
    # FORMAT HISTORY
    # ========================================================

    formatted_messages = [
        {
            "query": message.get("query"),
            "response": message.get("answer"),
        }
        for message in all_messages
    ]

    # ========================================================
    # RETURN HISTORY
    # ========================================================

    return {
        "success": True,
        "user_id": str(user_id),
        "conversation_id": conversation_id,
        "message_count": len(formatted_messages),
        "messages": formatted_messages,
    }
