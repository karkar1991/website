import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .config import settings
from .routers import admin, auth, finance, members, options, reports
from .security import hash_password

log = logging.getLogger("member_admin")


def bootstrap_admin() -> None:
    """Give the seeded admin a real password on first start (hash 'CHANGE_ME')."""
    with db.pool.connection() as conn:
        row = conn.execute("SELECT id, password_hash FROM admin_users WHERE username = %s",
                           (settings.admin_username,)).fetchone()
        if row and row["password_hash"] == "CHANGE_ME":
            if not settings.admin_password:
                log.warning("ADMIN_PASSWORD is empty: admin '%s' cannot log in yet", settings.admin_username)
                return
            conn.execute("UPDATE admin_users SET password_hash = %s WHERE id = %s",
                         (hash_password(settings.admin_password), row["id"]))
            log.warning("Initial password set for admin '%s'", settings.admin_username)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if db.pool is None:
        db.init_pool(settings.database_url)
    bootstrap_admin()
    yield
    db.close_pool()


app = FastAPI(title="Member Admin API", version="1.0.0", lifespan=lifespan,
              docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")

if settings.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

for r in (auth, options, members, finance, reports, admin):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    with db.pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"ok": True}
