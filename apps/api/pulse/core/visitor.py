"""Who is asking — decided by the server, never taken from a client header.

- `session`: a random id in an HttpOnly cookie; it separates one visitor's documents, drafts and chat
  from another's (the demo is shared by everyone who opens the link).
- `quota`: a salted hash of the client IP; AI limits are counted on it, so clearing cookies or sending
  a made-up header does not reset them.
"""

import hashlib
import secrets
from dataclasses import dataclass

from fastapi import Request, Response

COOKIE = "pulse_sid"
_SALT = secrets.token_hex(8)  # per process: hashes cannot be matched back to addresses across restarts


@dataclass(frozen=True, slots=True)
class Visitor:
    session: str
    quota: str


def client_ip(request: Request) -> str:
    # nginx sets X-Real-IP; behind it the socket peer is always 127.0.0.1.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


def identify(request: Request) -> Visitor:
    session = request.cookies.get(COOKIE) or getattr(request.state, "new_session", "")
    if not session or len(session) > 64:
        session = "anon"
    quota = hashlib.sha256(f"{_SALT}:{client_ip(request)}".encode()).hexdigest()[:16]
    return Visitor(session=session, quota=quota)


def ensure_cookie(request: Request, response: Response) -> None:
    """Middleware hook: give a first-time visitor a session id (the same request already uses it)."""
    if not request.cookies.get(COOKIE):
        sid = getattr(request.state, "new_session", "") or secrets.token_urlsafe(16)
        https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
        response.set_cookie(COOKIE, sid, max_age=60 * 60 * 24 * 30, httponly=True, samesite="lax", secure=https)


def assign(request: Request) -> None:
    if not request.cookies.get(COOKIE):
        request.state.new_session = secrets.token_urlsafe(16)
