import os
import secrets


from datetime import datetime, timedelta, timezone
import resend
import bcrypt

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Depends
from jose import JWTError, jwt

from database import get_db

from auth.dependencies import (
    get_current_user,
    require_admin,
    require_super_admin
)

from auth.jwt import (
    create_access_token,
    create_refresh_token,
    SECRET_KEY,
    ALGORITHM
)

from models.auth import (
    SignupRequest,
    VerifyEmailRequest,
    LoginRequest,
    RefreshTokenRequest,
    ResendVerificationRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    UpdateProfileRequest,
    UpdateUserRoleRequest,
    CreateAdminRequest
)


load_dotenv()


router = APIRouter(prefix="/auth")


# ============================================================
# EMAIL
# ============================================================

def send_otp_email(
    to_email: str,
    otp: str
):
    resend.api_key = os.getenv("RESEND_API_KEY")

    if not resend.api_key:
        raise RuntimeError("RESEND_API_KEY is not set")

    from_email = os.getenv("RESEND_FROM_EMAIL")

    if not from_email:
        raise RuntimeError("RESEND_FROM_EMAIL is not set")

    params = {
        "from": from_email,
        "to": [to_email],
        "subject": "Your Email Verification Code",
        "html": f"""
        <html>
            <body>
                <h2>Email Verification</h2>

                <p>Hello,</p>

                <p>Your verification code is:</p>

                <h1>{otp}</h1>

                <p>
                    This code will expire in
                    <strong>10 minutes</strong>.
                </p>

                <p>
                    If you did not create an account,
                    you can safely ignore this email.
                </p>

                <p>Regards,<br>Dify Backend</p>
            </body>
        </html>
        """
    }

    try:
        result = resend.Emails.send(params)

        print(f"OTP email sent successfully to {to_email}")
        print(f"Resend response: {result}")

        return result

    except Exception as e:
        print(f"Failed to send OTP email to {to_email}: {e}")
        raise

# ============================================================
# SIGNUP
# ============================================================

@router.post("/signup")
def signup(request: SignupRequest):

    db = get_db()
    cursor = db.cursor()

    try:

        # Check if email already exists
        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE email = %s
            """,
            (request.email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

        # Hash password
        password_hash = bcrypt.hashpw(
            request.password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        # Create user
        cursor.execute(
            """
            INSERT INTO users (
                email,
                password_hash,
                is_verified
            )
            VALUES (%s, %s, FALSE)
            RETURNING id, email, is_verified
            """,
            (
                request.email,
                password_hash
            )
        )

        user = cursor.fetchone()

        # Generate 6-digit OTP
        verification_code = (
            f"{secrets.randbelow(1000000):06d}"
        )

        # OTP expires in 10 minutes
        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(minutes=10)
        )

        # Store OTP
        cursor.execute(
            """
            INSERT INTO email_verifications (
                user_id,
                code,
                expires_at
            )
            VALUES (%s, %s, %s)
            """,
            (
                user[0],
                verification_code,
                expires_at
            )
        )

        db.commit()

        # Send OTP
        send_otp_email(
            user[1],
            verification_code
        )

        return {
            "success": True,
            "message": "User created successfully. Verification code sent.",
            "user": {
                "id": str(user[0]),
                "email": user[1],
                "is_verified": user[2]
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        cursor.close()
        db.close()


# ============================================================
# VERIFY EMAIL
# ============================================================

@router.post("/verify-email")
def verify_email(
    request: VerifyEmailRequest
):

    db = get_db()
    cursor = db.cursor()

    try:

        # Find user
        cursor.execute(
            """
            SELECT id, email, is_verified, role
            FROM users
            WHERE email = %s
            """,
            (request.email,)
        )

        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        user_id, email, is_verified, role = user

        if is_verified:
            raise HTTPException(
                status_code=400,
                detail="Email is already verified"
            )

        # Get latest OTP
        cursor.execute(
            """
            SELECT id, code, expires_at
            FROM email_verifications
            WHERE user_id = %s
            ORDER BY expires_at DESC
            LIMIT 1
            """,
            (user_id,)
        )

        verification = cursor.fetchone()

        if not verification:
            raise HTTPException(
                status_code=400,
                detail="Verification code not found"
            )

        verification_id, stored_code, expires_at = verification

        # Check expiry
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(
                status_code=400,
                detail="Verification code has expired"
            )

        # Check OTP
        if request.code != stored_code:
            raise HTTPException(
                status_code=400,
                detail="Invalid verification code"
            )

        # Verify email
        cursor.execute(
            """
            UPDATE users
            SET is_verified = TRUE
            WHERE id = %s
            """,
            (user_id,)
        )

        # Delete used OTP
        cursor.execute(
            """
            DELETE FROM email_verifications
            WHERE id = %s
            """,
            (verification_id,)
        )

        # Create access token
        access_token = create_access_token(
            str(user_id),
            email,
            role
        )

        # Create refresh token
        refresh_token, refresh_expires_at = create_refresh_token(
            str(user_id),
            email
        )

        # Store refresh token
        cursor.execute(
            """
            INSERT INTO refresh_tokens (
                user_id,
                token,
                expires_at
            )
            VALUES (%s, %s, %s)
            """,
            (
                user_id,
                refresh_token,
                refresh_expires_at
            )
        )

        db.commit()

        return {
            "success": True,
            "message": "Email verified successfully. You are now logged in.",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": str(user_id),
                "email": email,
                "is_verified": True,
                "role": role
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        cursor.close()
        db.close()


# ============================================================
# RESEND VERIFICATION
# ============================================================

@router.post("/resend-verification")
def resend_verification(
    request: ResendVerificationRequest
):

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute(
            """
            SELECT id, email, is_verified
            FROM users
            WHERE email = %s
            """,
            (request.email,)
        )

        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        if user[2]:
            raise HTTPException(
                status_code=400,
                detail="Email is already verified"
            )

        # Generate new OTP
        verification_code = (
            f"{secrets.randbelow(1000000):06d}"
        )

        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(minutes=10)
        )

        # Remove old OTPs
        cursor.execute(
            """
            DELETE FROM email_verifications
            WHERE user_id = %s
            """,
            (user[0],)
        )

        # Store new OTP
        cursor.execute(
            """
            INSERT INTO email_verifications (
                user_id,
                code,
                expires_at
            )
            VALUES (%s, %s, %s)
            """,
            (
                user[0],
                verification_code,
                expires_at
            )
        )

        db.commit()

        # Send OTP
        send_otp_email(
            user[1],
            verification_code
        )

        return {
            "success": True,
            "message": "A new verification code has been sent"
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        cursor.close()
        db.close()


# ============================================================
# LOGIN
# ============================================================

@router.post("/login")
def login(
    request: LoginRequest
):

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute(
            """
            SELECT
                id,
                email,
                password_hash,
                is_verified,
                role
            FROM users
            WHERE email = %s
            """,
            (request.email,)
        )

        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        (
            user_id,
            email,
            password_hash,
            is_verified,
            role
        ) = user

        # Email verification required
        if not is_verified:
            raise HTTPException(
                status_code=403,
                detail="Please verify your email before logging in"
            )

        # Check password
        password_correct = bcrypt.checkpw(
            request.password.encode("utf-8"),
            password_hash.encode("utf-8")
        )

        if not password_correct:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        # Create access token
        access_token = create_access_token(
            str(user_id),
            email,
            role
        )

        # Create refresh token
        refresh_token, refresh_expires_at = (
            create_refresh_token(
                str(user_id),
                email
            )
        )

        # Store refresh token
        cursor.execute(
            """
            INSERT INTO refresh_tokens (
                user_id,
                token,
                expires_at
            )
            VALUES (%s, %s, %s)
            """,
            (
                user_id,
                refresh_token,
                refresh_expires_at
            )
        )

        db.commit()

        return {
            "success": True,
            "message": "Login successful",

            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",

            "user": {
                "id": str(user_id),
                "email": email,
                "is_verified": is_verified,
                "role": role
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        cursor.close()
        db.close()


# ============================================================
# CURRENT USER
# ============================================================

@router.get("/me")
def get_me(
    current_user: dict = Depends(get_current_user)
):

    return {
        "success": True,
        "user": current_user
    }


# ============================================================
# REFRESH ACCESS TOKEN
# ============================================================

@router.post("/refresh")
def refresh_access_token(
    request: RefreshTokenRequest
):

    refresh_token = request.refresh_token

    try:

        # Decode refresh JWT
        payload = jwt.decode(
            refresh_token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("sub")
        email = payload.get("email")
        token_type = payload.get("type")

        if not user_id or not email:
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token"
            )

        if token_type != "refresh":
            raise HTTPException(
                status_code=401,
                detail="Invalid token type"
            )

        db = get_db()
        cursor = db.cursor()

        try:

            # Validate token in database
            cursor.execute(
                """
                SELECT revoked, expires_at
                FROM refresh_tokens
                WHERE token = %s
                  AND user_id = %s
                """,
                (
                    refresh_token,
                    user_id
                )
            )

            stored_token = cursor.fetchone()

            if not stored_token:
                raise HTTPException(
                    status_code=401,
                    detail="Refresh token not found"
                )

            revoked, expires_at = stored_token

            if revoked:
                raise HTTPException(
                    status_code=401,
                    detail="Refresh token has been revoked"
                )

            if datetime.now(timezone.utc) > expires_at:
                raise HTTPException(
                    status_code=401,
                    detail="Refresh token has expired"
                )

            # Get CURRENT user role from database
            cursor.execute(
                """
                SELECT email, role
                FROM users
                WHERE id = %s
                """,
                (user_id,)
            )

            user = cursor.fetchone()

            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="User no longer exists"
                )

            current_email, role = user

            # Create new access token
            new_access_token = create_access_token(
                str(user_id),
                current_email,
                role
            )

            return {
                "success": True,
                "access_token": new_access_token,
                "token_type": "bearer",
                "user": {
                    "id": str(user_id),
                    "email": current_email,
                    "role": role
                }
            }

        finally:
            cursor.close()
            db.close()

    except HTTPException:
        raise

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token"
        )


# ============================================================
# LOGOUT
# ============================================================

@router.post("/logout")
def logout(
    request: RefreshTokenRequest
):

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute(
            """
            UPDATE refresh_tokens
            SET revoked = TRUE
            WHERE token = %s
            """,
            (request.refresh_token,)
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Refresh token not found"
            )

        db.commit()

        return {
            "success": True,
            "message": "Logged out successfully"
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        cursor.close()
        db.close()


# ============================================================
# FORGOT PASSWORD
# ============================================================

@router.post("/forgot-password")
def forgot_password(
    request: ForgotPasswordRequest
):

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute(
            """
            SELECT id, email
            FROM users
            WHERE email = %s
            """,
            (request.email,)
        )

        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        # Generate reset code
        reset_code = (
            f"{secrets.randbelow(1000000):06d}"
        )

        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(minutes=10)
        )

        # Remove previous codes
        cursor.execute(
            """
            DELETE FROM email_verifications
            WHERE user_id = %s
            """,
            (user[0],)
        )

        # Store reset code
        cursor.execute(
            """
            INSERT INTO email_verifications (
                user_id,
                code,
                expires_at
            )
            VALUES (%s, %s, %s)
            """,
            (
                user[0],
                reset_code,
                expires_at
            )
        )

        db.commit()

        # Send reset code
        send_otp_email(
            user[1],
            reset_code
        )

        return {
            "success": True,
            "message": "Password reset code has been sent"
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        cursor.close()
        db.close()


# ============================================================
# RESET PASSWORD
# ============================================================

@router.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest
):

    db = get_db()
    cursor = db.cursor()

    try:

        # Find user
        cursor.execute(
            """
            SELECT id, email
            FROM users
            WHERE email = %s
            """,
            (request.email,)
        )

        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        # Get latest reset code
        cursor.execute(
            """
            SELECT id, code, expires_at
            FROM email_verifications
            WHERE user_id = %s
            ORDER BY expires_at DESC
            LIMIT 1
            """,
            (user[0],)
        )

        verification = cursor.fetchone()

        if not verification:
            raise HTTPException(
                status_code=400,
                detail="No password reset code found"
            )

        verification_id, stored_code, expires_at = verification

        # Check expiry
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(
                status_code=400,
                detail="Password reset code has expired"
            )

        # Check code
        if request.code != stored_code:
            raise HTTPException(
                status_code=400,
                detail="Invalid password reset code"
            )

        # Hash new password
        new_password_hash = bcrypt.hashpw(
            request.new_password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        # Update password
        cursor.execute(
            """
            UPDATE users
            SET password_hash = %s
            WHERE id = %s
            """,
            (
                new_password_hash,
                user[0]
            )
        )

        # Delete used reset code
        cursor.execute(
            """
            DELETE FROM email_verifications
            WHERE id = %s
            """,
            (verification_id,)
        )

        # Revoke all refresh tokens
        cursor.execute(
            """
            UPDATE refresh_tokens
            SET revoked = TRUE
            WHERE user_id = %s
            """,
            (user[0],)
        )

        db.commit()

        return {
            "success": True,
            "message": "Password reset successfully"
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        cursor.close()
        db.close()


# ============================================================
# CHANGE PASSWORD
# ============================================================

@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user)
):

    db = get_db()
    cursor = db.cursor()

    try:

        # Get current password
        cursor.execute(
            """
            SELECT password_hash
            FROM users
            WHERE id = %s
            """,
            (current_user["id"],)
        )

        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        # Verify current password
        if not bcrypt.checkpw(
            request.current_password.encode("utf-8"),
            user[0].encode("utf-8")
        ):
            raise HTTPException(
                status_code=400,
                detail="Current password is incorrect"
            )

        # Prevent same password
        if request.current_password == request.new_password:
            raise HTTPException(
                status_code=400,
                detail="New password must be different"
            )

        # Hash new password
        new_password_hash = bcrypt.hashpw(
            request.new_password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        # Update password
        cursor.execute(
            """
            UPDATE users
            SET password_hash = %s
            WHERE id = %s
            """,
            (
                new_password_hash,
                current_user["id"]
            )
        )

        # Revoke refresh tokens
        cursor.execute(
            """
            UPDATE refresh_tokens
            SET revoked = TRUE
            WHERE user_id = %s
            """,
            (current_user["id"],)
        )

        db.commit()

        return {
            "success": True,
            "message": "Password changed successfully"
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        cursor.close()
        db.close()


# ============================================================
# GET PROFILE
# ============================================================

@router.get("/profile")
def get_profile(
    current_user: dict = Depends(get_current_user)
):

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute(
            """
            SELECT
                id,
                name,
                email,
                is_verified,
                role
            FROM users
            WHERE id = %s
            """,
            (current_user["id"],)
        )

        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        return {
            "success": True,
            "user": {
                "id": str(user[0]),
                "name": user[1],
                "email": user[2],
                "is_verified": user[3],
                "role": user[4]
            }
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# UPDATE PROFILE
# ============================================================

@router.put("/profile")
def update_profile(
    request: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user)
):

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute(
            """
            UPDATE users
            SET name = %s
            WHERE id = %s
            RETURNING id, name, email, is_verified, role
            """,
            (
                request.name,
                current_user["id"]
            )
        )

        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        db.commit()

        return {
            "success": True,
            "message": "Profile updated successfully",
            "user": {
                "id": str(user[0]),
                "name": user[1],
                "email": user[2],
                "is_verified": user[3],
                "role": user[4]
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        cursor.close()
        db.close()


# ============================================================
# ADMIN TEST
# ============================================================

@router.get("/admin-test")
def admin_test(
    current_user: dict = Depends(require_admin)
):

    return {
        "success": True,
        "message": "Welcome Admin!",
        "user": current_user
    }


# ============================================================
# GET ALL USERS
# ============================================================

@router.get("/admin/users")
def get_all_users(
    current_user: dict = Depends(require_admin)
):

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute(
            """
            SELECT
                id,
                name,
                email,
                is_verified,
                role
            FROM users
            ORDER BY email
            """
        )

        users = cursor.fetchall()

        return {
            "success": True,
            "users": [
                {
                    "id": str(user[0]),
                    "name": user[1],
                    "email": user[2],
                    "is_verified": user[3],
                    "role": user[4]
                }
                for user in users
            ]
        }

    finally:
        cursor.close()
        db.close()


# ============================================================
# UPDATE USER ROLE
# ============================================================

@router.put("/admin/users/{user_id}/role")
def update_user_role(
    user_id: str,
    request: UpdateUserRoleRequest,
    current_user: dict = Depends(require_admin)
):

    db = get_db()
    cursor = db.cursor()

    try:

        allowed_roles = [
            "user",
            "admin",
            "super_admin"
        ]

        if request.role not in allowed_roles:
            raise HTTPException(
                status_code=400,
                detail="Invalid role"
            )

        # Find target user
        cursor.execute(
            """
            SELECT
                id,
                email,
                role
            FROM users
            WHERE id = %s
            """,
            (user_id,)
        )

        target_user = cursor.fetchone()

        if not target_user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        target_id, target_email, target_role = target_user

        current_role = current_user["role"]

        # Super admin cannot be modified
        if target_role == "super_admin":
            raise HTTPException(
                status_code=403,
                detail="Super admin cannot be modified"
            )

        # Admin cannot modify another admin
        if (
            target_role == "admin"
            and current_role != "super_admin"
        ):
            raise HTTPException(
                status_code=403,
                detail="Only super admin can modify an admin"
            )

        # Only super admin can assign super_admin
        if (
            request.role == "super_admin"
            and current_role != "super_admin"
        ):
            raise HTTPException(
                status_code=403,
                detail="Only super admin can create a super admin"
            )

        # Update role
        cursor.execute(
            """
            UPDATE users
            SET role = %s
            WHERE id = %s
            RETURNING id, email, role
            """,
            (
                request.role,
                target_id
            )
        )

        updated_user = cursor.fetchone()

        db.commit()

        return {
            "success": True,
            "message": "User role updated successfully",
            "user": {
                "id": str(updated_user[0]),
                "email": updated_user[1],
                "role": updated_user[2]
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        cursor.close()
        db.close()


# ============================================================
# DELETE USER
# ============================================================

@router.delete("/admin/users/{user_id}")
def delete_user(
    user_id: str,
    current_user: dict = Depends(require_admin)
):

    db = get_db()
    cursor = db.cursor()

    try:

        # Find target user
        cursor.execute(
            """
            SELECT
                id,
                email,
                role
            FROM users
            WHERE id = %s
            """,
            (user_id,)
        )

        target_user = cursor.fetchone()

        if not target_user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        target_id, target_email, target_role = target_user

        current_role = current_user["role"]

        # Super admin cannot be deleted
        if target_role == "super_admin":
            raise HTTPException(
                status_code=403,
                detail="Super admin cannot be deleted"
            )

        # Admin cannot delete another admin
        if (
            target_role == "admin"
            and current_role != "super_admin"
        ):
            raise HTTPException(
                status_code=403,
                detail="Only super admin can delete an admin"
            )

        # Prevent self deletion
        if str(target_id) == str(current_user["id"]):
            raise HTTPException(
                status_code=400,
                detail="You cannot delete your own account"
            )

        # Delete user
        cursor.execute(
            """
            DELETE FROM users
            WHERE id = %s
            """,
            (target_id,)
        )

        db.commit()

        return {
            "success": True,
            "message": "User deleted successfully",
            "user": {
                "id": str(target_id),
                "email": target_email,
                "role": target_role
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        cursor.close()
        db.close()


# ============================================================
# CREATE ADMIN
# ============================================================

@router.post("/admin/create")
def create_admin(
    request: CreateAdminRequest,
    current_user: dict = Depends(require_super_admin)
):

    db = get_db()
    cursor = db.cursor()

    try:

        # Check email
        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE email = %s
            """,
            (request.email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="User with this email already exists"
            )

        # Hash password
        password_hash = bcrypt.hashpw(
            request.password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        # Create admin
        cursor.execute(
            """
            INSERT INTO users (
                email,
                password_hash,
                name,
                is_verified,
                role
            )
            VALUES (
                %s,
                %s,
                %s,
                TRUE,
                'admin'
            )
            RETURNING id, email, name, role
            """,
            (
                request.email,
                password_hash,
                request.name
            )
        )

        new_admin = cursor.fetchone()

        db.commit()

        return {
            "success": True,
            "message": "Admin created successfully",
            "user": {
                "id": str(new_admin[0]),
                "email": new_admin[1],
                "name": new_admin[2],
                "role": new_admin[3]
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        cursor.close()
        db.close()


# ============================================================
# ADMIN STATS
# ============================================================

@router.get("/admin/stats")
def get_admin_stats(
    current_user: dict = Depends(require_admin)
):

    db = get_db()
    cursor = db.cursor()

    try:

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_users,

                COUNT(*)
                FILTER (
                    WHERE role = 'user'
                ) AS normal_users,

                COUNT(*)
                FILTER (
                    WHERE role = 'admin'
                ) AS admins,

                COUNT(*)
                FILTER (
                    WHERE role = 'super_admin'
                ) AS super_admins,

                COUNT(*)
                FILTER (
                    WHERE is_verified = TRUE
                ) AS verified_users,

                COUNT(*)
                FILTER (
                    WHERE is_verified = FALSE
                ) AS unverified_users

            FROM users
            """
        )

        stats = cursor.fetchone()

        return {
            "success": True,
            "stats": {
                "total_users": stats[0],
                "normal_users": stats[1],
                "admins": stats[2],
                "super_admins": stats[3],
                "verified_users": stats[4],
                "unverified_users": stats[5]
            }
        }

    finally:
        cursor.close()
        db.close()