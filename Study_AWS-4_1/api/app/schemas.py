from datetime import datetime

from pydantic import BaseModel, Field

from .models import TaskStatus


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatus = TaskStatus.pending


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    status: TaskStatus
    createdAt: datetime
    updatedAt: datetime


class ErrorResponse(BaseModel):
    message: str
    errorCode: str | None = None
    requestId: str | None = None
