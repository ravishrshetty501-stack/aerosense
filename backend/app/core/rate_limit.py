import time
from typing import Dict, List, Tuple
from fastapi import Request, HTTPException, status

class InMemoryRateLimiter:
    """
    Sliding-window in-memory rate limiter for FastAPI endpoints.
    Protects sensitive operations (AI queries, login attempts, report generation)
    from automated abuse, credential stuffing, and DoS attacks.
    """
    def __init__(self, requests_limit: int = 30, window_seconds: int = 60):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        # Mapping: client_identifier -> list of timestamps
        self._history: Dict[str, List[float]] = {}
        self._last_cleanup = time.time()

    def _cleanup_old_records(self, now: float) -> None:
        """Periodic garbage collection of expired timestamps every 60s."""
        if now - self._last_cleanup < 60:
            return
        self._last_cleanup = now
        expired_before = now - self.window_seconds
        keys_to_delete = []
        for client, timestamps in self._history.items():
            valid = [ts for ts in timestamps if ts > expired_before]
            if valid:
                self._history[client] = valid
            else:
                keys_to_delete.append(client)
        for k in keys_to_delete:
            self._history.pop(k, None)

    async def __call__(self, request: Request) -> None:
        now = time.time()
        self._cleanup_old_records(now)

        # Identify client by forward headers (for proxy/load balancer) or socket IP
        client_ip = (
            request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or request.headers.get("x-real-ip")
            or (request.client.host if request.client else "unknown")
        )

        window_start = now - self.window_seconds
        timestamps = self._history.get(client_ip, [])
        # Keep only timestamps inside current sliding window
        valid_timestamps = [ts for ts in timestamps if ts > window_start]

        if len(valid_timestamps) >= self.requests_limit:
            retry_after = int(self.window_seconds - (now - valid_timestamps[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: Maximum {self.requests_limit} requests per {self.window_seconds}s. Try again in {retry_after}s.",
                headers={"Retry-After": str(max(1, retry_after))}
            )

        valid_timestamps.append(now)
        self._history[client_ip] = valid_timestamps

# Pre-configured rate limiter instances for different route sensitivity levels
ai_chat_limiter = InMemoryRateLimiter(requests_limit=25, window_seconds=60)
auth_limiter = InMemoryRateLimiter(requests_limit=10, window_seconds=60)
report_limiter = InMemoryRateLimiter(requests_limit=15, window_seconds=60)
