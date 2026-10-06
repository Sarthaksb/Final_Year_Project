"""
backend/main.py
----------------
FastAPI application entry point.

Lifespan:
  startup  — configure logging, connect MongoDB, initialise Beanie ODM
  shutdown — close Motor client

Middleware (applied in order):
  1. CORSMiddleware       — cross-origin headers
  2. RequestIDMiddleware  — X-Request-ID UUID on every request
  3. TimingLoggingMiddleware — logs method/path/status/ms

Routes:
  /api/auth/*       — register, login
  /api/diagnosis/*  — analyze image + symptoms
  /api/cases/*      — list, retrieve, delete patient cases
  /api/doctor/*     — doctor dashboard (role-gated)
  /api/health       — deep liveness probe (pings MongoDB)
  /api/me           — current user profile

CORS:
  Allow all origins in development (restrict in production).
"""

import logging
import traceback
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.database import close_db, init_db, get_motor_client
from core.logging_config import configure_logging
from core.middleware import RequestIDMiddleware, TimingLoggingMiddleware
from api.routes import auth, cases, diagnosis, doctor, lesions, admin
from api.dependencies import get_current_user

logger = logging.getLogger(__name__)

# Add project root to sys.path so we can import ml module
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: configure logging, init DB, and load ML model. Shutdown: close connection."""
    configure_logging()
    logger.info("Starting %s v%s [%s]", settings.app_name, "1.0.0", settings.environment)
    await init_db()
    logger.info("MongoDB initialised — database: %s", settings.mongo_db_name)

    # Load ML Model
    ckpt = settings.model_checkpoint_path
    if not ckpt or not Path(ckpt).exists():
        logger.warning("ML Model checkpoint missing at '%s'. Inference will return MODEL_UNAVAILABLE.", ckpt)
        app.state.ml_model = None
        app.state.ml_device = None
    else:
        try:
            from ml.classifier.predict import load_model
            logger.info("Loading ML Model from '%s'...", ckpt)
            model, device = load_model(ckpt)
            app.state.ml_model = model
            app.state.ml_device = device
            logger.info("ML Model loaded successfully and attached to app state.")
        except Exception as exc:
            logger.error("Failed to load ML Model: %s", exc)
            app.state.ml_model = None
            app.state.ml_device = None

    yield
    await close_db()
    logger.info("MongoDB connection closed. Shutdown complete.")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "## AI-Powered Smart Dermatology Diagnostic System\n\n"
        "**Stack:** EfficientNet-B0 classifier · LangGraph agent (Gemini) · ChromaDB RAG\n\n"
        "### Authentication\n"
        "All protected routes require `Authorization: Bearer <token>` header.\n"
        "Obtain a token via `POST /api/auth/login`.\n\n"
        "### Roles\n"
        "- **patient** — can upload images, view own cases\n"
        "- **doctor** — can view all cases, submit reviews, download PDF reports\n"
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "auth",      "description": "Register and login"},
        {"name": "diagnosis", "description": "Image upload + full AI pipeline"},
        {"name": "cases",     "description": "Patient case history"},
        {"name": "doctor",    "description": "Doctor dashboard (role-gated)"},
        {"name": "utility",   "description": "Health, ping, and user profile"},
    ],
)

# ── CORS ──────────────────────────────────────────────────────────────────────
_origins = (
    ["*"]
    if settings.environment == "development"
    else [
        "http://localhost:5173",
        "http://localhost:3000",
        # add your production domain here
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Custom middleware (order: outermost executed first) ───────────────────────
app.add_middleware(TimingLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

# ── Static files (uploaded images / Grad-CAM PNGs) ───────────────────────────
upload_dir = Path(settings.upload_dir)
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,      prefix=settings.api_prefix)
app.include_router(diagnosis.router, prefix=settings.api_prefix)
app.include_router(cases.router,     prefix=settings.api_prefix)
app.include_router(doctor.router,    prefix=settings.api_prefix)
app.include_router(lesions.router,   prefix=settings.api_prefix)
app.include_router(admin.router,     prefix=settings.api_prefix)


# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for unhandled exceptions.
    - Development: exposes traceback in response for easier debugging.
    - Production: returns generic message; traceback goes to logs only.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        "Unhandled exception [%s] %s %s — %s",
        request_id,
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )

    if settings.environment == "development":
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "exception": str(exc),
                "traceback": traceback.format_exc().splitlines()[-5:],
                "request_id": request_id,
            },
        )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. Please try again later.",
            "request_id": request_id,
        },
    )


# ── Utility endpoints ─────────────────────────────────────────────────────────

@app.get("/", tags=["utility"])
async def root():
    """API root — returns app info and useful links."""
    return {
        "app":         settings.app_name,
        "version":     "1.0.0",
        "environment": settings.environment,
        "docs":        "/docs",
        "redoc":       "/redoc",
        "health":      f"{settings.api_prefix}/health",
    }


@app.get(f"{settings.api_prefix}/health", tags=["utility"])
async def health_check():
    """
    Deep liveness / readiness probe.
    - Pings MongoDB to verify the connection is alive.
    - Returns HTTP 200 if healthy, HTTP 503 if the database is unreachable.
    """
    try:
        client = get_motor_client()
        await client.admin.command("ping")
        db_status = "connected"
    except Exception as exc:
        logger.error("Health check — DB ping failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status":  "degraded",
                "db":      "unreachable",
                "detail":  "MongoDB ping failed",
            },
        )

    return {
        "status":      "ok",
        "db":          db_status,
        "environment": settings.environment,
        "version":     "1.0.0",
    }


@app.get(f"{settings.api_prefix}/me", tags=["utility"])
async def me(current_user=Depends(get_current_user)):
    """
    Return the currently authenticated user's profile.
    Use this endpoint to validate a session token and get role/name for UI.
    """
    from schemas.user import UserOut
    return UserOut(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
    )
