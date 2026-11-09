import os
import jwt
from typing import Optional
from fastapi import Header, HTTPException, status
from ..config import settings


def get_current_user_id(authorization: Optional[str] = Header(default=None)) -> str:
    """
    Validates Supabase Bearer JWT tokens.
    In development mode or when AUTH_ENFORCE_JWT is false, allows demo sessions
    or falls back to a deterministic demo user ID ('demo-candidate-001').
    """
    if not authorization:
        if settings.AUTH_ENFORCE_JWT:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Authorization header with Bearer token",
            )
        return "demo-candidate-001"

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Must be 'Bearer <token>'",
        )

    token = parts[1]

    # If Supabase JWT Secret is provided, decode and verify claims
    if settings.SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="JWT token missing 'sub' subject claim",
                )
            return user_id
        except jwt.PyJWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"JWT verification failed: {str(e)}",
            )

    # In dev mode without secret, unverified decode or fallback sub claim
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
        return unverified.get("sub", "demo-candidate-001")
    except Exception:
        if settings.AUTH_ENFORCE_JWT:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format",
            )
        return "demo-candidate-001"

