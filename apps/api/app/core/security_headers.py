# 文件说明：核心基础设施：security_headers。
from fastapi import FastAPI, Request
from fastapi.responses import Response

from app.core.config import Settings


def install_security_headers(app: FastAPI, settings: Settings) -> None:
    @app.middleware("http")
    async def security_headers(request: Request, call_next: object) -> Response:
        response = await call_next(request)  # type: ignore[operator]
        if settings.security_headers_enabled and request.url.path.startswith("/api/"):
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault(
                "Permissions-Policy",
                "camera=(), microphone=(), geolocation=(self)",
            )
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            )
            response.headers.setdefault(
                "Cross-Origin-Resource-Policy",
                "same-site",
            )
        return response
