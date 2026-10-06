
import json
import requests

from mem0_service import add_memory
from database import get_db
from config import DIFY_API_KEY, DIFY_API_URL


def stream_chat(request, current_user):
    """
    Stream a chat response from Dify.

    Security:
    - User ID always comes from the JWT.
    - Existing conversations must belong to the current user.
    - New conversations are automatically saved after Dify creates them.
    - Client cannot choose another user's user_id.
    """

    # =========================================================
    # USER ID FROM JWT
    # =========================================================

    user_id = current_user["id"]

    conversation_id = request.conversation_id
    is_new_chat = conversation_id is None

    # =========================================================
    # VALIDATE CONFIGURATION
    # =========================================================

    if not DIFY_API_KEY:
        def config_error_stream():
            yield (
                "event: error\n"
                f"data: {json.dumps({
                    'message': 'DIFY_API_KEY is not configured'
                })}\n\n"
            )

        return config_error_stream()

    if not DIFY_API_URL:
        def config_url_error_stream():
            yield (
                "event: error\n"
                f"data: {json.dumps({
                    'message': 'DIFY_API_URL is not configured'
                })}\n\n"
            )

        return config_url_error_stream()

    # =========================================================
    # VALIDATE QUERY
    # =========================================================

    if not request.query or not request.query.strip():
        def empty_query_stream():
            yield (
                "event: error\n"
                f"data: {json.dumps({
                    'message': 'Query cannot be empty'
                })}\n\n"
            )

        return empty_query_stream()

    # =========================================================
    # EXISTING CHAT SECURITY CHECK
    # =========================================================

    if not is_new_chat:

        conversation_id = conversation_id.strip()

        if not conversation_id:
            def empty_conversation_stream():
                yield (
                    "event: error\n"
                    f"data: {json.dumps({
                        'message': 'conversation_id cannot be empty'
                    })}\n\n"
                )

            return empty_conversation_stream()

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
            cursor.close()
            db.close()
            raise

        finally:
            try:
                cursor.close()
            except Exception:
                pass

            try:
                db.close()
            except Exception:
                pass

        # -----------------------------------------------------
        # Conversation does not belong to current user
        # -----------------------------------------------------

        if not conversation:

            def unauthorized_stream():
                yield (
                    "event: error\n"
                    f"data: {json.dumps({
                        'message': 'You do not have access to this conversation'
                    })}\n\n"
                )

            return unauthorized_stream()

    # =========================================================
    # DIFY PAYLOAD
    # =========================================================

    payload = {
        "inputs": {
            "user_id": str(user_id),
            "is_new_chat": is_new_chat,
            "conversation_id": conversation_id or "",
        },
        "query": request.query.strip(),
        "response_mode": "streaming",
        "user": str(user_id),
    }

    # Existing conversation
    if not is_new_chat:
        payload["conversation_id"] = conversation_id

    # =========================================================
    # STREAM GENERATOR
    # =========================================================

    def generate():

        full_answer = []

        # For a new chat this will be populated by Dify.
        # For an existing chat it already contains the ID.
        current_conversation_id = conversation_id

        dify_response = None

        try:

            # =================================================
            # SEND REQUEST TO DIFY
            # =================================================

            dify_response = requests.post(
                DIFY_API_URL,
                headers={
                    "Authorization": f"Bearer {DIFY_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                stream=True,
                timeout=120,
            )

            # =================================================
            # DIFY HTTP ERROR
            # =================================================

            if dify_response.status_code != 200:

                try:
                    error_response = dify_response.json()
                except ValueError:
                    error_response = {
                        "message": dify_response.text
                    }

                yield (
                    "event: error\n"
                    f"data: {json.dumps({
                        'message': 'Dify returned an error',
                        'status': dify_response.status_code,
                        'response': error_response
                    })}\n\n"
                )

                return

            # =================================================
            # READ DIFY STREAM
            # =================================================

            for line in dify_response.iter_lines(
                decode_unicode=True
            ):

                if not line:
                    continue

                if not line.startswith("data:"):
                    continue

                data_text = line[5:].strip()

                if not data_text:
                    continue

                try:
                    dify_data = json.loads(data_text)

                except json.JSONDecodeError:
                    # Ignore malformed/non-JSON stream chunks
                    continue

                event = dify_data.get("event")

                # =================================================
                # GET CONVERSATION ID
                # =================================================

                dify_conversation_id = dify_data.get(
                    "conversation_id"
                )

                if dify_conversation_id:
                    current_conversation_id = (
                        dify_conversation_id
                    )

                # =================================================
                # MESSAGE CHUNK
                # =================================================

                if event == "message":

                    chunk = dify_data.get(
                        "answer",
                        ""
                    )

                    if chunk:

                        full_answer.append(chunk)

                        yield (
                            "event: message\n"
                            f"data: {json.dumps({
                                'content': chunk
                            })}\n\n"
                        )

                # =================================================
                # MESSAGE COMPLETE
                # =================================================

                elif event == "message_end":

                    answer = "".join(full_answer)

                    # =============================================
                    # SAVE NEW CONVERSATION
                    # =============================================

                    if (
                        is_new_chat
                        and current_conversation_id
                    ):

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
                                ON CONFLICT (
                                    user_id,
                                    conversation_id
                                )
                                DO UPDATE SET
                                    updated_at = NOW()
                                """,
                                (
                                    user_id,
                                    current_conversation_id
                                )
                            )

                            db.commit()

                        except Exception as e:

                            db.rollback()

                            print(
                                "CONVERSATION SAVE FAILED:",
                                str(e)
                            )

                        finally:

                            cursor.close()
                            db.close()

                    # =============================================
                    # UPDATE EXISTING CONVERSATION TIMESTAMP
                    # =============================================

                    elif current_conversation_id:

                        db = get_db()
                        cursor = db.cursor()

                        try:

                            cursor.execute(
                                """
                                UPDATE conversations
                                SET updated_at = NOW()
                                WHERE user_id = %s
                                AND conversation_id = %s
                                """,
                                (
                                    user_id,
                                    current_conversation_id
                                )
                            )

                            db.commit()

                        except Exception as e:

                            db.rollback()

                            print(
                                "CONVERSATION UPDATE FAILED:",
                                str(e)
                            )

                        finally:

                            cursor.close()
                            db.close()

                    # =============================================
                    # SAVE MEMORY TO MEM0
                    # =============================================

                    memory_saved = False

                    if answer.strip():

                        try:

                            add_memory(
                                user_id=str(user_id),
                                query=request.query.strip(),
                                response=answer,
                            )

                            memory_saved = True

                        except Exception as e:

                            print(
                                "MEM0 SAVE FAILED:",
                                str(e)
                            )

                    # =============================================
                    # SEND COMPLETE EVENT
                    # =============================================

                    yield (
                        "event: done\n"
                        f"data: {json.dumps({
                            'success': True,
                            'user_id': str(user_id),
                            'conversation_id': current_conversation_id,
                            'memory_saved': memory_saved
                        })}\n\n"
                    )

                    break

                # =================================================
                # DIFY ERROR EVENT
                # =================================================

                elif event == "error":

                    yield (
                        "event: error\n"
                        f"data: {json.dumps({
                            'error': dify_data
                        })}\n\n"
                    )

                    break

        except requests.Timeout:

            yield (
                "event: error\n"
                f"data: {json.dumps({
                    'message': 'Dify request timed out'
                })}\n\n"
            )

        except requests.RequestException as e:

            yield (
                "event: error\n"
                f"data: {json.dumps({
                    'message': 'Could not connect to Dify',
                    'error': str(e)
                })}\n\n"
            )

        except Exception as e:

            print(
                "CHAT STREAM ERROR:",
                str(e)
            )

            yield (
                "event: error\n"
                f"data: {json.dumps({
                    'message': 'An unexpected error occurred',
                    'error': str(e)
                })}\n\n"
            )

        finally:

            if dify_response is not None:

                try:
                    dify_response.close()
                except Exception:
                    pass

    return generate()
