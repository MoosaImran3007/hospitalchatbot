
from fastapi import APIRouter, Depends, HTTPException
import requests

from database import get_db
from auth.dependencies import get_current_user
from models.conversation import SaveConversationRequest
from config import DIFY_API_KEY


router = APIRouter(prefix="/conversations")


# ============================================================
# GET MY CONVERSATIONS
# ============================================================

@router.get("")
def get_my_conversations(
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            """
            SELECT
                id,
                conversation_id,
                created_at,
                updated_at
            FROM conversations
            WHERE user_id = %s
            ORDER BY updated_at DESC
            """,
            (user_id,)
        )

        conversations = cursor.fetchall()

        return {
            "success": True,
            "conversations": [
                {
                    "id": str(row[0]),
                    "conversation_id": row[1],
                    "created_at": row[2],
                    "updated_at": row[3]
                }
                for row in conversations
            ]
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()


# ============================================================
# SAVE CONVERSATION
# ============================================================

@router.post("")
def save_conversation(
    request: SaveConversationRequest,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    conversation_id = request.conversation_id.strip()

    if not conversation_id:
        raise HTTPException(
            status_code=400,
            detail="conversation_id is required"
        )

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO conversations (
                user_id,
                conversation_id
            )
            VALUES (%s, %s)
            ON CONFLICT (user_id, conversation_id)
            DO UPDATE SET updated_at = NOW()
            RETURNING
                id,
                conversation_id,
                created_at,
                updated_at
            """,
            (
                user_id,
                conversation_id
            )
        )

        conversation = cursor.fetchone()

        db.commit()

        return {
            "success": True,
            "message": "Conversation saved successfully",
            "conversation": {
                "id": str(conversation[0]),
                "conversation_id": conversation[1],
                "created_at": conversation[2],
                "updated_at": conversation[3]
            }
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()
        db.close()

