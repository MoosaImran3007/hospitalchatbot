import json
import time
import requests

from config import DIFY_KB_API_KEY, DIFY_KB_DATASET_ID


DIFY_BASE_URL = "https://api.dify.ai/v1"


def upload_document_to_kb(
    user_id: str,
    filename: str,
    file_content: bytes,
    content_type: str = "text/plain"
):
    """
    Upload a document to the configured Dify Knowledge Base,
    wait for indexing, assign the authenticated user's ID as
    document metadata, verify it, and return the result.
    """

    # =========================================================
    # 1. Validate configuration
    # =========================================================

    if not DIFY_KB_API_KEY:
        raise Exception(
            "DIFY_KB_API_KEY is not configured"
        )

    if not DIFY_KB_DATASET_ID:
        raise Exception(
            "DIFY_KB_DATASET_ID is not configured"
        )

    if not user_id:
        raise Exception(
            "user_id is required"
        )

    if not filename:
        raise Exception(
            "Filename is required"
        )

    if not file_content:
        raise Exception(
            "Document is empty"
        )

    # =========================================================
    # 2. Common headers
    # =========================================================

    headers = {
        "Authorization": f"Bearer {DIFY_KB_API_KEY}"
    }

    json_headers = {
        "Authorization": f"Bearer {DIFY_KB_API_KEY}",
        "Content-Type": "application/json"
    }

    dataset_url = (
        f"{DIFY_BASE_URL}/datasets/"
        f"{DIFY_KB_DATASET_ID}"
    )

    # =========================================================
    # 3. Create HTTP session
    # =========================================================

    session = requests.Session()

    try:

        # =====================================================
        # 4. Upload document to Dify
        # =====================================================

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

        try:
            response = session.post(
                f"{dataset_url}/document/create-by-file",
                headers=headers,
                files={
                    "file": (
                        filename,
                        file_content,
                        content_type
                    )
                },
                data={
                    "data": json.dumps(upload_settings)
                },
                timeout=120
            )

        except requests.Timeout:
            raise Exception(
                "Dify Knowledge Base upload timed out"
            )

        except requests.RequestException as e:
            raise Exception(
                f"Could not connect to Dify Knowledge Base: {str(e)}"
            )

        if response.status_code not in (200, 201):
            raise Exception(
                f"Dify KB upload failed "
                f"(HTTP {response.status_code}): "
                f"{response.text}"
            )

        try:
            dify_data = response.json()
        except ValueError:
            raise Exception(
                "Dify returned an invalid JSON response during upload"
            )

        document = dify_data.get("document") or {}

        document_id = document.get("id")
        batch_id = dify_data.get("batch")

        if not document_id:
            raise Exception(
                "Dify did not return a document ID"
            )

        # =====================================================
        # 5. Wait for indexing
        # =====================================================

        max_attempts = 60
        indexing_status = None
        verify_data = None

        for _ in range(max_attempts):

            try:
                status_response = session.get(
                    f"{dataset_url}/documents/{document_id}",
                    headers=headers,
                    timeout=30
                )

            except requests.Timeout:
                raise Exception(
                    "Dify document status request timed out"
                )

            except requests.RequestException as e:
                raise Exception(
                    f"Could not check Dify document status: {str(e)}"
                )

            if status_response.status_code != 200:
                raise Exception(
                    "Could not check Dify document status "
                    f"(HTTP {status_response.status_code}): "
                    f"{status_response.text}"
                )

            try:
                status_data = status_response.json()
            except ValueError:
                raise Exception(
                    "Dify returned invalid JSON while checking document status"
                )

            indexing_status = status_data.get(
                "indexing_status"
            )

            if indexing_status == "completed":
                verify_data = status_data
                break

            if indexing_status == "error":
                raise Exception(
                    "Dify document indexing failed: "
                    f"{status_data.get('error')}"
                )

            time.sleep(2)

        else:
            raise Exception(
                "Dify indexing timed out. "
                f"Last status: {indexing_status}"
            )

        # =====================================================
        # 6. Get existing metadata fields
        # =====================================================

        try:
            metadata_response = session.get(
                f"{dataset_url}/metadata",
                headers=headers,
                timeout=30
            )

        except requests.Timeout:
            raise Exception(
                "Dify metadata request timed out"
            )

        except requests.RequestException as e:
            raise Exception(
                f"Could not connect to Dify metadata API: {str(e)}"
            )

        if metadata_response.status_code != 200:
            raise Exception(
                "Could not get Dify metadata fields "
                f"(HTTP {metadata_response.status_code}): "
                f"{metadata_response.text}"
            )

        try:
            metadata_data = metadata_response.json()
        except ValueError:
            raise Exception(
                "Dify returned invalid metadata JSON"
            )

        metadata_fields = metadata_data.get(
            "doc_metadata"
        ) or []

        user_id_field = None

        for field in metadata_fields:
            if field.get("name") == "user_id":
                user_id_field = field
                break

        # =====================================================
        # 7. Create user_id metadata field if necessary
        # =====================================================

        if not user_id_field:

            try:
                create_metadata_response = session.post(
                    f"{dataset_url}/metadata",
                    headers=json_headers,
                    json={
                        "name": "user_id",
                        "type": "string"
                    },
                    timeout=30
                )

            except requests.Timeout:
                raise Exception(
                    "Creating Dify user_id metadata field timed out"
                )

            except requests.RequestException as e:
                raise Exception(
                    f"Could not create Dify metadata field: {str(e)}"
                )

            if create_metadata_response.status_code not in (
                200,
                201
            ):
                raise Exception(
                    "Could not create user_id metadata field "
                    f"(HTTP {create_metadata_response.status_code}): "
                    f"{create_metadata_response.text}"
                )

            try:
                user_id_field = create_metadata_response.json()
            except ValueError:
                raise Exception(
                    "Dify returned invalid JSON when creating metadata field"
                )

        metadata_field_id = user_id_field.get("id")

        if not metadata_field_id:
            raise Exception(
                "Dify did not return user_id metadata field ID"
            )

        # =====================================================
        # 8. Assign user_id metadata to document
        # =====================================================

        try:
            metadata_update_response = session.post(
                f"{dataset_url}/documents/metadata",
                headers=json_headers,
                json={
                    "operation_data": [
                        {
                            "document_id": document_id,
                            "metadata_list": [
                                {
                                    "id": metadata_field_id,
                                    "value": str(user_id),
                                    "name": "user_id"
                                }
                            ]
                        }
                    ]
                },
                timeout=30
            )

        except requests.Timeout:
            raise Exception(
                "Dify document metadata update timed out"
            )

        except requests.RequestException as e:
            raise Exception(
                f"Could not update Dify document metadata: {str(e)}"
            )

        if metadata_update_response.status_code != 200:
            raise Exception(
                "Could not assign user_id metadata "
                f"(HTTP {metadata_update_response.status_code}): "
                f"{metadata_update_response.text}"
            )

        # =====================================================
        # 9. Verify metadata
        # =====================================================

        try:
            verify_response = session.get(
                f"{dataset_url}/documents/{document_id}",
                headers=headers,
                timeout=30
            )

        except requests.Timeout:
            raise Exception(
                "Dify document metadata verification timed out"
            )

        except requests.RequestException as e:
            raise Exception(
                f"Could not verify Dify document metadata: {str(e)}"
            )

        if verify_response.status_code != 200:
            raise Exception(
                "Could not verify document metadata "
                f"(HTTP {verify_response.status_code}): "
                f"{verify_response.text}"
            )

        try:
            verify_data = verify_response.json()
        except ValueError:
            raise Exception(
                "Dify returned invalid JSON during metadata verification"
            )

        verified_user_id = None

        for metadata in verify_data.get("doc_metadata") or []:

            if metadata.get("name") == "user_id":
                verified_user_id = metadata.get("value")
                break

        if str(verified_user_id) != str(user_id):
            raise Exception(
                "user_id metadata verification failed"
            )

        # =====================================================
        # 10. Return result
        # =====================================================

        return {
            "success": True,
            "user_id": str(verified_user_id),
            "filename": filename,
            "document_id": document_id,
            "batch_id": batch_id,
            "indexing_status": verify_data.get(
                "indexing_status"
            ),
            "segment_count": verify_data.get(
                "segment_count"
            )
        }

    finally:
        session.close()
def delete_document_from_kb(document_id: str):
    if not DIFY_KB_API_KEY:
        raise ValueError("DIFY_KB_API_KEY is not configured")

    if not DIFY_KB_DATASET_ID:
        raise ValueError("DIFY_KB_DATASET_ID is not configured")

    if not document_id:
        raise ValueError("Document ID is required")

    url = (
        f"https://api.dify.ai/v1/datasets/"
        f"{DIFY_KB_DATASET_ID}/documents/{document_id}"
    )

    headers = {
        "Authorization": f"Bearer {DIFY_KB_API_KEY}"
    }

    response = requests.delete(
        url,
        headers=headers,
        timeout=30
    )

    if response.status_code not in (200, 204):
        raise RuntimeError(
            f"Failed to delete Dify document: "
            f"{response.status_code} - {response.text}"
        )

    return {
        "success": True,
        "document_id": document_id
    }