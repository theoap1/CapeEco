"""
Siteline API — FastAPI backend serving PostGIS data + AI analysis
for South African property development intelligence.

Route modules:
  api/routes/search.py      — GET /api/search
  api/routes/properties.py  — GET /api/property/{id}/*
  api/routes/comparison.py  — GET /api/property/{id}/compare/*
  api/routes/layers.py      — GET /api/layers/*
  api/routes/reports.py     — GET /api/property/{id}/report
  api/routes/ai.py          — POST /api/ai/analyze
  api/routes/chat.py        — POST /api/ai/chat (SSE streaming)
  api/routes/v1.py          — /api/v1/* public API
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text

from api.db import init_engine, ensure_tables, get_engine, SCHEMA
from api.auth import (
    UserCreate, UserLogin, UserResponse, Token,
    hash_password, verify_password, create_access_token, get_current_user,
)

logger = logging.getLogger("siteline")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine()
    ensure_tables()
    logger.info("Siteline API started")
    yield
    engine = get_engine()
    if engine:
        engine.dispose()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = FastAPI(title="Siteline API", version="2.0.0", lifespan=lifespan)

ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if os.environ.get("ENVIRONMENT") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ---------------------------------------------------------------------------
# Auth endpoints (kept in main for backward compat)
# ---------------------------------------------------------------------------
@app.post("/api/auth/register", response_model=Token)
def auth_register(body: UserCreate):
    """Create a new user account."""
    email = body.email.strip().lower()
    if not email or "@" not in email:
        from fastapi import HTTPException
        raise HTTPException(400, "Invalid email address")
    if len(body.password) < 6:
        from fastapi import HTTPException
        raise HTTPException(400, "Password must be at least 6 characters")

    hashed = hash_password(body.password)
    engine = get_engine()
    with engine.connect() as conn:
        exists = conn.execute(
            text(f"SELECT id FROM {SCHEMA}.users WHERE email = :email"),
            {"email": email},
        ).fetchone()
        if exists:
            from fastapi import HTTPException
            raise HTTPException(409, "Email already registered")

        row = conn.execute(
            text(f"""
                INSERT INTO {SCHEMA}.users (email, hashed_password, full_name)
                VALUES (:email, :hashed, :name)
                RETURNING id, email, full_name, is_active, created_at
            """),
            {"email": email, "hashed": hashed, "name": body.full_name},
        ).fetchone()
        conn.commit()

    user = dict(row._mapping)
    token = create_access_token({"sub": str(user["id"])})
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.post("/api/auth/login", response_model=Token)
def auth_login(body: UserLogin):
    """Authenticate and return a JWT token."""
    email = body.email.strip().lower()
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT id, email, full_name, is_active, created_at, hashed_password FROM {SCHEMA}.users WHERE email = :email"),
            {"email": email},
        ).fetchone()

    if not row:
        from fastapi import HTTPException
        raise HTTPException(401, "Invalid email or password")

    user = dict(row._mapping)
    if not verify_password(body.password, user.pop("hashed_password")):
        from fastapi import HTTPException
        raise HTTPException(401, "Invalid email or password")

    if not user["is_active"]:
        from fastapi import HTTPException
        raise HTTPException(403, "Account disabled")

    token = create_access_token({"sub": str(user["id"])})
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.get("/api/auth/me", response_model=UserResponse)
def auth_me(current_user: dict = Depends(get_current_user)):
    """Return the current authenticated user."""
    return current_user


# ---------------------------------------------------------------------------
# Mount route modules
# ---------------------------------------------------------------------------
from api.routes.search import router as search_router
from api.routes.properties import router as properties_router
from api.routes.comparison import router as comparison_router
from api.routes.layers import router as layers_router
from api.routes.reports import router as reports_router
from api.routes.ai import router as ai_router
from api.routes.v1 import router as v1_router
from api.routes.chat import router as chat_router
from api.routes.newdata import router as newdata_router
from api.routes.conversations import router as conversations_router

app.include_router(search_router)
app.include_router(properties_router)
app.include_router(comparison_router)
app.include_router(layers_router)
app.include_router(reports_router)
app.include_router(ai_router)
app.include_router(v1_router)
app.include_router(chat_router)
app.include_router(newdata_router)
app.include_router(conversations_router)


# ---------------------------------------------------------------------------
# Serve frontend static files in production
# ---------------------------------------------------------------------------
_FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if _FRONTEND_DIR.is_dir():
    from fastapi.responses import FileResponse

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file = _FRONTEND_DIR / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(_FRONTEND_DIR / "index.html")

    logger.info("Serving frontend from %s", _FRONTEND_DIR)
