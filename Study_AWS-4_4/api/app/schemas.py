from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .models import TaskStatus


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.pending


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: TaskStatus
    createdAt: datetime
    updatedAt: datetime


class ErrorResponse(BaseModel):
    message: str
    errorCode: Optional[str] = None
    requestId: Optional[str] = None
