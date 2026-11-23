from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging_config import setup_logging
from app.core.middleware import register_request_middleware
from app.dependencies.db import DbSession
from app.routers import auth as auth_router
from app.routers import debug as debug_router
from app.routers import auth as auth_router
from app.routers import customers as customers_router
from app.routers import debug as debug_router
from app.routers import users as users_router
from app.routers import tasks as tasks_router

setup_logging()

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "Backend API for AI Employee OS. Log in with POST /api/v1/auth/login, then click "
        "**Authorize** and paste the access_token."
    ),
)

# Order matters. Middleware added LAST is the OUTERMOST layer, so CORS wraps everything.
register_request_middleware(app)  # request id + request log line
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],  # lets frontend JavaScript read the request id
)

register_exception_handlers(app)

API_PREFIX = "/api/v1"
app.include_router(auth_router.router, prefix=API_PREFIX)
if settings.is_development:
    app.include_router(debug_router.router, prefix=API_PREFIX)
    app.include_router(auth_router.router, prefix=API_PREFIX)
app.include_router(users_router.router, prefix=API_PREFIX)
app.include_router(customers_router.router, prefix=API_PREFIX)
app.include_router(tasks_router.router, prefix=API_PREFIX)

@app.get(f"{API_PREFIX}/health", tags=["Health"])
def health(db: DbSession):
    db.execute(text("SELECT 1"))  # if the database is down this becomes a 503 (see error_handlers)
    return {
        "success": True,
        "message": "OK",
        "data": {"status": "healthy", "database": "connected"},
    }