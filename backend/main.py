"""FastAPI application entrypoint, lifespan manager, middleware, and router mounting."""

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.dependencies import (
    get_db_manager,
    get_metrics_service,
    get_gemini_client,
)
from backend.api.routes import (
    chat_router,
    metrics_router,
    health_router,
    conversations_router,
)
from backend.services.idempotency import IdempotencyConflictError

# Configure minimal clean logging without credentials
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("iimbx_helpdesk")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: startup database initialization and shutdown cleanup."""
    logger.info("Initializing IIMBx Helpdesk backend services...")
    db_mgr = get_db_manager()
    await db_mgr.initialize()

    metrics_svc = get_metrics_service()
    await metrics_svc.initialize_metrics()

    logger.info("Database WAL and system metrics ready.")
    yield
    logger.info("Shutting down IIMBx Helpdesk backend services...")
    gemini_client = get_gemini_client()
    await gemini_client.close()
    logger.info("Cleanup complete.")


def create_app() -> FastAPI:
    """Create and configure FastAPI instance."""
    app = FastAPI(
        title="IIMBx Course Helpdesk API",
        description="Official course policy assistant for DPM-101",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Security Headers Middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # Exception Handlers: Safe, non-leaking error responses
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation Error",
                "detail": "Invalid request parameters or payload format.",
            },
        )

    @app.exception_handler(IdempotencyConflictError)
    async def idempotency_conflict_handler(request: Request, exc: IdempotencyConflictError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "Idempotency Conflict",
                "detail": str(exc),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        err_name = "Idempotency Conflict" if exc.status_code == 409 else "HTTP Error"
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": err_name,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception during request processing: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "detail": "An unexpected server error occurred. Please try again later.",
            },
        )

    # Register API Routers
    app.include_router(chat_router)
    app.include_router(metrics_router)
    app.include_router(health_router)
    app.include_router(conversations_router)

    # Mount static assets if directory exists
    css_dir = FRONTEND_DIR / "css"
    js_dir = FRONTEND_DIR / "js"
    if css_dir.exists():
        app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")
    if js_dir.exists():
        app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")

    # Serve chatbot frontend
    @app.get("/", include_in_schema=False)
    async def serve_index():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Frontend index.html not found."},
        )

    return app


app = create_app()
