import logging
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, engine, get_db
from .logging_config import configure_logging, request_id_var
from .models import Task, TaskStatus
from .schemas import ErrorResponse, TaskInput, TaskResponse

configure_logging(settings.log_level)
logger = logging.getLogger("task_api")

app = FastAPI(title="Task Management API", version="1.0.0")


class ApiError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid4()))
    token = request_id_var.set(request_id)
    started_at = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception(
            "request_unhandled_exception",
            extra={
                "_method": request.method,
                "_path": request.url.path,
                "_latencyMs": elapsed_ms,
                "_errorCode": "UNHANDLED_EXCEPTION",
            },
        )
        request_id_var.reset(token)
        raise

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    log_method = logger.error if response.status_code >= 500 else logger.info
    log_method(
        "request_completed",
        extra={
            "_method": request.method,
            "_path": request.url.path,
            "_statusCode": response.status_code,
            "_latencyMs": elapsed_ms,
        },
    )
    response.headers["x-request-id"] = request_id
    request_id_var.reset(token)
    return response


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    log_method = logger.error if exc.status_code >= 500 else logger.warning
    log_method(
        "api_error",
        extra={
            "_statusCode": exc.status_code,
            "_errorCode": exc.error_code,
            "_handled": True,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "message": exc.message,
            "errorCode": exc.error_code,
            "requestId": request_id_var.get(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "internal_server_error",
        extra={
            "_statusCode": 500,
            "_errorCode": "INTERNAL_SERVER_ERROR",
            "_handled": False,
        },
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={
            "message": "内部サーバーエラー",
            "errorCode": "INTERNAL_SERVER_ERROR",
            "requestId": request_id_var.get(),
        },
    )


@app.on_event("startup")
def startup() -> None:
    # Local practice helper. In AWS, run migrations from the bastion instead.
    Base.metadata.create_all(bind=engine)


def to_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        status=TaskStatus(task.status),
        createdAt=task.created_at,
        updatedAt=task.updated_at,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/debug/error", response_model=ErrorResponse)
def debug_error() -> ErrorResponse:
    if not settings.enable_debug_error_endpoint:
        raise ApiError(status_code=404, error_code="DEBUG_ROUTE_DISABLED", message="デバッグ用エンドポイントは無効です")
    raise RuntimeError("Intentional error for CloudWatch Logs Insights practice")


@app.get("/api/tasks", response_model=list[TaskResponse])
def list_tasks(status: TaskStatus | None = None, db: Session = Depends(get_db)) -> list[TaskResponse]:
    stmt = select(Task)
    if status is not None:
        stmt = stmt.where(Task.status == status.value)
    tasks = db.scalars(stmt.order_by(Task.id)).all()
    return [to_response(task) for task in tasks]


@app.post("/api/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskInput, db: Session = Depends(get_db)) -> TaskResponse:
    task = Task(title=payload.title, description=payload.description, status=payload.status.value)
    db.add(task)
    db.commit()
    db.refresh(task)
    return to_response(task)


@app.get("/api/tasks/{task_id}", response_model=TaskResponse, responses={404: {"model": ErrorResponse}})
def get_task(task_id: int, db: Session = Depends(get_db)) -> TaskResponse:
    task = db.get(Task, task_id)
    if task is None:
        raise ApiError(status_code=404, error_code="TASK_NOT_FOUND", message="タスクが見つかりません")
    return to_response(task)


@app.put("/api/tasks/{task_id}", response_model=TaskResponse, responses={404: {"model": ErrorResponse}})
def update_task(task_id: int, payload: TaskInput, db: Session = Depends(get_db)) -> TaskResponse:
    task = db.get(Task, task_id)
    if task is None:
        raise ApiError(status_code=404, error_code="TASK_NOT_FOUND", message="タスクが見つかりません")

    task.title = payload.title
    task.description = payload.description
    task.status = payload.status.value
    db.commit()
    db.refresh(task)
    return to_response(task)


@app.delete("/api/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, responses={404: {"model": ErrorResponse}})
def delete_task(task_id: int, db: Session = Depends(get_db)) -> Response:
    task = db.get(Task, task_id)
    if task is None:
        raise ApiError(status_code=404, error_code="TASK_NOT_FOUND", message="タスクが見つかりません")

    db.delete(task)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
