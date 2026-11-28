"""Centralized credential redaction and safe exception formatting for logs, HTTP probes, and errors."""

from __future__ import annotations

import logging
import re
import traceback
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

REDACTED = "[REDACTED]"

_QUERY_SECRET_RE = re.compile(
    r"(?i)([?&](?:key|token|api_key|apikey|access_token|auth_token)=)([^&\s'\"\)\],;<>]+)"
)
_HEADER_SECRET_RE = re.compile(
    r"(?i)((?:x-goog-api-key|x-api-key|authorization)['\"]?\s*[:=]\s*['\"]?(?:Bearer\s+)?)([^'\"\s,\}\]\)]+)"
)
_BYTES_HEADER_RE = re.compile(
    r"(?i)(b['\"](?:x-goog-api-key|x-api-key|authorization)['\"],\s*b['\"])([^'\"]+)(['\"])"
)
_URL_USERINFO_RE = re.compile(r"(://[^:/\s@]+:)([^@\s'\"\)]+)(@)")

_LOG_REDACTION_INSTALLED = False


def collect_configured_secrets(extra_secrets: Optional[Iterable[Optional[str]]] = None) -> List[str]:
    """Collects non-empty secret strings from configuration and caller hints without exposing them."""
    candidates: List[str] = []
    try:
        from app.core.config import settings

        for attr in ("GEMINI_API_KEY", "WAQI_API_KEY", "OPENAQ_API_KEY", "SECRET_KEY"):
            val = getattr(settings, attr, None)
            if isinstance(val, str) and len(val) >= 4:
                candidates.append(val)
    except Exception:
        pass

    if extra_secrets:
        for secret in extra_secrets:
            if isinstance(secret, str) and len(secret) >= 4:
                candidates.append(secret)

    expanded: Dict[str, None] = {}
    for secret in candidates:
        expanded.setdefault(secret, None)
        encoded = quote(secret, safe="")
        if encoded and encoded != secret and len(encoded) >= 4:
            expanded.setdefault(encoded, None)

    return sorted(expanded.keys(), key=len, reverse=True)


def redact_sensitive_text(value: Any, extra_secrets: Optional[Iterable[Optional[str]]] = None) -> str:
    """Redacts configured API keys, query tokens, auth headers, and URL passwords from arbitrary text."""
    text = value if isinstance(value, str) else str(value)
    if not text:
        return ""

    text = _QUERY_SECRET_RE.sub(rf"\1{REDACTED}", text)
    text = _HEADER_SECRET_RE.sub(rf"\1{REDACTED}", text)
    text = _BYTES_HEADER_RE.sub(rf"\1{REDACTED}\3", text)
    text = _URL_USERINFO_RE.sub(rf"\1{REDACTED}\3", text)

    for secret in collect_configured_secrets(extra_secrets):
        if secret in text:
            text = text.replace(secret, REDACTED)

    return text


def format_safe_exception(exc: BaseException, extra_secrets: Optional[Iterable[Optional[str]]] = None) -> str:
    """Formats an exception cleanly as '<Type>: <redacted_message>' without credential leakage."""
    exc_name = type(exc).__name__
    redacted_msg = redact_sensitive_text(str(exc), extra_secrets=extra_secrets).strip()
    if redacted_msg:
        return f"{exc_name}: {redacted_msg}"
    return exc_name


def _sanitize_log_arg(arg: Any) -> Any:
    if arg is None or isinstance(arg, (bool, int, float)):
        return arg
    if isinstance(arg, str):
        return redact_sensitive_text(arg)
    if isinstance(arg, bytes):
        decoded = arg.decode("utf-8", errors="replace")
        redacted = redact_sensitive_text(decoded)
        return redacted.encode("utf-8") if redacted != decoded else arg
    if isinstance(arg, tuple):
        return tuple(_sanitize_log_arg(item) for item in arg)
    if isinstance(arg, list):
        return [_sanitize_log_arg(item) for item in arg]
    if isinstance(arg, dict):
        return {k: _sanitize_log_arg(v) for k, v in arg.items()}

    raw = str(arg)
    redacted = redact_sensitive_text(raw)
    return redacted if redacted != raw else arg


def _scrub_log_record(record: logging.LogRecord) -> logging.LogRecord:
    if isinstance(record.msg, str):
        record.msg = redact_sensitive_text(record.msg)
    else:
        record.msg = _sanitize_log_arg(record.msg)

    if record.args:
        record.args = _sanitize_log_arg(record.args)

    if record.exc_info and isinstance(record.exc_info, tuple) and record.exc_info[0] is not None:
        tb_text = "".join(traceback.format_exception(*record.exc_info)).rstrip()
        record.exc_text = redact_sensitive_text(tb_text)
        record.exc_info = None
    elif record.exc_text:
        record.exc_text = redact_sensitive_text(record.exc_text)

    return record


class CredentialRedactingFilter(logging.Filter):
    """Logging filter scrubbing secrets from log messages, args, URLs, and formatted tracebacks."""

    def filter(self, record: logging.LogRecord) -> bool:
        _scrub_log_record(record)
        return True


def install_log_redaction() -> None:
    """Installs process-wide log record scrubbing and logger filters idempotently."""
    global _LOG_REDACTION_INSTALLED
    if not _LOG_REDACTION_INSTALLED:
        base_factory = logging.getLogRecordFactory()

        def _redacting_record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
            record = base_factory(*args, **kwargs)
            return _scrub_log_record(record)

        logging.setLogRecordFactory(_redacting_record_factory)
        _LOG_REDACTION_INSTALLED = True

    shared_filter = CredentialRedactingFilter()
    for logger_name in ("", "app", "httpx", "httpcore", "uvicorn", "uvicorn.error", "uvicorn.access"):
        target_logger = logging.getLogger(logger_name)
        if not any(isinstance(f, CredentialRedactingFilter) for f in target_logger.filters):
            target_logger.addFilter(shared_filter)


install_log_redaction()
