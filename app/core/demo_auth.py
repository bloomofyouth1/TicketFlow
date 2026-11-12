import hmac
import os

from fastapi import Request
from fastapi.responses import JSONResponse

def auth_required():
    return os.getenv(
        "TICKETFLOW_REQUIRE_AUTH", "0"
    ) == "1"

async def demo_auth_middleware(
    request: Request,
    call_next,
):
    # 容器健康检查不携带身份凭据。
    if request.url.path == "/health":
        return await call_next(request)

    if not auth_required():
        return await call_next(request)

    expected = os.getenv(
        "TICKETFLOW_ADMIN_TOKEN", ""
    )

    # 开启认证却未配置密钥时，拒绝访问。
    if len(expected) < 32:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Authentication is not configured"
            },
        )

    authorization = request.headers.get(
        "authorization", ""
    )

    scheme, _, supplied = authorization.partition(" ")

    valid = (
        scheme.lower() == "bearer"
        and bool(supplied)
        and hmac.compare_digest(
            supplied.encode("utf-8"),
            expected.encode("utf-8"),
        )
    )

    if not valid:
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response
