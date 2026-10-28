"""Two local bearer-token roles. No credentials in API output or request logs."""
from collections import defaultdict, deque
from hmac import compare_digest
import os
import time

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


def configured_tokens():
    tokens = {role: os.getenv(f"LEDGERSHIELD_{role.upper()}_TOKEN", "")
              for role in ("operator", "admin")}
    for token in tokens.values():
        if token and len(token) < 32:
            raise ValueError("Configured API tokens must contain at least 32 characters")
    if tokens["operator"] and tokens["operator"] == tokens["admin"]:
        raise ValueError("Operator and admin must use distinct tokens")
    return tokens


async def principal(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    tokens = request.app.state.tokens
    if not any(tokens.values()):
        raise HTTPException(503, detail="authentication_unconfigured")
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, detail="authentication_required", headers={"WWW-Authenticate": "Bearer"})
    # Header bytes can be non-ASCII; compare_digest(str) requires ASCII.
    supplied = credentials.credentials.encode("utf-8")
    for role, token in tokens.items():
        if token and compare_digest(supplied, token.encode("utf-8")):
            return role
    raise HTTPException(401, detail="invalid_credentials", headers={"WWW-Authenticate": "Bearer"})


def require_role(minimum="operator"):
    async def authorized(role: str = Depends(principal)):
        if minimum == "admin" and role != "admin":
            raise HTTPException(403, detail="admin_role_required")
        return role
    return authorized


class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(deque)

    def check(self, principal_id, scope, limit=60, window=60):
        now = time.monotonic()
        queue = self.requests[principal_id, scope]
        while queue and queue[0] <= now - window:
            queue.popleft()
        if len(queue) >= limit:
            retry = max(1, int(window - (now - queue[0])) + 1)
            raise HTTPException(429, detail="rate_limit_exceeded", headers={"Retry-After": str(retry)})
        queue.append(now)


async def operator(request: Request, role: str = Depends(require_role())):
    request.app.state.limiter.check(role, "mutations")
    return role


async def admin(request: Request, role: str = Depends(require_role("admin"))):
    request.app.state.limiter.check(role, "mutations")
    return role
