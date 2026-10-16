from collections import OrderedDict, deque
from math import ceil
from threading import Lock
from time import monotonic

from starlette.responses import JSONResponse


CONTENT_SECURITY_POLICY = (
    "default-src 'none'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "img-src 'self' data: https:; "
    "font-src 'self' https://fonts.gstatic.com; "
    "connect-src 'self'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class RequestBodySizeLimitMiddleware:
    def __init__(self, app, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_lengths = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"content-length"
        ]
        if content_lengths:
            try:
                declared_length = int(content_lengths[0])
                if declared_length < 0 or len(set(content_lengths)) != 1:
                    raise ValueError
            except ValueError:
                response = JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header."},
                    headers=SECURITY_HEADERS,
                )
                await response(scope, receive, send)
                return
            if declared_length > self.max_body_bytes:
                await self._send_too_large(scope, receive, send)
                return

        buffered_messages = []
        body_size = 0
        while True:
            message = await receive()
            buffered_messages.append(message)
            if message["type"] != "http.request":
                break

            body_size += len(message.get("body", b""))
            if body_size > self.max_body_bytes:
                await self._send_too_large(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        message_index = 0

        async def replay_receive():
            nonlocal message_index
            if message_index < len(buffered_messages):
                message = buffered_messages[message_index]
                message_index += 1
                return message
            return await receive()

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _send_too_large(scope, receive, send) -> None:
        response = JSONResponse(
            status_code=413,
            content={"detail": "Request body is too large."},
            headers=SECURITY_HEADERS,
        )
        await response(scope, receive, send)


class SlidingWindowRateLimiter:
    def __init__(self, max_keys: int = 20_000) -> None:
        self._events: OrderedDict[str, deque[float]] = OrderedDict()
        self._windows: dict[str, int] = {}
        self._max_keys = max_keys
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = monotonic()
        with self._lock:
            events = self._events.get(key)
            if events is None:
                self._remove_expired(now, scan_all=len(self._events) >= self._max_keys)
                if len(self._events) >= self._max_keys:
                    return False, window_seconds
                events = deque()
                self._events[key] = events
            self._windows[key] = window_seconds

            self._prune(events, now, window_seconds)
            if len(events) >= limit:
                return False, max(1, ceil(events[0] + window_seconds - now))

            events.append(now)
            self._events.move_to_end(key)
            return True, 0

    def is_limited(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = monotonic()
        with self._lock:
            events = self._events.get(key)
            if events is None:
                return False, 0
            self._prune(events, now, window_seconds)
            if not events:
                del self._events[key]
                self._windows.pop(key, None)
                return False, 0
            if len(events) >= limit:
                return True, max(1, ceil(events[0] + window_seconds - now))
            return False, 0

    def record(self, key: str, window_seconds: int) -> None:
        now = monotonic()
        with self._lock:
            events = self._events.get(key)
            if events is None:
                self._remove_expired(now, scan_all=len(self._events) >= self._max_keys)
                if len(self._events) >= self._max_keys:
                    return
                events = deque()
                self._events[key] = events
            self._windows[key] = window_seconds
            self._prune(events, now, window_seconds)
            events.append(now)
            self._events.move_to_end(key)

    def clear_key(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)
            self._windows.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._windows.clear()

    def _remove_expired(self, now: float, *, scan_all: bool = False) -> None:
        keys = self._events if scan_all else list(self._events)[:256]
        for key in list(keys):
            events = self._events[key]
            self._prune(events, now, self._windows[key])
            if not events:
                del self._events[key]
                del self._windows[key]

    @staticmethod
    def _prune(events: deque[float], now: float, window_seconds: int) -> None:
        cutoff = now - window_seconds
        while events and events[0] <= cutoff:
            events.popleft()


rate_limiter = SlidingWindowRateLimiter()
