import os
import json
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException,UploadFile, File, Form
from pydantic import BaseModel
from mem0_service import search_memory, add_memory
import re
from fastapi.responses import StreamingResponse
load_dotenv()

app = FastAPI()


DIFY_KB_API_KEY = os.getenv("DIFY_KB_API_KEY")
DIFY_KB_DATASET_ID = os.getenv("DIFY_KB_DATASET_ID")

if not DIFY_KB_API_KEY:
    raise RuntimeError("DIFY_KB_API_KEY is not set")

if not DIFY_KB_DATASET_ID:
    raise RuntimeError("DIFY_KB_DATASET_ID is not set")

DIFY_API_KEY = os.getenv("DIFY_API_KEY")

DIFY_API_URL = os.getenv(
    "DIFY_API_URL",
    "https://api.dify.ai/v1/chat-messages",
)

if not DIFY_API_KEY:
    raise RuntimeError("DIFY_API_KEY is not set")



class ChatRequest(BaseModel):
    user_id: str
    query: str
    conversation_id: str | None = None


class MemorySearchRequest(BaseModel):
    user_id: str

    query: str


# @app.post("/chat")
# def chat(request: ChatRequest):

#     print("\n" + "=" * 70)
#     print(" CHAT REQUEST")
#     print("=" * 70)
#     print("USER ID:", request.user_id)
#     print("QUERY:", request.query)
#     print("INCOMING CONVERSATION ID:", request.conversation_id)
#     is_new_chat = request.conversation_id is None

#     print("\nIS NEW CHAT:", is_new_chat)

#     if is_new_chat:
#         print("New chat")
#     else:
#         print(" Existing chat")
#         print("Conversation ID:", request.conversation_id)


#     payload = {
#         "inputs": {
#             "user_id": request.user_id,

#             # IMPORTANT:
#             # Dify input variable is Boolean.
#             "is_new_chat": is_new_chat,

#             # Keep the existing conversation ID available
#             # inside the workflow.
#             "conversation_id": request.conversation_id or "",
#         },

#         "query": request.query,

#         "response_mode": "blocking",

#         "user": request.user_id,
#     }


#     if not is_new_chat:

#         payload["conversation_id"] = request.conversation_id

#         print("\n Sending existing conversation to Dify:")
#         print(request.conversation_id)

#     else:

#         print("\n No conversation_id sent to Dify")
#         print("Dify will create a new conversation.")

#     # ========================================================
#     # DEBUG PAYLOAD
#     # ========================================================

#     print("\n" + "=" * 70)
#     print("DIFY REQUEST")
#     print("=" * 70)

#     print(payload)

#     # ========================================================
#     # CALL DIFY
#     # ========================================================

#     try:

#         dify_response = requests.post(
#             DIFY_API_URL,
#             headers={
#                 "Authorization": f"Bearer {DIFY_API_KEY}",
#                 "Content-Type": "application/json",
#             },
#             json=payload,
#             timeout=120,
#         )

#     except requests.RequestException as e:

#         print("\n DIFY CONNECTION ERROR")
#         print(str(e))

#         raise HTTPException(
#             status_code=502,
#             detail={
#                 "message": "Could not connect to Dify",
#                 "error": str(e),
#             },
#         )

#     # ========================================================
#     # CHECK DIFY RESPONSE
#     # ========================================================

#     if dify_response.status_code != 200:

#         print("\n DIFY ERROR")
#         print("STATUS:", dify_response.status_code)
#         print("BODY:", dify_response.text)

#         raise HTTPException(
#             status_code=502,
#             detail={
#                 "message": "Dify returned an error",
#                 "status": dify_response.status_code,
#                 "response": dify_response.text,
#             },
#         )

#     # ========================================================
#     # PARSE RESPONSE
#     # ========================================================

#     try:

#         dify_data = dify_response.json()

#     except ValueError:

#         raise HTTPException(
#             status_code=502,
#             detail="Dify returned invalid JSON",
#         )

#     # ========================================================
#     # GET CONVERSATION ID
#     # ========================================================

#     conversation_id = dify_data.get("conversation_id")

#     if not conversation_id:

#         print("\n DIFY DID NOT RETURN CONVERSATION ID")
#         print(dify_data)

#         raise HTTPException(
#             status_code=502,
#             detail="Dify did not return conversation_id",
#         )

#     # ========================================================
#     # GET ANSWER
#     # ========================================================

#     answer = dify_data.get("answer")

#     if not answer:

#         print("\n DIFY DID NOT RETURN ANSWER")
#         print(dify_data)

#         raise HTTPException(
#             status_code=502,
#             detail="Dify did not return answer",
#         )

#     print("\n" + "=" * 70)
#     print("DIFY RESPONSE")
#     print("=" * 70)

#     print("CONVERSATION ID:", conversation_id)
#     print("ANSWER:", answer)

#     # ========================================================
#     # SAVE QUERY + RESPONSE TO MEM0
#     # ========================================================

#     memory_saved = False

#     print("\n" + "=" * 70)
#     print("💾 SAVING TO MEM0")
#     print("=" * 70)

#     try:

#         add_memory(
#             user_id=request.user_id,
#             query=request.query,
#             response=answer,
#         )

#         memory_saved = True

#         print("✅ MEMORY SAVED")

#     except Exception as e:

#         print("\n⚠️ MEM0 SAVE FAILED")
#         print(str(e))

#     # ========================================================
#     # RETURN TO CLIENT
#     # ========================================================

#     print("\n" + "=" * 70)
#     print("📤 RETURNING RESPONSE")
#     print("=" * 70)

#     print("USER ID:", request.user_id)
#     print("CONVERSATION ID:", conversation_id)
#     print("IS NEW CHAT:", is_new_chat)
#     print("MEMORY SAVED:", memory_saved)

#     return {
#         "success": True,
#         "user_id": request.user_id,
#         "conversation_id": conversation_id,
#         "answer": answer,
#         "memory_saved": memory_saved,
#     }

@app.post("/chat")
def chat(request: ChatRequest):

    print("\n" + "=" * 70)
    print("💬 CHAT REQUEST")
    print("=" * 70)
    print("USER ID:", request.user_id)
    print("QUERY:", request.query)
    print("INCOMING CONVERSATION ID:", request.conversation_id)

    is_new_chat = request.conversation_id is None

    print("\nIS NEW CHAT:", is_new_chat)

    if is_new_chat:
        print("🆕 New chat")
    else:
        print("➡️ Existing chat")
        print("Conversation ID:", request.conversation_id)

    payload = {
        "inputs": {
            "user_id": request.user_id,

            # IMPORTANT:
            # Dify input variable is Boolean.
            "is_new_chat": is_new_chat,

            # Keep the existing conversation ID available
            # inside the workflow.
            "conversation_id": request.conversation_id or "",
        },

        "query": request.query,

        # CHANGED: blocking → streaming
        "response_mode": "streaming",

        "user": request.user_id,
    }

    if not is_new_chat:

        payload["conversation_id"] = request.conversation_id

        print("\n📌 Sending existing conversation to Dify:")
        print(request.conversation_id)

    else:

        print("\n📌 No conversation_id sent to Dify")
        print("Dify will create a new conversation.")

    # ========================================================
    # DEBUG PAYLOAD
    # ========================================================

    print("\n" + "=" * 70)
    print("📤 DIFY REQUEST")
    print("=" * 70)

    print(payload)

    # ========================================================
    # STREAM DIFY RESPONSE
    # ========================================================

    def generate():

        full_answer = []
        conversation_id = request.conversation_id

        try:

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

        except requests.RequestException as e:

            print("\n❌ DIFY CONNECTION ERROR")
            print(str(e))

            yield (
                "event: error\n"
                f"data: {json.dumps({'error': str(e)})}\n\n"
            )

            return

        # ====================================================
        # CHECK DIFY RESPONSE
        # ====================================================

        if dify_response.status_code != 200:

            print("\n❌ DIFY ERROR")
            print("STATUS:", dify_response.status_code)

            error_text = dify_response.text

            print("BODY:", error_text)

            yield (
                "event: error\n"
                f"data: {json.dumps({
                    'message': 'Dify returned an error',
                    'status': dify_response.status_code,
                    'response': error_text
                })}\n\n"
            )

            return

        # ====================================================
        # READ STREAM
        # ====================================================

        print("\n" + "=" * 70)
        print("🔄 DIFY STREAM STARTED")
        print("=" * 70)

        try:

            for line in dify_response.iter_lines(
                decode_unicode=True
            ):

                if not line:
                    continue

                print("DIFY:", line)

                # Dify sends:
                #
                # event: message
                # data: {...}

                if not line.startswith("data:"):
                    continue

                data_text = line[5:].strip()

                try:

                    dify_data = json.loads(data_text)

                except json.JSONDecodeError:

                    print(
                        "⚠️ Could not parse Dify data:",
                        data_text
                    )

                    continue

                event = dify_data.get("event")

                # =================================================
                # CONVERSATION ID
                # =================================================

                if dify_data.get("conversation_id"):

                    conversation_id = (
                        dify_data["conversation_id"]
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

                        print(
                            "📝 CHUNK:",
                            repr(chunk)
                        )

                        yield (
                            "event: message\n"
                            f"data: {json.dumps({
                                'content': chunk
                            })}\n\n"
                        )

                # =================================================
                # MESSAGE END
                # =================================================

                elif event == "message_end":

                    answer = "".join(full_answer)

                    print("\n" + "=" * 70)
                    print("✅ DIFY RESPONSE COMPLETE")
                    print("=" * 70)

                    print(
                        "CONVERSATION ID:",
                        conversation_id
                    )

                    print(
                        "ANSWER:",
                        answer
                    )

                    # =============================================
                    # SAVE QUERY + RESPONSE TO MEM0
                    # =============================================

                    memory_saved = False

                    print("\n" + "=" * 70)
                    print("💾 SAVING TO MEM0")
                    print("=" * 70)

                    try:

                        add_memory(
                            user_id=request.user_id,
                            query=request.query,
                            response=answer,
                        )

                        memory_saved = True

                        print("✅ MEMORY SAVED")

                    except Exception as e:

                        print("\n⚠️ MEM0 SAVE FAILED")
                        print(str(e))

                    # =============================================
                    # SEND COMPLETION TO FRONTEND
                    # =============================================

                    yield (
                        "event: done\n"
                        f"data: {json.dumps({
                            'success': True,
                            'user_id': request.user_id,
                            'conversation_id': conversation_id,
                            'memory_saved': memory_saved
                        })}\n\n"
                    )

                    break

                # =================================================
                # ERROR EVENT
                # =================================================

                elif event == "error":

                    print("\n❌ DIFY STREAM ERROR")
                    print(dify_data)

                    yield (
                        "event: error\n"
                        f"data: {json.dumps({
                            'error': dify_data
                        })}\n\n"
                    )

                    break

        except Exception as e:

            print("\n❌ STREAM PROCESSING ERROR")
            print(str(e))

            yield (
                "event: error\n"
                f"data: {json.dumps({
                    'error': str(e)
                })}\n\n"
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
# ============================================================
# MEM0 SEARCH
# ============================================================

@app.post("/mem0/search")
def mem0_search(request: MemorySearchRequest):

    print("\n" + "=" * 70)
    print("🧠 MEM0 SEARCH REQUEST")
    print("=" * 70)
    print("USER ID:", request.user_id)
    print("QUERY:", request.query)

    try:

        result = search_memory(
            user_id=request.user_id,
            query=request.query,
        )

        print("\n✅ MEM0 SEARCH COMPLETE")
        print(result)

        memories = []

        for item in result.get("results", []):

            if isinstance(item, dict):

                memory = item.get("memory")

                if memory:
                    memories.append(memory)

        return {
            "success": True,
            "user_id": request.user_id,
            "query": request.query,
            "memories": memories,
        }

    except Exception as e:

        print("\n❌ MEM0 SEARCH FAILED")
        print(str(e))

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Mem0 search failed",
                "error": str(e),
            },
        )
import time
@app.post("/kb/upload")
async def upload_to_kb(
    user_id: str = Form(...),
    file: UploadFile = File(...),
):
    print("\n" + "=" * 70)
    print("📚 KB UPLOAD")
    print("=" * 70)
    print("USER ID:", user_id)
    print("FILE:", file.filename)

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required",
        )

    try:
        # ---------------------------------------------------------
        # 1. READ FILE
        # ---------------------------------------------------------
        file_content = await file.read()

        if not file_content:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty",
            )

        # ---------------------------------------------------------
        # 2. UPLOAD DOCUMENT TO DIFY
        #    WITH RUNTIME CHUNKING SETTINGS
        # ---------------------------------------------------------
        print("\n📤 Uploading document to Dify...")

        upload_settings = {
            "indexing_technique": "economy",
            "doc_form": "text_model",
            "process_rule": {
                "mode": "custom",
                "rules": {
                    "pre_processing_rules": [
                        {
                            "id": "remove_extra_spaces",
                            "enabled": True
                        },
                        {
                            "id": "remove_urls_emails",
                            "enabled": False
                        }
                    ],
                    "segmentation": {
                        "separator": "\n\n",
                        "max_tokens": 1024,
                        "chunk_overlap": 50
                    }
                }
            }
        }

        response = requests.post(
            f"https://api.dify.ai/v1/datasets/"
            f"{DIFY_KB_DATASET_ID}/document/create-by-file",
            headers={
                "Authorization": f"Bearer {DIFY_KB_API_KEY}",
            },
            files={
                "file": (
                    file.filename,
                    file_content,
                    file.content_type or "application/octet-stream",
                )
            },
            data={
                "data": json.dumps(upload_settings)
            },
            timeout=120,
        )

        print("DIFY UPLOAD STATUS:", response.status_code)
        print("DIFY RESPONSE:", response.text)

        if response.status_code not in (200, 201):
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Dify KB upload failed",
                    "status": response.status_code,
                    "response": response.text,
                },
            )

        dify_data = response.json()

        document = dify_data.get("document", {})
        document_id = document.get("id")
        batch_id = dify_data.get("batch")

        if not document_id:
            raise HTTPException(
                status_code=502,
                detail="Dify did not return document ID",
            )

        print("DOCUMENT ID:", document_id)
        print("BATCH ID:", batch_id)

        # ---------------------------------------------------------
        # 3. WAIT FOR INDEXING
        # ---------------------------------------------------------
        print("\n⏳ Waiting for Dify indexing...")

        max_attempts = 60
        indexing_status = None

        for attempt in range(max_attempts):

            status_response = requests.get(
                f"https://api.dify.ai/v1/datasets/"
                f"{DIFY_KB_DATASET_ID}/documents/{document_id}",
                headers={
                    "Authorization": f"Bearer {DIFY_KB_API_KEY}",
                },
                timeout=30,
            )

            if status_response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": "Could not check Dify document status",
                        "status": status_response.status_code,
                        "response": status_response.text,
                    },
                )

            status_data = status_response.json()

            indexing_status = status_data.get("indexing_status")

            print(
                f"Attempt {attempt + 1}/{max_attempts} "
                f"- status: {indexing_status}"
            )

            if indexing_status == "completed":
                break

            if indexing_status == "error":
                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": "Dify document indexing failed",
                        "document_id": document_id,
                        "error": status_data.get("error"),
                    },
                )

            time.sleep(2)

        else:
            raise HTTPException(
                status_code=504,
                detail={
                    "message": "Dify indexing timed out",
                    "document_id": document_id,
                    "last_status": indexing_status,
                },
            )

        print("✅ INDEXING COMPLETED")

        # ---------------------------------------------------------
        # 4. GET USER_ID METADATA FIELD
        # ---------------------------------------------------------
        print("\n🏷️ Getting user_id metadata field...")

        metadata_response = requests.get(
            f"https://api.dify.ai/v1/datasets/"
            f"{DIFY_KB_DATASET_ID}/metadata",
            headers={
                "Authorization": f"Bearer {DIFY_KB_API_KEY}",
            },
            timeout=30,
        )

        if metadata_response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Could not get Dify metadata fields",
                    "status": metadata_response.status_code,
                    "response": metadata_response.text,
                },
            )

        metadata_data = metadata_response.json()

        metadata_fields = metadata_data.get("doc_metadata", [])

        user_id_field = None

        for field in metadata_fields:
            if field.get("name") == "user_id":
                user_id_field = field
                break

        # ---------------------------------------------------------
        # 5. CREATE user_id FIELD IF IT DOESN'T EXIST
        # ---------------------------------------------------------
        if not user_id_field:

            print("⚠️ user_id metadata field does not exist.")
            print("Creating it...")

            create_metadata_response = requests.post(
                f"https://api.dify.ai/v1/datasets/"
                f"{DIFY_KB_DATASET_ID}/metadata",
                headers={
                    "Authorization": f"Bearer {DIFY_KB_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "name": "user_id",
                    "type": "string",
                },
                timeout=30,
            )

            if create_metadata_response.status_code not in (200, 201):
                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": "Could not create user_id metadata field",
                        "status": create_metadata_response.status_code,
                        "response": create_metadata_response.text,
                    },
                )

            user_id_field = create_metadata_response.json()

        metadata_field_id = user_id_field.get("id")

        if not metadata_field_id:
            raise HTTPException(
                status_code=502,
                detail="Dify did not return user_id metadata field ID",
            )

        print("METADATA FIELD ID:", metadata_field_id)

        # ---------------------------------------------------------
        # 6. ASSIGN user_id TO DOCUMENT
        # ---------------------------------------------------------
        print("\n🏷️ Assigning user_id metadata...")

        metadata_update_response = requests.post(
            f"https://api.dify.ai/v1/datasets/"
            f"{DIFY_KB_DATASET_ID}/documents/metadata",
            headers={
                "Authorization": f"Bearer {DIFY_KB_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "operation_data": [
                    {
                        "document_id": document_id,
                        "metadata_list": [
                            {
                                "id": metadata_field_id,
                                "value": user_id,
                                "name": "user_id",
                            }
                        ],
                    }
                ]
            },
            timeout=30,
        )

        print(
            "METADATA UPDATE STATUS:",
            metadata_update_response.status_code,
        )
        print("METADATA RESPONSE:", metadata_update_response.text)

        if metadata_update_response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Could not assign user_id metadata",
                    "status": metadata_update_response.status_code,
                    "response": metadata_update_response.text,
                },
            )

        # ---------------------------------------------------------
        # 7. VERIFY METADATA
        # ---------------------------------------------------------
        print("\n🔍 Verifying document metadata...")

        verify_response = requests.get(
            f"https://api.dify.ai/v1/datasets/"
            f"{DIFY_KB_DATASET_ID}/documents/{document_id}",
            headers={
                "Authorization": f"Bearer {DIFY_KB_API_KEY}",
            },
            timeout=30,
        )

        if verify_response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Could not verify document metadata",
                    "status": verify_response.status_code,
                    "response": verify_response.text,
                },
            )

        verify_data = verify_response.json()

        verified_user_id = None

        for metadata in verify_data.get("doc_metadata") or []:
            if metadata.get("name") == "user_id":
                verified_user_id = metadata.get("value")
                break

        if verified_user_id != user_id:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "user_id metadata verification failed",
                    "expected": user_id,
                    "actual": verified_user_id,
                },
            )

        print("✅ METADATA VERIFIED")
        print("USER ID:", verified_user_id)

        # ---------------------------------------------------------
        # 8. SUCCESS
        # ---------------------------------------------------------
        return {
            "success": True,
            "user_id": verified_user_id,
            "filename": file.filename,
            "document_id": document_id,
            "batch_id": batch_id,
            "indexing_status": verify_data.get("indexing_status"),
            "segment_count": verify_data.get("segment_count"),
            "metadata": {
                "user_id": verified_user_id,
            },
        }

    except requests.RequestException as e:

        print("\n❌ DIFY CONNECTION ERROR")
        print(str(e))

        raise HTTPException(
            status_code=502,
            detail={
                "message": "Could not connect to Dify Knowledge API",
                "error": str(e),
            },
        )
        
@app.get("/chat/history/{user_id}/{conversation_id}")
def get_chat_history(
    user_id: str,
    conversation_id: str,
):
    print("\n" + "=" * 70)
    print("📜 DIFY CHAT HISTORY REQUEST")
    print("=" * 70)
    print("USER ID:", user_id)
    print("CONVERSATION ID:", conversation_id)

    all_messages = []
    first_id = None

    try:

        while True:

            params = {
                "user": user_id,
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

            print(
                "DIFY HISTORY STATUS:",
                response.status_code
            )

            if response.status_code != 200:
                print("DIFY HISTORY ERROR:")
                print(response.text)

                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": "Dify history request failed",
                        "status": response.status_code,
                        "response": response.text,
                    },
                )

            data = response.json()

            messages = data.get("data", [])

            all_messages.extend(messages)

            print(
                f"Retrieved {len(messages)} messages "
                f"(total: {len(all_messages)})"
            )

            # No more messages
            if not data.get("has_more"):
                break

            # Safety check
            if not messages:
                break

            # Dify pagination
            first_id = messages[-1].get("id")

            if not first_id:
                break

        print("\n✅ COMPLETE CHAT HISTORY RETRIEVED")
        print("TOTAL MESSAGES:", len(all_messages))

        return {
            "success": True,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "message_count": len(all_messages),
            "messages": all_messages,
        }

    except requests.RequestException as e:

        print("\n❌ DIFY HISTORY CONNECTION ERROR")
        print(str(e))

        raise HTTPException(
            status_code=502,
            detail={
                "message": "Could not connect to Dify",
                "error": str(e),
            },
        )
class AssessmentReportRequest(BaseModel):
    user_id: str
    questions_and_answers: dict
DIFY_REPORT_API_KEY = os.getenv("DIFY_REPORT_API_KEY")
DIFY_REPORT_API_URL = os.getenv("DIFY_REPORT_API_URL")
@app.post("/assessment/report")
def generate_assessment_report(request: AssessmentReportRequest):

    if not DIFY_REPORT_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="DIFY_REPORT_API_KEY is not configured"
        )

    # -------------------------------------------------
    # 1. GET QUESTIONS + ANSWERS
    # -------------------------------------------------

    questions_and_answers = request.questions_and_answers.get(
        "questions_and_answers",
        []
    )

    if not isinstance(questions_and_answers, list):
        raise HTTPException(
            status_code=400,
            detail="questions_and_answers must contain a list"
        )

    # -------------------------------------------------
    # 2. SEND QUESTIONS + ANSWERS TO DIFY
    # -------------------------------------------------

    payload = {
        "inputs": {
            "questions_and_answers": request.questions_and_answers
        },
        "response_mode": "blocking",
        "user": request.user_id
    }

    headers = {
        "Authorization": f"Bearer {DIFY_REPORT_API_KEY}",
        "Content-Type": "application/json"
    }

    try:

        response = requests.post(
            DIFY_REPORT_API_URL,
            headers=headers,
            json=payload,
            timeout=120
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail={
                    "message": "Dify report generation failed",
                    "error": response.text
                }
            )

        data = response.json()

    except requests.RequestException as e:

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Could not connect to Dify",
                "error": str(e)
            }
        )

    # -------------------------------------------------
    # 3. GET REPORT FROM DIFY
    # -------------------------------------------------

    outputs = data.get(
        "data",
        {}
    ).get(
        "outputs",
        {}
    )

    report = outputs.get("text")

    if not report:
        raise HTTPException(
            status_code=500,
            detail="Dify returned an empty report"
        )

    # -------------------------------------------------
    # 4. TRY TO CONVERT REPORT STRING INTO JSON
    # -------------------------------------------------

    report_data = report

    if isinstance(report, str):

        try:

            report_data = json.loads(report)

        except json.JSONDecodeError:

            # If Dify returned JSON inside markdown fences
            cleaned_report = report.strip()

            if cleaned_report.startswith("```json"):
                cleaned_report = cleaned_report[7:]

            elif cleaned_report.startswith("```"):
                cleaned_report = cleaned_report[3:]

            if cleaned_report.endswith("```"):
                cleaned_report = cleaned_report[:-3]

            cleaned_report = cleaned_report.strip()

            try:
                report_data = json.loads(cleaned_report)
            except json.JSONDecodeError:
                report_data = report

    # -------------------------------------------------
    # 5. CREATE SAFE FILE NAME
    # -------------------------------------------------

    safe_user_name = re.sub(
        r"[^a-zA-Z0-9_-]",
        "_",
        request.user_id
    ).strip("_")

    if not safe_user_name:
        safe_user_name = "user"

    # -------------------------------------------------
    # 6. CREATE DIRECTORY
    # -------------------------------------------------

    os.makedirs(
        "assessment_data",
        exist_ok=True
    )

    file_path = os.path.join(
        "assessment_data",
        f"{safe_user_name}.txt"
    )

    # -------------------------------------------------
    # 7. CREATE FINAL JSON
    # -------------------------------------------------

    assessment_data = {

        "user_id": request.user_id,

        "questions_and_answers":
            questions_and_answers,

        "report":
            report_data

    }

    # -------------------------------------------------
    # 8. SAVE JSON FILE
    # -------------------------------------------------

    with open(
        file_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            assessment_data,
            file,
            indent=2,
            ensure_ascii=False
        )
    # -------------------------------------------------
    # 9. UPLOAD THE JSON FILE TO EXISTING KB ENDPOINT
    # -------------------------------------------------

    try:

        with open(
            file_path,
            "rb"
        ) as assessment_file:

            kb_response = requests.post(
                "http://localhost:8000/kb/upload",

                files={
                    "file": (
                        f"{safe_user_name}.txt",
                        assessment_file,
                        "application/json"
                    )
                },

                data={
                    "user_id": request.user_id
                },

                timeout=180
            )


        if kb_response.status_code != 200:

            raise HTTPException(
                status_code=kb_response.status_code,
                detail={
                    "message": "KB upload failed",
                    "error": kb_response.text
                }
            )


        kb_data = kb_response.json()


    except requests.RequestException as e:

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Could not connect to KB upload endpoint",
                "error": str(e)
            }
        )
  

    return {

        "success": True,

        "user_id":
            request.user_id,

        "report":
            report_data,

        "file":
            file_path,

        "kb_uploaded":
            True,

        "kb_response":
            kb_data,

        "workflow_run_id":
            data.get("workflow_run_id")

    }