"""The FastAPI application.

Assembly only: configuration, middleware, error handling, routes. No business
logic lives here, which is why the whole discovery pipeline can be exercised in
tests without an HTTP client.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import ROUTERS
from app.config import get_settings
from app.db.base import get_engine
from app.logging_config import Event, configure_logging, log_event
from app.security.ratelimit import SECURITY_HEADERS

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)

    # Configuration that is fatal in production and merely noteworthy locally.
    # Refusing to boot is the right response to a missing signing key in
    # production, and the wrong response on a developer's laptop.
    problems = settings.startup_problems()
    for problem in problems:
        log_event(logger, Event.CONFIG_PROBLEM, problem, level=logging.ERROR)
    if problems and settings.is_production:
        raise RuntimeError("Refusing to start: " + " | ".join(problems))

    log_event(
        logger,
        Event.API_STARTED,
        "api started",
        environment=settings.environment,
        database="postgres" if settings.uses_postgres else "sqlite",
        llm=settings.llm_provider.value if settings.llm_available else "none",
        live_search=settings.search_provider.value if settings.live_search_available else "none",
    )
    yield
    get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Money You're Missing",
        version="0.1.0",
        description=(
            "Personal opportunity-to-income engine for professionals in Germany. "
            "Opportunities come from real sources; scores are computed deterministically; "
            "unknown values stay unknown."
        ),
        lifespan=lifespan,
        # Docs stay available in development and are the fastest way for a
        # reviewer to see the whole surface. Disabled in production.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            log_event(
                logger,
                Event.UNHANDLED_ERROR,
                "unhandled error",
                level=logging.ERROR,
                request_id=request_id,
                path=request.url.path,
                method=request.method,
            )
            logger.exception("unhandled error")
            # Never leak an internal message or stack trace to a client.
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Something went wrong on our side. Your saved data is safe.",
                    "recovery": "Please try again in a moment.",
                },
            )
        response.headers["X-Request-ID"] = request_id
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Report which fields were wrong without echoing the values back.

        The input to these endpoints includes CV text and tax questions;
        FastAPI's default handler puts the offending value in the response, and
        from there into a client's error log.
        """
        fields = [".".join(str(part) for part in error["loc"][1:]) for error in exc.errors()]
        log_event(
            logger,
            Event.VALIDATION_ERROR,
            "request failed validation",
            level=logging.INFO,
            path=request.url.path,
            fields=fields,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Some fields are not valid: " + ", ".join(fields or ["request body"]),
                "fields": fields,
            },
        )

    for router in ROUTERS:
        app.include_router(router)
    return app


app = create_app()
