import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api import admin, admin_config, auth, customer, messages, provider, public, webhooks
from app.core.config import get_settings
from app.core.db import engine
from app.core.errors import install_error_handlers
from app.core.ratelimit import limiter


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"), "level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        for k in ("request_id", "method", "path", "status", "ms"):
            if hasattr(record, k):
                data[k] = getattr(record, k)
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data)


def configure_logging() -> None:
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [h]
    root.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    s = get_settings()
    dsn = __import__("os").environ.get("SENTRY_DSN")
    if dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=dsn, environment=s.env, traces_sample_rate=0.1, send_default_pii=False)
        except ImportError:
            logging.getLogger("roanwick").warning("SENTRY_DSN set but sentry-sdk is not installed")
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Roanwick API", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None,
        description="REST API for the Roanwick home-services marketplace. Amounts are integer pence (GBP). Times are ISO 8601 with offsets; working hours are Europe/London local time.",
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    install_error_handlers(app)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID"])

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = rid
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if s.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith("/api/v1/auth") or request.url.path.startswith("/api/v1/admin"):
            response.headers["Cache-Control"] = "no-store"
        logging.getLogger("roanwick.access").info(
            "request", extra={"request_id": rid, "method": request.method, "path": request.url.path, "status": response.status_code, "ms": round((time.perf_counter() - t0) * 1000)}
        )
        return response

    @app.get("/health", tags=["Operations"], include_in_schema=False)
    def health():
        return {"status": "ok"}

    @app.get("/ready", tags=["Operations"], include_in_schema=False)
    def ready():
        with engine.connect() as c:
            c.execute(text("select 1"))
        return {"status": "ready"}

    for r in (auth.router, public.router, customer.router, provider.router, messages.router, admin.router, admin_config.router, webhooks.router):
        app.include_router(r, prefix="/api/v1")
    return app


app = create_app()
