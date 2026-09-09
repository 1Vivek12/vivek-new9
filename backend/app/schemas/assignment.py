"""Assignment Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AssignmentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    priority: str = Field(default="NORMAL")
    assigned_to_user_id: Optional[str] = None
    due_date: Optional[datetime] = None


class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    priority: Optional[str] = None
    status: Optional[str] = None
    assigned_to_user_id: Optional[str] = None
    due_date: Optional[datetime] = None


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    title: str
    description: Optional[str] = None
    priority: str
    status: str
    assigned_to_user_id: Optional[str] = None
    created_by_user_id: str
    due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
