from __future__ import annotations

from fastapi import APIRouter, Depends

from ...core.security import UserContext, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=UserContext)
async def read_current_user(current_user: UserContext = Depends(get_current_user)) -> UserContext:
    return current_user

