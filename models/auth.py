from pydantic import BaseModel, EmailStr, Field


# ============================================================
# SIGNUP
# ============================================================

class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)


# ============================================================
# EMAIL VERIFICATION
# ============================================================

class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


# ============================================================
# LOGIN
# ============================================================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ============================================================
# REFRESH TOKEN
# ============================================================

class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ============================================================
# PASSWORD RESET
# ============================================================

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


# ============================================================
# PROFILE
# ============================================================

class UpdateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


# ============================================================
# ADMIN / RBAC
# ============================================================

class UpdateUserRoleRequest(BaseModel):
    role: str


class CreateAdminRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=100)