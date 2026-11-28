from collections import OrderedDict
import ipaddress
import logging
import math
import os
import time
from typing import Any, Iterable, List, Optional, Tuple, Union
from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
IPNetwork = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]


def _parse_ip(value: Optional[str]) -> Optional[IPAddress]:
    """Parses and validates a candidate IPv4/IPv6 address, returning None if malformed."""
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or len(candidate) > 64:
        return None
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


def _parse_trusted_networks(raw_entries: Optional[Iterable[str]]) -> Tuple[IPNetwork, ...]:
    """Converts trusted proxy IPs or CIDR blocks into immutable network objects."""
    if not raw_entries:
        return ()
    networks: List[IPNetwork] = []
    for entry in raw_entries:
        if not isinstance(entry, str):
            continue
        cleaned = entry.strip()
        if not cleaned:
            continue
        try:
            networks.append(ipaddress.ip_network(cleaned, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid trusted proxy network entry: %r", cleaned)
    return tuple(networks)


def _validate_positive_int(value: Any, name: str) -> int:
    """Validates that `value` is a strictly positive int (rejecting bool and floats)."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _validate_positive_finite_number(value: Any, name: str) -> Union[int, float]:
    """Validates that `value` is a positive finite int or float (rejecting bool and non-finite values)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive finite number")
    try:
        numeric = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} must be a positive finite number") from exc
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return value


class InMemoryRateLimiter:
    """
    Sliding-window in-memory rate limiter for FastAPI endpoints.
    Protects sensitive operations (AI queries, login attempts, report generation)
    from automated abuse, credential stuffing, and DoS attacks.

    Capacity-Exhaustion Policy:
    - Bounded per-IP history holds up to `max_clients` active IP keys in `_history`.
    - Active (unexpired) client records in `_history` are NEVER evicted before their
      window expires, preventing high-cardinality traffic from resetting active quotas.
    - When `_history` reaches `max_clients` and cooldown-gated expired-record reclamation
      leaves `_history` full, unseen client IPs are routed to a single shared bounded
      overflow bucket (`_overflow_timestamps`) enforcing the same `requests_limit` /
      `window_seconds` sliding window and HTTP 429 + `Retry-After` contract.
    """
    def __init__(
        self,
        requests_limit: int = 30,
        window_seconds: Union[int, float] = 60,
        trusted_proxies: Optional[Iterable[str]] = None,
        max_clients: int = 10000,
    ):
        self.requests_limit = _validate_positive_int(requests_limit, "requests_limit")
        self.window_seconds = _validate_positive_finite_number(window_seconds, "window_seconds")
        self.max_clients = _validate_positive_int(max_clients, "max_clients")

        if trusted_proxies is None:
            env_proxies = os.getenv("RATE_LIMIT_TRUSTED_PROXIES") or os.getenv("TRUSTED_PROXIES") or ""
            raw_proxies: Iterable[str] = [p for p in env_proxies.split(",") if p.strip()]
        else:
            raw_proxies = trusted_proxies
        self._trusted_networks: Tuple[IPNetwork, ...] = _parse_trusted_networks(raw_proxies)

        # Bounded per-IP active history plus a single bounded overflow window list.
        self._history: "OrderedDict[str, List[float]]" = OrderedDict()
        self._overflow_timestamps: List[float] = []

        now = time.time()
        self._cleanup_interval = max(1.0, min(60.0, float(self.window_seconds)))
        self._capacity_cleanup_cooldown = max(1.0, min(5.0, float(self.window_seconds)))
        self._last_cleanup = now
        self._last_capacity_cleanup = 0.0

    def _is_trusted_proxy(self, addr: Optional[IPAddress]) -> bool:
        return addr is not None and any(addr in net for net in self._trusted_networks)

    def _extract_client_ip(self, request: Request) -> str:
        """
        Resolves the client identifier for rate limiting.
        Forwarding headers are ignored unless the immediate TCP peer is an explicitly
        configured trusted proxy. Only X-Forwarded-For is consulted (right-to-left),
        failing closed to the validated peer IP on missing, empty, trusted-only, or
        malformed headers; X-Real-IP is never trusted.
        """
        peer_raw = request.client.host if getattr(request, "client", None) else None
        peer_addr = _parse_ip(peer_raw)
        fallback_peer = str(peer_addr) if peer_addr is not None else "unknown"

        if not self._is_trusted_proxy(peer_addr):
            return fallback_peer

        headers = getattr(request, "headers", None) or {}
        xff_raw = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For") or ""
        if isinstance(xff_raw, str) and xff_raw.strip():
            for raw_hop in reversed(xff_raw.split(",")):
                if not raw_hop.strip():
                    continue
                hop_ip = _parse_ip(raw_hop)
                if hop_ip is None:
                    return fallback_peer
                if self._is_trusted_proxy(hop_ip):
                    continue
                return str(hop_ip)

        return fallback_peer

    def _purge_expired_records(self, now: float) -> None:
        """Scans tracked buckets once to reclaim keys whose timestamps have all expired."""
        self._last_cleanup = now
        self._last_capacity_cleanup = now
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
        self._overflow_timestamps = [ts for ts in self._overflow_timestamps if ts > expired_before]

    def _cleanup_old_records(self, now: float) -> None:
        """Periodic garbage collection gated strictly by `_cleanup_interval`."""
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._purge_expired_records(now)

    def _consume_window_slot(self, timestamps: List[float], now: float, window_start: float) -> List[float]:
        """Prunes expired timestamps for a single bucket and records the request or raises 429."""
        valid_timestamps = [ts for ts in timestamps if ts > window_start]
        if len(valid_timestamps) >= self.requests_limit:
            retry_after = int(self.window_seconds - (now - valid_timestamps[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: Maximum {self.requests_limit} requests per {self.window_seconds}s. Try again in {retry_after}s.",
                headers={"Retry-After": str(max(1, retry_after))}
            )
        valid_timestamps.append(now)
        return valid_timestamps

    async def __call__(self, request: Request) -> None:
        now = time.time()
        self._cleanup_old_records(now)

        client_ip = self._extract_client_ip(request)
        window_start = now - self.window_seconds

        if client_ip in self._history:
            self._history[client_ip] = self._consume_window_slot(self._history[client_ip], now, window_start)
            return

        if len(self._history) >= self.max_clients:
            if now - self._last_capacity_cleanup >= self._capacity_cleanup_cooldown:
                self._purge_expired_records(now)

        if len(self._history) < self.max_clients:
            self._history[client_ip] = self._consume_window_slot([], now, window_start)
            return

        # Capacity remains exhausted by active records: route unseen identity to shared overflow bucket.
        self._overflow_timestamps = self._consume_window_slot(self._overflow_timestamps, now, window_start)

# Pre-configured rate limiter instances for different route sensitivity levels
ai_chat_limiter = InMemoryRateLimiter(requests_limit=25, window_seconds=60)
auth_limiter = InMemoryRateLimiter(requests_limit=10, window_seconds=60)
report_limiter = InMemoryRateLimiter(requests_limit=15, window_seconds=60)
