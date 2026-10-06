from fastapi import APIRouter, HTTPException, UploadFile, File, Depends

from auth.dependencies import get_current_user
from services.kb_service import upload_document_to_kb

router = APIRouter()


@router.post("/kb/upload")
async def upload_to_kb(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required"
        )

    try:
        file_content = await file.read()

        if not file_content:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty"
            )

        result = upload_document_to_kb(
            user_id=user_id,
            filename=file.filename,
            file_content=file_content,
            content_type=file.content_type or "application/octet-stream"
        )

        return result

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Could not upload document to Dify Knowledge Base",
                "error": str(e)
            }
        )