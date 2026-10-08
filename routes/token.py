from fastapi import APIRouter

from auth.jwt import create_access_token


router = APIRouter(prefix="/auth")


@router.post("/test-access-token")
def generate_access_token():

    user_id = "040b2fa5-9847-4ba7-a99e-37bf4252c8bd"
    email = "rmoosa568@gmail.com"
    role = "user"

    access_token = create_access_token(
        user_id=user_id,
        email=email,
        role=role
    )

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer"
    }