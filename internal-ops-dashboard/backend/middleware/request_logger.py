import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.utils.logger import app_logger, log_structured


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        level = "info" if response.status_code < 400 else "warning"
        if response.status_code >= 500:
            level = "error"

        log_structured(
            app_logger, level, "http_request",
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response