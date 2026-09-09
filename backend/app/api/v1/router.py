"""API v1 Router registry."""

from fastapi import APIRouter

from app.api.v1.audit import router as audit_router
from app.api.v1.health import router as health_router
from app.api.v1.tenants import router as tenants_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(tenants_router)
api_v1_router.include_router(audit_router)
