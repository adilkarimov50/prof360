"""Security middleware: rate limiting and security headers."""
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Simple in-memory rate limiter (per IP)
_buckets: dict[str, list[float]] = defaultdict(list)
_LIMIT = 120  # requests
_WINDOW = 60  # seconds


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.startswith("/api/"):
            ip = request.client.host if request.client else "unknown"
            now = time.time()
            bucket = _buckets[ip]
            _buckets[ip] = [t for t in bucket if now - t < _WINDOW]
            if len(_buckets[ip]) >= _LIMIT:
                return Response("Rate limit exceeded", status_code=429)
            _buckets[ip].append(now)

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
