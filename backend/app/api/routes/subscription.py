from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from typing import List, Optional

from ...core.security import get_current_user, UserContext
from ...services.subscription_service import (
    SUBSCRIPTION_PLANS,
    SubscriptionService,
    get_subscription_service,
)


router = APIRouter(prefix="/api/subscription", tags=["subscription"])


class CheckoutRequest(BaseModel):
    plan: str


class ApiKeyResponse(BaseModel):
    id: str
    name: Optional[str] = None
    created_at: str
    last_used_at: Optional[str] = None


class CreateApiKeyRequest(BaseModel):
    name: Optional[str] = None


def get_subscription_service_dep() -> SubscriptionService:
    return get_subscription_service()


@router.get("/plans")
async def list_plans() -> dict:
    return SUBSCRIPTION_PLANS


@router.get("")
async def get_subscription(
    current_user: UserContext = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service_dep),
) -> dict:
    plan = service.get_user_plan(current_user.id)
    payload = SUBSCRIPTION_PLANS.get(plan, {})
    return {"plan": plan, "features": payload.get("features", []), "price": payload.get("price")}


@router.get("/usage")
async def get_usage(
    current_user: UserContext = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service_dep),
) -> dict:
    return service.get_usage(current_user.id)


@router.post("/checkout", status_code=status.HTTP_201_CREATED)
async def create_checkout(
    body: CheckoutRequest,
    current_user: UserContext = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service_dep),
) -> dict:
    try:
        session = service.create_checkout_session(current_user.id, body.plan)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return session


@router.post("/webhook/lemonsqueezy", status_code=status.HTTP_202_ACCEPTED)
async def handle_webhook(
    payload: dict,
    service: SubscriptionService = Depends(get_subscription_service_dep),
) -> dict:
    return service.handle_webhook(payload)


@router.get("/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    current_user: UserContext = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service_dep),
) -> List[ApiKeyResponse]:
    try:
        service.require_feature(current_user.id, "api_access")
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    keys = service.list_api_keys(current_user.id)
    return [ApiKeyResponse(**item) for item in keys]


@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: CreateApiKeyRequest,
    current_user: UserContext = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service_dep),
) -> dict:
    try:
        result = service.create_api_key(current_user.id, name=payload.name)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return result


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: str,
    current_user: UserContext = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service_dep),
) -> Response:
    try:
        service.require_feature(current_user.id, "api_access")
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    service.delete_api_key(current_user.id, key_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

