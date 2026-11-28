from __future__ import annotations

from datetime import date, datetime, timedelta, timezone, tzinfo
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, localcontext
import math
import re
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

"""
India Central Pollution Control Board (CPCB) National Air Quality Index (NAQI) Methodology
Authoritative Reference:
- National Air Quality Index (NAQI), Control of Urban Pollution Series: CUPS/82/2014-15,
  Central Pollution Control Board (CPCB) & IIT Kanpur, October 2014.
- CPCB Official How_AQI_Calculated.pdf (Table 3.1): Cp = truncated concentration of pollutant p.

Covered Pollutants & Native CPCB Units / Averaging Periods / Truncation Precision:
- PM2.5 (ug/m3, 24-hr avg): truncated (ROUND_DOWN) to integer (1)
- PM10  (ug/m3, 24-hr avg): truncated (ROUND_DOWN) to integer (1)
- NO2   (ug/m3, 24-hr avg): truncated (ROUND_DOWN) to integer (1)
- SO2   (ug/m3, 24-hr avg): truncated (ROUND_DOWN) to integer (1)
- O3    (ug/m3,  8-hr avg up to 208; paired 1-hr avg when 8-hr > 208): truncated (ROUND_DOWN) to integer (1)
- CO    (mg/m3,  8-hr avg): truncated (ROUND_DOWN) to 0.1 (0.1)
- NH3   (ug/m3, 24-hr avg): truncated (ROUND_DOWN) to integer (1)
- Pb    (ug/m3, 24-hr avg): truncated (ROUND_DOWN) to 0.1 (0.1)

Open-Ended Severe Category (401-500):
- CPCB Table 3.1 defines open-ended Severe thresholds (PM2.5 >250, PM10 >430, NO2 >400,
  SO2 >1600, CO >34.0, O3 >748, NH3 >1800, Pb >3.5) with no official closed ceiling or published
  mathematical formula in How_AQI_Calculated.pdf.
- Documented engineering interpretation: sub-indices in the open-ended Severe range follow
  the continuous Very Poor slope continuation clamped strictly within [401, 500].

Minimum Pollutant Rule:
- Official CPCB NAQI requires at least 3 eligible pollutants, at least one of which MUST be
  PM2.5 or PM10. When unmet, returns aqi=None and category='Unavailable' (never returns a
  numeric 'Provisional' official CPCB score), while preserving diagnostic subindices.
"""

CPCB_METHODOLOGY_VERSION = "CPCB_NAQI_CUPS_82_2014_15"
CPCB_COMPLIANCE_DISCLAIMER = (
    "Formula calculations align with CPCB NAQI (CUPS/82/2014-15) breakpoints, 0-500 scale, "
    "and minimum-pollutant gate; formula execution alone does not constitute formal CPCB monitoring "
    "or 16-of-24-hour capture compliance."
)

_CPCB_QUANTIZERS: Dict[str, Decimal] = {
    "pm25": Decimal("1"),
    "pm10": Decimal("1"),
    "no2": Decimal("1"),
    "so2": Decimal("1"),
    "co": Decimal("0.1"),
    "o3": Decimal("1"),
    "nh3": Decimal("1"),
    "pb": Decimal("0.1"),
}

# Breakpoint tuples: (BP_low, BP_high_or_None_if_open_ended, I_low, I_high)
CPCB_BREAKPOINTS: Dict[str, List[Tuple[float, Optional[float], int, int]]] = {
    "pm25": [  # ug/m3, 24-hr avg
        (0, 30, 0, 50),
        (31, 60, 51, 100),
        (61, 90, 101, 200),
        (91, 120, 201, 300),
        (121, 250, 301, 400),
        (251, None, 401, 500),  # 250+ open-ended Severe
    ],
    "pm10": [  # ug/m3, 24-hr avg
        (0, 50, 0, 50),
        (51, 100, 51, 100),
        (101, 250, 101, 200),
        (251, 350, 201, 300),
        (351, 430, 301, 400),
        (431, None, 401, 500),  # 430+ open-ended Severe
    ],
    "no2": [  # ug/m3, 24-hr avg
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 180, 101, 200),
        (181, 280, 201, 300),
        (281, 400, 301, 400),
        (401, None, 401, 500),  # 400+ open-ended Severe
    ],
    "so2": [  # ug/m3, 24-hr avg
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 380, 101, 200),
        (381, 800, 201, 300),
        (801, 1600, 301, 400),
        (1601, None, 401, 500),  # 1600+ open-ended Severe
    ],
    "co": [  # mg/m3, 8-hr avg
        (0.0, 1.0, 0, 50),
        (1.1, 2.0, 51, 100),
        (2.1, 10.0, 101, 200),
        (10.1, 17.0, 201, 300),
        (17.1, 34.0, 301, 400),
        (34.1, None, 401, 500),  # 34+ open-ended Severe
    ],
    "o3": [  # ug/m3, 8-hr avg
        (0, 50, 0, 50),
        (51, 100, 51, 100),
        (101, 168, 101, 200),
        (169, 208, 201, 300),
        (209, 748, 301, 400),
        (749, None, 401, 500),  # 748+ open-ended Severe
    ],
    "nh3": [  # ug/m3, 24-hr avg
        (0, 200, 0, 50),
        (201, 400, 51, 100),
        (401, 800, 101, 200),
        (801, 1200, 201, 300),
        (1201, 1800, 301, 400),
        (1801, None, 401, 500),  # 1800+ open-ended Severe
    ],
    "pb": [  # ug/m3, 24-hr avg
        (0.0, 0.5, 0, 50),
        (0.6, 1.0, 51, 100),
        (1.1, 2.0, 101, 200),
        (2.1, 3.0, 201, 300),
        (3.1, 3.5, 301, 400),
        (3.6, None, 401, 500),  # 3.5+ open-ended Severe
    ],
}

CPCB_O3_8H_BREAKPOINTS: List[Tuple[float, Optional[float], int, int]] = [  # ug/m3, 8-hr avg (0-300)
    (0, 50, 0, 50),
    (51, 100, 51, 100),
    (101, 168, 101, 200),
    (169, 208, 201, 300),
]

CPCB_O3_1H_HIGH_BREAKPOINTS: List[Tuple[float, Optional[float], int, int]] = [  # ug/m3, 1-hr avg when 8-hr > 208
    (209, 748, 301, 400),
    (749, None, 401, 500),  # 748+* open-ended Severe
]

# Engineering interpretation: continuous Very Poor tier anchor and concentration span for open-ended Severe
# (CPCB Table 3.1 lists Severe as open-ended X+ without publishing closed upper ceilings):
# I_severe = 400 + (Cp - vp_upper_threshold) * (100 / vp_span), clamped to [401, 500]
_CPCB_SEVERE_SLOPES: Dict[str, Tuple[Decimal, Decimal]] = {
    "pm25": (Decimal("250"), Decimal("130")),    # 120 -> 250
    "pm10": (Decimal("430"), Decimal("80")),     # 350 -> 430
    "no2": (Decimal("400"), Decimal("120")),     # 280 -> 400
    "so2": (Decimal("1600"), Decimal("800")),    # 800 -> 1600
    "co": (Decimal("34.0"), Decimal("17.0")),    # 17.0 -> 34.0
    "o3": (Decimal("748"), Decimal("540")),      # 208 -> 748
    "nh3": (Decimal("1800"), Decimal("600")),    # 1200 -> 1800
    "pb": (Decimal("3.5"), Decimal("0.5")),       # 3.0 -> 3.5
}

CPCB_POLLUTANT_SPECS: Dict[str, Dict[str, Any]] = {
    "pm25": {"unit": "ug/m3", "averaging_period": "24h", "truncation": "1", "severe_threshold": 250},
    "pm10": {"unit": "ug/m3", "averaging_period": "24h", "truncation": "1", "severe_threshold": 430},
    "no2": {"unit": "ug/m3", "averaging_period": "24h", "truncation": "1", "severe_threshold": 400},
    "so2": {"unit": "ug/m3", "averaging_period": "24h", "truncation": "1", "severe_threshold": 1600},
    "co": {"unit": "mg/m3", "averaging_period": "8h", "truncation": "0.1", "severe_threshold": 34.0},
    "o3": {"unit": "ug/m3", "averaging_period": "8h", "1h_trigger_above": 208, "truncation": "1", "severe_threshold": 748},
    "nh3": {"unit": "ug/m3", "averaging_period": "24h", "truncation": "1", "severe_threshold": 1800},
    "pb": {"unit": "ug/m3", "averaging_period": "24h", "truncation": "0.1", "severe_threshold": 3.5},
}

_UNIT_ALIASES: Dict[str, str] = {
    "ug/m3": "ug/m3",
    "µg/m³": "ug/m3",
    "μg/m³": "ug/m3",
    "ug/m^3": "ug/m3",
    "mg/m3": "mg/m3",
    "mg/m³": "mg/m3",
    "mg/m^3": "mg/m3",
    "ppm": "ppm",
    "ppb": "ppb",
    "aqi_subindex": "aqi_subindex",
    "waqi_iaqi_subindex": "waqi_iaqi_subindex",
}

_PERIOD_ALIASES: Dict[str, str] = {
    "1h": "1h",
    "1hr": "1h",
    "1-hr": "1h",
    "1-hour": "1h",
    "1 hour": "1h",
    "hourly": "1h",
    "8h": "8h",
    "8hr": "8h",
    "8-hr": "8h",
    "8-hour": "8h",
    "8 hours": "8h",
    "24h": "24h",
    "24hr": "24h",
    "24-hr": "24h",
    "24-hour": "24h",
    "24 hours": "24h",
    "daily": "24h",
    "instantaneous": "instantaneous",
    "unknown": "unknown",
    "provider_reported": "provider_reported",
}


def get_cpcb_category(aqi: int) -> Tuple[str, str, str]:
    if aqi <= 50:
        return "Good", "#10b981", "Minimal impact on health."
    elif aqi <= 100:
        return "Satisfactory", "#22c55e", "Minor breathing discomfort to sensitive people."
    elif aqi <= 200:
        return "Moderate", "#f59e0b", "Breathing discomfort to people with lungs, asthma and heart diseases."
    elif aqi <= 300:
        return "Poor", "#f97316", "Breathing discomfort to most people on prolonged exposure."
    elif aqi <= 400:
        return "Very Poor", "#ef4444", "Respiratory illness on prolonged exposure."
    else:
        return "Severe", "#7f1d1d", "Affects healthy people and seriously impacts those with existing diseases."


def _extract_finite_concentration(raw: Any) -> Optional[float]:
    """Extracts a finite float concentration, rejecting None, bool, NaN, infinities, and overflows."""
    if raw is None or isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    try:
        numeric = float(raw)
    except (OverflowError, ValueError, TypeError):
        return None
    return numeric if math.isfinite(numeric) else None


def _canonicalize_unit(raw_unit: Optional[str]) -> Optional[str]:
    if not isinstance(raw_unit, str):
        return None
    cleaned = raw_unit.strip()
    if not cleaned:
        return None
    return _UNIT_ALIASES.get(cleaned.lower(), cleaned.lower())


def _canonicalize_period(raw_period: Optional[str]) -> Optional[str]:
    if not isinstance(raw_period, str):
        return None
    cleaned = raw_period.strip().lower()
    if not cleaned:
        return None
    return _PERIOD_ALIASES.get(cleaned, cleaned)


def _canonicalize_pollutant_with_period(raw_pollutant: str) -> Tuple[Optional[str], Optional[str]]:
    """Map pollutant identifier to (base_pollutant, implied_averaging_period)."""
    cleaned = raw_pollutant.strip().lower().replace(".", "").replace("-", "_")
    if cleaned in {"pm25", "pm2_5"}:
        return "pm25", None
    if cleaned == "pm10":
        return "pm10", None
    if cleaned == "no2":
        return "no2", None
    if cleaned == "so2":
        return "so2", None
    if cleaned == "co":
        return "co", None
    if cleaned in {"o3", "ozone"}:
        return "o3", None
    if cleaned in {"o3_8h", "o38h", "o3_8hr"}:
        return "o3", "8h"
    if cleaned in {"o3_1h", "o31h", "o3_1hr"}:
        return "o3", "1h"
    if cleaned in {"nh3", "ammonia"}:
        return "nh3", None
    if cleaned in {"pb", "lead"}:
        return "pb", None
    return None, None


def _canonicalize_pollutant(raw_pollutant: str) -> Optional[str]:
    base, _ = _canonicalize_pollutant_with_period(raw_pollutant)
    return base


def _convert_to_cpcb_native_decimal(
    pollutant: str,
    numeric: float,
    canonical_unit: str,
) -> Tuple[Optional[Decimal], Optional[str]]:
    """Convert finite concentration to native CPCB mass units using exact SI scaling only."""
    dec = Decimal(str(numeric))
    if pollutant == "co":
        if canonical_unit == "mg/m3":
            return dec, "mg/m3"
        if canonical_unit == "ug/m3":
            return dec / Decimal("1000"), "mg/m3"
        if canonical_unit in {"ppm", "ppb"}:
            return None, f"volumetric_unit_{canonical_unit}_ineligible_without_ambient_tp_for_mg_m3"
        return None, f"unsupported_unit_{canonical_unit}_requires_mg_m3"

    if canonical_unit == "ug/m3":
        return dec, "ug/m3"
    if canonical_unit == "mg/m3":
        return dec * Decimal("1000"), "ug/m3"
    if canonical_unit in {"ppm", "ppb"}:
        return None, f"volumetric_unit_{canonical_unit}_ineligible_without_ambient_tp_for_ug_m3"
    return None, f"unsupported_unit_{canonical_unit}_requires_ug_m3"


def _truncate_cpcb_decimal(pollutant: str, value_dec: Decimal) -> Decimal:
    """Applies CPCB NAQI ROUND_DOWN concentration truncation matching breakpoint precision (Cp)."""
    step = _CPCB_QUANTIZERS[pollutant]
    abs_val = abs(value_dec)
    int_digits = len(str(int(abs_val))) if abs_val >= 1 else 1
    with localcontext() as ctx:
        ctx.prec = max(64, int_digits + 24)
        return value_dec.quantize(step, rounding=ROUND_DOWN)


def _interpolate_cpcb_subindex(
    pollutant: str,
    truncated_conc: Decimal,
    *,
    breakpoints_override: Optional[List[Tuple[float, Optional[float], int, int]]] = None,
) -> Optional[int]:
    """Computes integer CPCB subindex in [0, 500], handling open-ended Severe ranges cleanly."""
    breakpoints = breakpoints_override if breakpoints_override is not None else CPCB_BREAKPOINTS[pollutant]
    int_digits = len(str(int(abs(truncated_conc)))) if abs(truncated_conc) >= 1 else 1
    with localcontext() as ctx:
        ctx.prec = max(64, int_digits + 24)
        for bp_lo, bp_hi, i_lo, i_hi in breakpoints:
            bp_lo_d = Decimal(str(bp_lo))
            if bp_hi is not None:
                bp_hi_d = Decimal(str(bp_hi))
                if bp_lo_d <= truncated_conc <= bp_hi_d:
                    i_lo_d = Decimal(str(i_lo))
                    i_hi_d = Decimal(str(i_hi))
                    raw_index = ((i_hi_d - i_lo_d) * (truncated_conc - bp_lo_d)) / (bp_hi_d - bp_lo_d) + i_lo_d
                    return int(raw_index.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            else:
                # Open-ended Severe tier (>= bp_lo_d, i.e., above Very Poor ceiling):
                # Continuous Very Poor slope extension clamped strictly within [401, 500].
                if truncated_conc >= bp_lo_d:
                    vp_threshold, vp_span = _CPCB_SEVERE_SLOPES[pollutant]
                    if truncated_conc >= vp_threshold + vp_span:
                        return 500
                    raw_index = Decimal("400") + ((truncated_conc - vp_threshold) * Decimal("100")) / vp_span
                    idx = int(raw_index.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                    return min(500, max(401, idx))
    return None


def calculate_cpcb_subindex(
    pollutant: str,
    conc: Any,
    *,
    unit: Optional[str] = None,
    averaging_period: Optional[str] = None,
) -> Optional[int]:
    """
    Calculates an individual CPCB NAQI pollutant sub-index (CUPS/82/2014-15, scale 0-500).

    Per CPCB Table 3.1:
    - All pollutants except CO (0.1 mg/m3) and Pb (0.1 ug/m3) truncate Cp to integer.
    - For O3: 8-hr average applies only up to 208 ug/m3 (0-300); above 208 ug/m3 uses 1-hr O3.
      Standalone averaging_period='8h' returns None above 208 ug/m3.
    """
    if not isinstance(pollutant, str):
        return None
    norm_pollutant, implied_period = _canonicalize_pollutant_with_period(pollutant)
    numeric = _extract_finite_concentration(conc)
    if norm_pollutant is None or numeric is None or numeric < 0:
        return None

    expected_period = CPCB_POLLUTANT_SPECS[norm_pollutant]["averaging_period"]
    explicit_arg_period = _canonicalize_period(averaging_period) if averaging_period is not None else None
    if implied_period is not None and averaging_period is not None and explicit_arg_period != implied_period:
        return None
    effective_period = explicit_arg_period if averaging_period is not None else implied_period
    if norm_pollutant == "o3":
        if effective_period is not None and effective_period not in {"8h", "1h"}:
            return None
    elif effective_period is not None and effective_period != expected_period:
        return None

    default_unit = CPCB_POLLUTANT_SPECS[norm_pollutant]["unit"]
    canonical_unit = _canonicalize_unit(unit) if unit is not None else default_unit
    if canonical_unit is None:
        return None

    native_dec, _ = _convert_to_cpcb_native_decimal(norm_pollutant, numeric, canonical_unit)
    if native_dec is None:
        return None

    truncated_conc = _truncate_cpcb_decimal(norm_pollutant, native_dec)
    if norm_pollutant == "o3" and effective_period == "8h":
        return _interpolate_cpcb_subindex("o3", truncated_conc, breakpoints_override=CPCB_O3_8H_BREAKPOINTS)
    if norm_pollutant == "o3" and effective_period == "1h":
        return _interpolate_cpcb_subindex("o3", truncated_conc, breakpoints_override=CPCB_O3_1H_HIGH_BREAKPOINTS)
    return _interpolate_cpcb_subindex(norm_pollutant, truncated_conc)


# Explicit monitoring-station ID tags only; require explicit "ID:" / "ID=" labels (never display-name "#N").
_STATION_ID_PAREN_RE = re.compile(
    r"\(\s*(?:station|location|monitoring_station|site)[\s_]+id\s*[:=]\s*([A-Za-z0-9._-]+)\s*\)",
    re.IGNORECASE,
)
_STATION_ID_SOURCE_RE = re.compile(
    r"\b(?:station|location|monitoring_station|site)[\s_]+id\s*[:=]\s*([A-Za-z0-9._-]+)",
    re.IGNORECASE,
)
_SENSOR_ID_PAREN_RE = re.compile(
    r"\(\s*(?:sensor|sensors|instrument|channel)[\s_]+id\s*[:=]\s*([A-Za-z0-9._-]+)\s*\)",
    re.IGNORECASE,
)
_SENSOR_ID_SOURCE_RE = re.compile(
    r"\b(?:sensor|sensors|instrument|channel)[\s_]+id\s*[:=]\s*([A-Za-z0-9._-]+)",
    re.IGNORECASE,
)
_ID_TAG_STRIP_RE = re.compile(
    r"\(\s*(?:station|location|monitoring_station|site|sensor|sensors|instrument|channel)[\s_]+id\s*[:=]\s*[A-Za-z0-9._-]+\s*\)",
    re.IGNORECASE,
)
_INVALID_ID_TOKENS = frozenset({
    "unknown",
    "n/a",
    "na",
    "none",
    "null",
    "nil",
    "unavailable",
    "missing",
    "-",
    "station",
    "sensor",
    "default",
})
_SAFE_ID_CHARS_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
_AMBIGUOUS_SOURCE_TOKENS = frozenset({
    "unknown",
    "n/a",
    "na",
    "none",
    "null",
    "nil",
    "unavailable",
    "missing",
    "measured",
    "model",
    "model_derived",
    "provider_index",
    "provisional",
    "estimated",
    "verified",
    "ground",
    "ground_observation",
    "ground_station",
    "monitoring_station",
    "station",
    "sensor",
    "instrument",
    "monitor",
    "channel",
    "default",
    "local",
    "test",
    "openaq",
    "cpcb",
    "waqi",
    "aqicn",
    "open-meteo",
    "openmeteo",
    "epa",
    "eaqi",
    "eea",
})
_FIXED_OFFSET_RE = re.compile(r"^(?:UTC|GMT)?\s*([+-])\s*(\d{2}):?(\d{2})$", re.IGNORECASE)
_SUPPORTED_TIMESTAMP_SEMANTICS = frozenset({"period_end", "period_start", "contained"})
_VERIFIED_PROVIDER_NAMESPACES = frozenset({"openaq", "cpcb", "waqi", "aqicn", "open-meteo", "openmeteo", "epa"})
_INVALID_NAMESPACE_TOKENS = frozenset({"", "unknown", "local", "none", "n/a", "na", "default", "sensor", "station", "measured"})


def _extract_station_namespace(raw_namespace: Any, raw_source: Any) -> Optional[str]:
    """
    Extracts verified provider/network namespace scoping for locally assigned station identifiers.
    Prefers explicit `station_namespace`/`network`/`provider_namespace`/`provider` metadata and falls back
    ONLY to unambiguous provider prefixes (`OpenAQ / ...`, `CPCB / ...`, etc.), never arbitrary display names.
    """
    if isinstance(raw_namespace, str):
        ns = raw_namespace.strip().casefold()
        if ns and ns not in _INVALID_NAMESPACE_TOKENS:
            return ns
        return None
    if isinstance(raw_source, str):
        cleaned = raw_source.strip()
        if "/" in cleaned or ":" in cleaned:
            prefix = re.split(r"[/:]", cleaned, maxsplit=1)[0].strip().casefold()
            if prefix in _VERIFIED_PROVIDER_NAMESPACES:
                return prefix
    return None


def _extract_nonempty_id(raw_val: Any) -> Optional[str]:
    if raw_val is None or isinstance(raw_val, bool) or not isinstance(raw_val, (str, int)):
        return None
    text = str(raw_val).strip()
    if not text or not _SAFE_ID_CHARS_RE.fullmatch(text) or not any(ch.isalnum() for ch in text):
        return None
    cf = text.casefold()
    if cf in _INVALID_ID_TOKENS:
        return None
    return cf


def _extract_source_station_ids(raw_source: Any) -> Tuple[set[str], bool]:
    """
    Extracts explicit `Station/Location/Site ID:` tags from `raw_source`, detecting malformed or conflicting tags.
    Never extracts arbitrary `#N` display-name numbers.
    """
    if not isinstance(raw_source, str):
        return set(), False
    ids: set[str] = set()
    has_malformed = False
    for regex in (_STATION_ID_PAREN_RE, _STATION_ID_SOURCE_RE):
        for match in regex.finditer(raw_source):
            norm = _extract_nonempty_id(match.group(1))
            if norm is None:
                has_malformed = True
            else:
                ids.add(norm)
    return ids, has_malformed


def _extract_station_id(raw_station_id: Any, raw_source: Any) -> Optional[str]:
    """
    Extracts canonical lowercase monitoring-station identifier from verified station ID
    fields (`station_id`, `location_id`, `monitoring_station_id`, `site_id`) or explicit
    `Station ID: <id>` tags. Fails closed on malformed or conflicting tags, and never
    extracts display-name patterns such as `Station #5` or `Site #12`.
    """
    if raw_station_id is not None:
        explicit = _extract_nonempty_id(raw_station_id)
        if explicit is None:
            return None
        tag_ids, has_bad_tag = _extract_source_station_ids(raw_source)
        if has_bad_tag or (tag_ids and tag_ids != {explicit}):
            return None
        return explicit
    tag_ids, has_bad_tag = _extract_source_station_ids(raw_source)
    if has_bad_tag or len(tag_ids) != 1:
        return None
    return next(iter(tag_ids))


def _resolve_explicit_identity_metadata(
    raw_station_vals: List[Any],
    raw_namespace_vals: List[Any],
    raw_shared_vals: List[Any],
    raw_sensor_vals: List[Any],
    raw_source: Any,
) -> Dict[str, Any]:
    """
    Resolves station ID, namespace, shared ID, and sensor ID across multiple alias fields
    without arbitrary precedence: any disagreement across explicit aliases or source ID/provider
    tags fails closed with explicit conflict diagnostics.
    """
    explicit_ids: set[str] = set()
    malformed_station_id = False
    for val in raw_station_vals:
        if val is None:
            continue
        norm = _extract_nonempty_id(val)
        if norm is None:
            malformed_station_id = True
        else:
            explicit_ids.add(norm)

    tag_ids, has_bad_tag = _extract_source_station_ids(raw_source)
    combined_ids = explicit_ids | tag_ids
    conflicting_station_id = len(combined_ids) > 1
    if conflicting_station_id or malformed_station_id or (not explicit_ids and has_bad_tag) or (explicit_ids and has_bad_tag):
        station_id: Optional[str] = None
    elif len(combined_ids) == 1:
        station_id = next(iter(combined_ids))
    else:
        station_id = None

    explicit_namespaces: set[str] = set()
    malformed_namespace = False
    for val in raw_namespace_vals:
        if val is None:
            continue
        norm_ns = _extract_station_namespace(val, None)
        if norm_ns is None:
            malformed_namespace = True
        else:
            explicit_namespaces.add(norm_ns)

    source_ns = _extract_station_namespace(None, raw_source)
    combined_namespaces = set(explicit_namespaces)
    if source_ns is not None:
        combined_namespaces.add(source_ns)

    conflicting_station_namespace = len(combined_namespaces) > 1
    if conflicting_station_namespace or malformed_namespace:
        station_namespace: Optional[str] = None
    elif len(combined_namespaces) == 1:
        station_namespace = next(iter(combined_namespaces))
    else:
        station_namespace = None

    shared_ids: set[str] = set()
    malformed_shared_id = False
    for val in raw_shared_vals:
        if val is None:
            continue
        norm_sh = _extract_nonempty_id(val)
        if norm_sh is None:
            malformed_shared_id = True
        else:
            shared_ids.add(norm_sh)
    if len(shared_ids) > 1:
        malformed_shared_id = True
        shared_station_id: Optional[str] = None
    elif len(shared_ids) == 1 and not malformed_shared_id:
        shared_station_id = next(iter(shared_ids))
    else:
        shared_station_id = None

    explicit_sensor = next((v for v in raw_sensor_vals if v is not None), None)
    return {
        "station_id": station_id,
        "conflicting_station_id": conflicting_station_id,
        "explicit_station_id_malformed": malformed_station_id or has_bad_tag,
        "station_namespace": station_namespace,
        "conflicting_station_namespace": conflicting_station_namespace,
        "explicit_namespace_malformed": malformed_namespace,
        "shared_station_id": shared_station_id,
        "explicit_shared_id_malformed": malformed_shared_id,
        "sensor_id": _extract_sensor_id(explicit_sensor, raw_source),
    }


def _extract_sensor_id(raw_sensor_id: Any, raw_source: Any) -> Optional[str]:
    """Extracts diagnostic sensor/channel identifier separately from physical station identity."""
    if raw_sensor_id is not None:
        return _extract_nonempty_id(raw_sensor_id)
    if isinstance(raw_source, str):
        paren_match = _SENSOR_ID_PAREN_RE.search(raw_source)
        if paren_match:
            return _extract_nonempty_id(paren_match.group(1))
        match = _SENSOR_ID_SOURCE_RE.search(raw_source)
        if match:
            return _extract_nonempty_id(match.group(1))
    return None


def _normalize_source_identity(raw_source: Any) -> Optional[str]:
    """
    Diagnostic normalization of source display text.
    Never used to establish physical station identity for official CPCB O3 pairing.
    """
    if not isinstance(raw_source, str):
        return None
    stripped_tags = _ID_TAG_STRIP_RE.sub(" ", raw_source)
    cleaned = " ".join(stripped_tags.split()).strip(" -_/:.")
    if not cleaned:
        return None

    cf = cleaned.casefold()
    if cf in _AMBIGUOUS_SOURCE_TOKENS:
        return None

    segments = [seg.strip(" -_:.") for seg in re.split(r"[/|]", cf) if seg.strip(" -_:.")]
    if not segments:
        return None
    candidate = segments[-1]
    if candidate in _AMBIGUOUS_SOURCE_TOKENS:
        return None
    words = [w for w in re.split(r"[\s:_-]+", candidate) if w]
    meaningful_words = [w for w in words if w not in _AMBIGUOUS_SOURCE_TOKENS and not w.isdigit()]
    if not meaningful_words:
        return None

    return " ".join(cleaned.split()).casefold()


def _parse_cpcb_utc_timestamp_with_origin(
    raw_ts: Any,
    *,
    is_interval_bound: bool = False,
) -> Tuple[Optional[datetime], Optional[datetime], Optional[str]]:
    """
    Parses a timezone-aware timestamp or interval bound, returning `(utc_dt, original_offset_dt, error)`.
    Rejects missing, naive, malformed, or excessively future (> now + 5m) timestamps.
    """
    missing_code = "missing_interval_bounds" if is_interval_bound else "missing_observation_timestamp"
    malformed_code = "malformed_interval_bound" if is_interval_bound else "malformed_observation_timestamp"
    naive_code = "naive_or_unverified_timezone_interval" if is_interval_bound else "naive_or_unverified_timezone_timestamp"
    future_code = "future_interval_bound" if is_interval_bound else "future_observation_timestamp"

    if raw_ts is None or isinstance(raw_ts, bool):
        return None, None, missing_code
    if isinstance(raw_ts, datetime):
        dt = raw_ts
    elif isinstance(raw_ts, str):
        text = raw_ts.strip()
        if not text:
            return None, None, missing_code
        if text.endswith(("Z", "z")):
            text = f"{text[:-1]}+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None, None, malformed_code
    else:
        return None, None, malformed_code

    if dt.tzinfo is None or dt.utcoffset() is None:
        return None, None, naive_code

    dt_utc = dt.astimezone(timezone.utc)
    if dt_utc > datetime.now(timezone.utc) + timedelta(minutes=5):
        return None, None, future_code
    return dt_utc, dt, None


def _parse_cpcb_utc_timestamp(raw_ts: Any) -> Tuple[Optional[datetime], Optional[str]]:
    """Parses a timezone-aware observation timestamp to UTC, rejecting missing, naive, malformed, or future timestamps."""
    dt_utc, _, err = _parse_cpcb_utc_timestamp_with_origin(raw_ts)
    return dt_utc, err


def _parse_reporting_date_value(raw_rdate: Any) -> Tuple[Optional[date], Optional[str]]:
    if raw_rdate is None:
        return None, None
    if isinstance(raw_rdate, bool):
        return None, "malformed_reporting_date"
    if isinstance(raw_rdate, date) and not isinstance(raw_rdate, datetime):
        return raw_rdate, None
    if isinstance(raw_rdate, str):
        text = raw_rdate.strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return None, "malformed_reporting_date"
        try:
            return date.fromisoformat(text), None
        except ValueError:
            return None, "malformed_reporting_date"
    return None, "malformed_reporting_date"


def _parse_reporting_timezone(raw_tz: Any) -> Tuple[Optional[tzinfo], Optional[str]]:
    """Resolves explicit non-ambiguous timezone metadata (UTC/GMT, numeric +/-HH:MM, or valid ZoneInfo); never invents zones."""
    if raw_tz is None:
        return None, None
    if isinstance(raw_tz, tzinfo):
        return raw_tz, None
    if not isinstance(raw_tz, str):
        return None, "ambiguous_reporting_date_timezone"

    text = raw_tz.strip()
    if not text or text.casefold() in {"local", "unknown", "ambiguous", "none", "n/a", "ist", "cst", "est", "pst", "mst"}:
        return None, "ambiguous_reporting_date_timezone"

    if text.upper() in {"Z", "UTC", "GMT", "UTC+0", "UTC+00:00", "GMT+0"}:
        return timezone.utc, None

    offset_match = _FIXED_OFFSET_RE.match(text)
    if offset_match:
        sign_ch, hh_s, mm_s = offset_match.groups()
        hh, mm = int(hh_s), int(mm_s)
        if hh > 14 or mm >= 60:
            return None, "ambiguous_reporting_date_timezone"
        delta = timedelta(hours=hh, minutes=mm)
        return timezone(-delta if sign_ch == "-" else delta), None

    try:
        return ZoneInfo(text), None
    except Exception:
        return None, "ambiguous_reporting_date_timezone"


def _validate_single_reporting_date(
    prefix: str,
    raw_ts: Any,
    dt_utc: datetime,
    dt_origin: datetime,
    raw_rdate: Any,
    raw_rdate_tz: Any,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Verifies a measurement's optional reporting_date against its observation_timestamp without inventing timezones.
    Returns `(ok, error_code, ambiguity_note)`.
    """
    if raw_rdate is None:
        if raw_rdate_tz is not None:
            tz_parsed, tz_err = _parse_reporting_timezone(raw_rdate_tz)
            if tz_err is not None or tz_parsed is None:
                return False, f"{prefix}_ambiguous_reporting_date_timezone", "unresolvable_or_ambiguous_reporting_date_timezone"
        return True, None, None

    rdate, rdate_err = _parse_reporting_date_value(raw_rdate)
    if rdate_err is not None or rdate is None:
        return False, f"{prefix}_{rdate_err}", None

    if raw_rdate_tz is not None:
        tz_parsed, tz_err = _parse_reporting_timezone(raw_rdate_tz)
        if tz_err is not None or tz_parsed is None:
            return False, f"{prefix}_ambiguous_reporting_date_timezone", "unresolvable_or_ambiguous_reporting_date_timezone"
        expected_date = dt_utc.astimezone(tz_parsed).date()
        if expected_date != rdate:
            return False, f"{prefix}_incompatible_reporting_date", None
        return True, None, None

    # No separate reporting_date_timezone supplied: allow match against timestamp's own explicit offset or UTC.
    ts_str_upper = raw_ts.strip().upper() if isinstance(raw_ts, str) else ""
    origin_offset = dt_origin.utcoffset() or timedelta(0)
    has_non_utc_origin = (origin_offset != timedelta(0)) or (
        isinstance(raw_ts, str) and not ts_str_upper.endswith("Z") and "+00:00" not in ts_str_upper and "-00:00" not in ts_str_upper
    )

    if has_non_utc_origin and rdate == dt_origin.date():
        return True, None, None
    if rdate == dt_utc.date():
        return True, None, None

    # Impossible in any real Earth timezone [UTC-12:00, UTC+14:00]
    min_earth_date = (dt_utc - timedelta(hours=12)).date()
    max_earth_date = (dt_utc + timedelta(hours=14)).date()
    if rdate < min_earth_date or rdate > max_earth_date:
        return False, f"{prefix}_incompatible_reporting_date", None

    # Date differs from UTC (and timestamp's stated offset) without an explicit reporting_date_timezone -> fail closed
    return False, f"{prefix}_ambiguous_reporting_date_timezone", "reporting_date_differs_from_timestamp_without_explicit_timezone"


def _extract_measurement_fields(raw_item: Any) -> Dict[str, Any]:
    station_keys = ("station_id", "location_id", "monitoring_station_id", "site_id")
    namespace_keys = ("station_namespace", "network", "provider_namespace", "provider")
    shared_keys = ("shared_station_id", "global_station_id")
    sensor_keys = ("sensor_id", "sensors_id", "channel_id")

    if hasattr(raw_item, "model_dump") or hasattr(raw_item, "unit"):
        raw_source = getattr(raw_item, "source", None)
        id_meta = _resolve_explicit_identity_metadata(
            [getattr(raw_item, attr, None) for attr in station_keys],
            [getattr(raw_item, attr, None) for attr in namespace_keys],
            [getattr(raw_item, attr, None) for attr in shared_keys],
            [getattr(raw_item, attr, None) for attr in sensor_keys],
            raw_source,
        )
        # Never infer interval bounds from observation_timestamp or vice versa.
        raw_ts = next(
            (
                getattr(raw_item, attr)
                for attr in ("observation_timestamp", "timestamp", "datetime", "recorded_at", "observed_at")
                if getattr(raw_item, attr, None) is not None
            ),
            None,
        )
        raw_reporting_date = getattr(raw_item, "reporting_date", None)
        raw_reporting_date_tz = next(
            (
                getattr(raw_item, attr)
                for attr in ("reporting_date_timezone", "reporting_timezone")
                if getattr(raw_item, attr, None) is not None
            ),
            None,
        )
        raw_ts_semantics = getattr(raw_item, "timestamp_semantics", None)
        raw_window_start = getattr(raw_item, "window_start", None)
        raw_window_end = getattr(raw_item, "window_end", None)
        return {
            "has_rich_metadata": True,
            "value": getattr(raw_item, "value", None),
            "unit": getattr(raw_item, "unit", None),
            "data_origin": getattr(raw_item, "data_origin", None),
            "averaging_period": getattr(raw_item, "averaging_period", None),
            "provider_aqi_subindex": getattr(raw_item, "provider_aqi_subindex", None),
            "valid_hours": getattr(raw_item, "valid_hours", None),
            "coverage_hours": getattr(raw_item, "coverage_hours", None),
            "expected_hours": getattr(raw_item, "expected_hours", None),
            "sample_count": getattr(raw_item, "sample_count", None),
            "completeness_ratio": getattr(raw_item, "completeness_ratio", None),
            "source": raw_source if isinstance(raw_source, str) else None,
            "normalized_source": _normalize_source_identity(raw_source),
            **id_meta,
            "observation_timestamp": raw_ts,
            "reporting_date": raw_reporting_date,
            "reporting_date_timezone": raw_reporting_date_tz,
            "timestamp_semantics": raw_ts_semantics,
            "window_start": raw_window_start,
            "window_end": raw_window_end,
        }
    if isinstance(raw_item, dict):
        raw_source = (
            raw_item.get("source")
            if raw_item.get("source") is not None
            else raw_item.get("station_name")
        )
        id_meta = _resolve_explicit_identity_metadata(
            [raw_item.get(key) for key in station_keys],
            [raw_item.get(key) for key in namespace_keys],
            [raw_item.get(key) for key in shared_keys],
            [raw_item.get(key) for key in sensor_keys],
            raw_source,
        )
        # Never infer interval bounds from observation_timestamp or promote window_end as observation_timestamp.
        raw_ts = next(
            (
                raw_item.get(key)
                for key in ("observation_timestamp", "timestamp", "datetime", "recorded_at", "observed_at", "time")
                if raw_item.get(key) is not None
            ),
            None,
        )
        raw_reporting_date = (
            raw_item.get("reporting_date")
            if raw_item.get("reporting_date") is not None
            else raw_item.get("window_date")
        )
        raw_reporting_date_tz = (
            raw_item.get("reporting_date_timezone")
            if raw_item.get("reporting_date_timezone") is not None
            else raw_item.get("reporting_timezone")
        )
        raw_ts_semantics = raw_item.get("timestamp_semantics")
        raw_window_start = raw_item.get("window_start")
        raw_window_end = raw_item.get("window_end")
        return {
            "has_rich_metadata": True,
            "value": raw_item.get("value"),
            "unit": raw_item.get("unit"),
            "data_origin": raw_item.get("data_origin"),
            "averaging_period": raw_item.get("averaging_period"),
            "provider_aqi_subindex": raw_item.get("provider_aqi_subindex"),
            "valid_hours": raw_item.get("valid_hours"),
            "coverage_hours": (
                raw_item.get("coverage_hours")
                if raw_item.get("coverage_hours") is not None
                else raw_item.get("coverage_duration_hours")
            ),
            "expected_hours": raw_item.get("expected_hours"),
            "sample_count": (
                raw_item.get("sample_count")
                if raw_item.get("sample_count") is not None
                else raw_item.get("valid_observations")
            ),
            "completeness_ratio": raw_item.get("completeness_ratio"),
            "source": raw_source if isinstance(raw_source, str) else None,
            "normalized_source": _normalize_source_identity(raw_source),
            **id_meta,
            "observation_timestamp": raw_ts,
            "reporting_date": raw_reporting_date,
            "reporting_date_timezone": raw_reporting_date_tz,
            "timestamp_semantics": raw_ts_semantics,
            "window_start": raw_window_start,
            "window_end": raw_window_end,
        }
    return {
        "has_rich_metadata": False,
        "value": raw_item,
        "unit": None,
        "data_origin": None,
        "averaging_period": None,
        "provider_aqi_subindex": None,
        "valid_hours": None,
        "coverage_hours": None,
        "expected_hours": None,
        "sample_count": None,
        "completeness_ratio": None,
        "source": None,
        "normalized_source": None,
        "station_id": None,
        "conflicting_station_id": False,
        "explicit_station_id_malformed": False,
        "station_namespace": None,
        "conflicting_station_namespace": False,
        "explicit_namespace_malformed": False,
        "shared_station_id": None,
        "explicit_shared_id_malformed": False,
        "sensor_id": None,
        "observation_timestamp": None,
        "reporting_date": None,
        "reporting_date_timezone": None,
        "timestamp_semantics": None,
        "window_start": None,
        "window_end": None,
    }


def _validate_cpcb_16h_completeness(fields: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Verifies explicit CPCB minimum 16-hour data-capture evidence without inferring
    completeness from period.label strings or inventing partial-hour policies.
    """
    raw_valid_hours = fields.get("valid_hours")
    raw_cov_hours = fields.get("coverage_hours")
    raw_expected_hours = fields.get("expected_hours")
    raw_sample_count = fields.get("sample_count")
    raw_ratio = fields.get("completeness_ratio")

    has_any_completeness = any(
        v is not None
        for v in (raw_valid_hours, raw_cov_hours, raw_expected_hours, raw_sample_count, raw_ratio)
    )
    if not has_any_completeness:
        return False, "unverified_16h_data_completeness", None

    valid_hrs = _extract_finite_concentration(raw_valid_hours) if raw_valid_hours is not None else None
    cov_hrs = _extract_finite_concentration(raw_cov_hours) if raw_cov_hours is not None else None

    if raw_valid_hours is not None and (valid_hrs is None or valid_hrs < 0):
        return False, "inconsistent_or_malformed_completeness_metadata", None
    if raw_cov_hours is not None and (cov_hrs is None or cov_hrs < 0):
        return False, "inconsistent_or_malformed_completeness_metadata", None

    if valid_hrs is not None and cov_hrs is not None and abs(valid_hrs - cov_hrs) > 1e-6:
        return False, "inconsistent_or_malformed_completeness_metadata", None

    observed_hours = valid_hrs if valid_hrs is not None else cov_hrs
    if observed_hours is None:
        return False, "unverified_16h_data_completeness", None

    expected_hrs: Optional[float] = None
    if raw_expected_hours is not None:
        expected_hrs = _extract_finite_concentration(raw_expected_hours)
        if expected_hrs is None or expected_hrs <= 0:
            return False, "inconsistent_or_malformed_completeness_metadata", None
        if observed_hours > expected_hrs or expected_hrs != 24.0:
            return False, "inconsistent_or_malformed_completeness_metadata", None

    if raw_sample_count is not None:
        samples = _extract_finite_concentration(raw_sample_count)
        if samples is None or samples < 0 or not float(samples).is_integer() or samples < observed_hours:
            return False, "inconsistent_or_malformed_completeness_metadata", None

    if raw_ratio is not None:
        ratio = _extract_finite_concentration(raw_ratio)
        denom = expected_hrs if expected_hrs is not None else 24.0
        if ratio is None or ratio < 0.0 or ratio > 1.0 or abs(ratio - (observed_hours / denom)) > 0.05:
            return False, "inconsistent_or_malformed_completeness_metadata", None

    if observed_hours < 16.0:
        return False, "insufficient_data_completeness_below_16h", {"observed_hours": observed_hours}

    return True, "verified_16h_completeness", {
        "observed_hours": observed_hours,
        "expected_hours": expected_hrs if expected_hrs is not None else 24.0,
    }


def _validate_cpcb_1h_ozone_completeness(fields: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Validates completeness metadata for a 1-hour O3 observation paired with an 8h > 208 ug/m3 trigger.
    Accepts either 24h station capture (>=16 of 24h) or explicit single-hour validity (valid_hours=1, expected_hours=1).
    """
    raw_valid_hours = fields.get("valid_hours")
    raw_cov_hours = fields.get("coverage_hours")
    raw_expected_hours = fields.get("expected_hours")
    raw_sample_count = fields.get("sample_count")
    raw_ratio = fields.get("completeness_ratio")

    has_any_completeness = any(
        v is not None
        for v in (raw_valid_hours, raw_cov_hours, raw_expected_hours, raw_sample_count, raw_ratio)
    )
    if not has_any_completeness:
        return False, "unverified_1h_observation_completeness", None

    valid_hrs = _extract_finite_concentration(raw_valid_hours) if raw_valid_hours is not None else None
    cov_hrs = _extract_finite_concentration(raw_cov_hours) if raw_cov_hours is not None else None
    if raw_valid_hours is not None and (valid_hrs is None or valid_hrs < 0):
        return False, "inconsistent_or_malformed_completeness_metadata", None
    if raw_cov_hours is not None and (cov_hrs is None or cov_hrs < 0):
        return False, "inconsistent_or_malformed_completeness_metadata", None
    if valid_hrs is not None and cov_hrs is not None and abs(valid_hrs - cov_hrs) > 1e-6:
        return False, "inconsistent_or_malformed_completeness_metadata", None

    observed_hours = valid_hrs if valid_hrs is not None else cov_hrs
    if observed_hours is None:
        return False, "unverified_1h_observation_completeness", None

    expected_hrs = 24.0
    if raw_expected_hours is not None:
        expected_parsed = _extract_finite_concentration(raw_expected_hours)
        if expected_parsed is None or expected_parsed not in {1.0, 24.0}:
            return False, "inconsistent_or_malformed_completeness_metadata", None
        expected_hrs = expected_parsed

    if observed_hours > expected_hrs:
        return False, "inconsistent_or_malformed_completeness_metadata", None

    if raw_sample_count is not None:
        samples = _extract_finite_concentration(raw_sample_count)
        if samples is None or samples < 0 or not float(samples).is_integer() or samples < observed_hours:
            return False, "inconsistent_or_malformed_completeness_metadata", None

    if raw_ratio is not None:
        ratio = _extract_finite_concentration(raw_ratio)
        if ratio is None or ratio < 0.0 or ratio > 1.0 or abs(ratio - (observed_hours / expected_hrs)) > 0.05:
            return False, "inconsistent_or_malformed_completeness_metadata", None

    min_req = 1.0 if expected_hrs == 1.0 else 16.0
    if observed_hours < min_req:
        return False, "insufficient_1h_o3_data_completeness", {"observed_hours": observed_hours, "expected_hours": expected_hrs}

    return True, "verified_1h_o3_completeness", {"observed_hours": observed_hours, "expected_hours": expected_hrs}


def classify_cpcb_measurement_eligibility(pollutant: str, raw_item: Any) -> Dict[str, Any]:
    """
    Classifies a pollutant input under CPCB NAQI provenance rules:
    - methodology_eligible (verified measured concentration, unit, period, and >=16h completeness)
    - model_derived_provisional
    - provider_index
    - unavailable_or_insufficient (including metadata-free scalars, negatives, isolated 1h O3, and unverified completeness)
    """
    norm_pollutant, implied_period = _canonicalize_pollutant_with_period(pollutant) if isinstance(pollutant, str) else (None, None)
    fields = _extract_measurement_fields(raw_item)
    data_origin = fields["data_origin"]
    unit = _canonicalize_unit(fields["unit"])
    explicit_period = _canonicalize_period(fields["averaging_period"])
    period = explicit_period or implied_period

    if data_origin == "provider_index" or unit in {"aqi_subindex", "waqi_iaqi_subindex"}:
        return {
            "pollutant": norm_pollutant or pollutant,
            "classification": "provider_index",
            "eligible_for_official_cpcb": False,
            "eligible_for_formula_without_origin": False,
            "eligible_for_provisional": False,
            "averaging_period": period,
            "provider_aqi_subindex": fields["provider_aqi_subindex"],
            "reason": "provider_reported_subindex_excluded_from_concentration_equations",
        }

    numeric = _extract_finite_concentration(fields["value"])
    if numeric is None:
        return {
            "pollutant": norm_pollutant or pollutant,
            "classification": "unavailable_or_insufficient",
            "eligible_for_official_cpcb": False,
            "eligible_for_formula_without_origin": False,
            "eligible_for_provisional": False,
            "averaging_period": period,
            "reason": "missing_or_non_finite_value",
        }

    if norm_pollutant is None:
        return {
            "pollutant": pollutant,
            "classification": "unavailable_or_insufficient",
            "eligible_for_official_cpcb": False,
            "eligible_for_formula_without_origin": False,
            "eligible_for_provisional": False,
            "averaging_period": period,
            "reason": "unsupported_cpcb_pollutant",
        }

    # P1 FIX B: Never clamp negative concentrations to 0.0 (applies uniformly to rich & scalar inputs)
    if numeric < 0:
        return {
            "pollutant": norm_pollutant,
            "classification": "unavailable_or_insufficient",
            "eligible_for_official_cpcb": False,
            "eligible_for_formula_without_origin": False,
            "eligible_for_provisional": False,
            "averaging_period": period,
            "reason": "negative_concentration",
        }

    spec = CPCB_POLLUTANT_SPECS[norm_pollutant]
    expected_period = spec["averaging_period"]

    if data_origin == "model_derived":
        if unit is None:
            return {
                "pollutant": norm_pollutant,
                "classification": "unavailable_or_insufficient",
                "eligible_for_official_cpcb": False,
                "eligible_for_formula_without_origin": False,
                "eligible_for_provisional": False,
                "averaging_period": period,
                "reason": "missing_unit_metadata",
            }
        native_dec, conv_err = _convert_to_cpcb_native_decimal(norm_pollutant, numeric, unit)
        if native_dec is None:
            return {
                "pollutant": norm_pollutant,
                "classification": "model_derived_provisional",
                "eligible_for_official_cpcb": False,
                "eligible_for_formula_without_origin": False,
                "eligible_for_provisional": False,
                "averaging_period": period,
                "reason": conv_err,
            }
        truncated_dec = _truncate_cpcb_decimal(norm_pollutant, native_dec)
        diag_sub = _interpolate_cpcb_subindex(norm_pollutant, truncated_dec)
        return {
            "pollutant": norm_pollutant,
            "classification": "model_derived_provisional",
            "eligible_for_official_cpcb": False,
            "eligible_for_formula_without_origin": False,
            "eligible_for_provisional": True,
            "native_unit": conv_err,
            "raw_native_concentration": float(native_dec),
            "truncated_concentration": float(truncated_dec),
            "averaging_period": period,
            "diagnostic_subindex": diag_sub,
            "reason": "model_derived_provisional_ineligible_for_official_cpcb",
        }

    effective_unit = unit
    if effective_unit is None:
        if fields["has_rich_metadata"]:
            return {
                "pollutant": norm_pollutant,
                "classification": "unavailable_or_insufficient",
                "eligible_for_official_cpcb": False,
                "eligible_for_formula_without_origin": False,
                "eligible_for_provisional": False,
                "native_unit": None,
                "averaging_period": period,
                "reason": "missing_unit_metadata",
            }
        effective_unit = spec["unit"]

    native_dec, conv_err = _convert_to_cpcb_native_decimal(norm_pollutant, numeric, effective_unit)
    if native_dec is None:
        return {
            "pollutant": norm_pollutant,
            "classification": "unavailable_or_insufficient",
            "eligible_for_official_cpcb": False,
            "eligible_for_formula_without_origin": False,
            "eligible_for_provisional": False,
            "averaging_period": period,
            "reason": conv_err,
        }

    truncated_dec = _truncate_cpcb_decimal(norm_pollutant, native_dec)
    sub = _interpolate_cpcb_subindex(norm_pollutant, truncated_dec)
    if sub is None:
        return {
            "pollutant": norm_pollutant,
            "classification": "unavailable_or_insufficient",
            "eligible_for_official_cpcb": False,
            "eligible_for_formula_without_origin": False,
            "eligible_for_provisional": False,
            "native_unit": conv_err if unit is not None else None,
            "averaging_period": period,
            "reason": "outside_cpcb_range",
        }

    # P1 FIX A: Metadata-free scalar inputs are NEVER methodology_eligible and NEVER infer averaging_period
    if not fields["has_rich_metadata"]:
        return {
            "pollutant": norm_pollutant,
            "classification": "unavailable_or_insufficient",
            "eligible_for_official_cpcb": False,
            "eligible_for_formula_without_origin": True,
            "eligible_for_provisional": False,
            "native_unit": None,
            "formula_unit": conv_err,
            "raw_native_concentration": float(native_dec),
            "truncated_concentration": float(truncated_dec),
            "averaging_period": None,
            "subindex": sub,
            "reason": "scalar_formula_input_without_origin_or_averaging_metadata",
        }

    if implied_period is not None and explicit_period is not None and explicit_period != implied_period:
        return {
            "pollutant": norm_pollutant,
            "classification": "unavailable_or_insufficient",
            "eligible_for_official_cpcb": False,
            "eligible_for_formula_without_origin": False,
            "eligible_for_provisional": False,
            "native_unit": conv_err,
            "averaging_period": explicit_period,
            "expected_averaging_period": implied_period,
            "diagnostic_subindex": sub,
            "reason": "contradictory_key_and_averaging_period",
        }

    is_o3_1h = norm_pollutant == "o3" and period == "1h"
    if not is_o3_1h and period != expected_period:
        return {
            "pollutant": norm_pollutant,
            "classification": "unavailable_or_insufficient",
            "eligible_for_official_cpcb": False,
            "eligible_for_formula_without_origin": False,
            "eligible_for_provisional": False,
            "native_unit": conv_err,
            "averaging_period": period,
            "expected_averaging_period": expected_period,
            "diagnostic_subindex": sub,
            "reason": "missing_or_ineligible_averaging_period",
        }

    if data_origin != "measured":
        return {
            "pollutant": norm_pollutant,
            "classification": "unavailable_or_insufficient",
            "eligible_for_official_cpcb": False,
            "eligible_for_formula_without_origin": False,
            "eligible_for_provisional": False,
            "native_unit": conv_err,
            "averaging_period": period,
            "diagnostic_subindex": sub,
            "reason": "unverified_or_non_measured_data_origin",
        }

    if is_o3_1h:
        comp_1h_ok, comp_1h_reason, comp_1h_meta = _validate_cpcb_1h_ozone_completeness(fields)
        return _attach_o3_pairing_metadata(
            {
                "pollutant": "o3",
                "classification": "unavailable_or_insufficient",
                "eligible_for_official_cpcb": False,
                "eligible_for_formula_without_origin": False,
                "eligible_for_provisional": False,
                "eligible_1h_candidate": comp_1h_ok,
                "native_unit": conv_err,
                "raw_native_concentration": float(native_dec),
                "truncated_concentration": float(truncated_dec),
                "averaging_period": "1h",
                "completeness": comp_1h_meta,
                "diagnostic_subindex": sub,
                "reason": (
                    "isolated_1h_o3_cannot_prove_8h_exceeds_208_trigger"
                    if comp_1h_ok
                    else comp_1h_reason
                ),
            },
            fields,
        )

    # P1 FIX C: Require evidence of >=16h data completeness before methodology_eligible classification
    completeness_ok, completeness_reason, completeness_meta = _validate_cpcb_16h_completeness(fields)
    if not completeness_ok:
        return {
            "pollutant": norm_pollutant,
            "classification": "unavailable_or_insufficient",
            "eligible_for_official_cpcb": False,
            "eligible_for_formula_without_origin": False,
            "eligible_for_provisional": False,
            "native_unit": conv_err,
            "raw_native_concentration": float(native_dec),
            "truncated_concentration": float(truncated_dec),
            "averaging_period": period,
            "completeness": completeness_meta,
            "diagnostic_subindex": sub,
            "reason": completeness_reason,
        }

    if norm_pollutant == "o3" and truncated_dec > Decimal("208"):
        return _attach_o3_pairing_metadata(
            {
                "pollutant": "o3",
                "classification": "unavailable_or_insufficient",
                "eligible_for_official_cpcb": False,
                "eligible_for_formula_without_origin": False,
                "eligible_for_provisional": False,
                "o3_8h_trigger_exceeded": True,
                "native_unit": conv_err,
                "raw_native_concentration": float(native_dec),
                "truncated_concentration": float(truncated_dec),
                "averaging_period": "8h",
                "completeness": completeness_meta,
                "diagnostic_subindex": sub,
                "reason": "o3_8h_exceeds_208_requires_eligible_1h_observation",
            },
            fields,
        )

    eligible_result: Dict[str, Any] = {
        "pollutant": norm_pollutant,
        "classification": "methodology_eligible",
        "eligible_for_official_cpcb": True,
        "eligible_for_formula_without_origin": False,
        "eligible_for_provisional": False,
        "native_unit": conv_err,
        "raw_native_concentration": float(native_dec),
        "truncated_concentration": float(truncated_dec),
        "averaging_period": period,
        "completeness": completeness_meta,
        "subindex": sub,
        "reason": "measured_native_concentration_methodology_eligible",
    }
    if norm_pollutant == "o3":
        return _attach_o3_pairing_metadata(eligible_result, fields)
    return eligible_result


def _attach_o3_pairing_metadata(prov: Dict[str, Any], fields: Dict[str, Any]) -> Dict[str, Any]:
    raw_ts = fields.get("observation_timestamp")
    parsed_utc, dt_origin, _ = _parse_cpcb_utc_timestamp_with_origin(raw_ts)
    if parsed_utc is not None and dt_origin is not None:
        formatted_ts: Any = dt_origin.isoformat() if isinstance(raw_ts, str) or dt_origin.utcoffset() != timedelta(0) else parsed_utc.isoformat().replace("+00:00", "Z")
        formatted_utc: Optional[str] = parsed_utc.isoformat().replace("+00:00", "Z")
    else:
        formatted_ts = raw_ts
        formatted_utc = None

    prov["station_id"] = fields.get("station_id")
    if fields.get("conflicting_station_id"):
        prov["conflicting_station_id"] = True
    if fields.get("explicit_station_id_malformed"):
        prov["explicit_station_id_malformed"] = True
    if fields.get("station_namespace") is not None:
        prov["station_namespace"] = fields.get("station_namespace")
    if fields.get("conflicting_station_namespace"):
        prov["conflicting_station_namespace"] = True
    if fields.get("explicit_namespace_malformed"):
        prov["explicit_namespace_malformed"] = True
    if fields.get("shared_station_id") is not None:
        prov["shared_station_id"] = fields.get("shared_station_id")
    if fields.get("explicit_shared_id_malformed"):
        prov["explicit_shared_id_malformed"] = True
    if fields.get("sensor_id") is not None:
        prov["sensor_id"] = fields.get("sensor_id")
    prov["source"] = fields.get("source")
    prov["observation_timestamp"] = formatted_ts
    if formatted_utc is not None:
        prov["observation_timestamp_utc"] = formatted_utc
    if fields.get("reporting_date") is not None:
        prov["reporting_date"] = fields.get("reporting_date")
    if fields.get("reporting_date_timezone") is not None:
        prov["reporting_date_timezone"] = fields.get("reporting_date_timezone")
    if fields.get("timestamp_semantics") is not None:
        prov["timestamp_semantics"] = fields.get("timestamp_semantics")
    if fields.get("window_start") is not None:
        prov["window_start"] = fields.get("window_start")
    if fields.get("window_end") is not None:
        prov["window_end"] = fields.get("window_end")
    return prov


def _resolve_crosswalk_target(
    station_crosswalk: Optional[Dict[Any, str]],
    namespace: Optional[str],
    station_id: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    """
    No server-controlled authoritative station crosswalk registry currently exists in AeroSense AI.
    Validates syntax of caller-supplied mappings if passed, but refuses to treat untrusted/caller
    dictionaries as authoritative cross-provider identity.
    """
    if not isinstance(station_crosswalk, dict) or not namespace or not station_id:
        return None, None
    return None, "unverified_caller_crosswalk"


def _validate_cpcb_station_pair(
    p8h_prov: Dict[str, Any],
    p1h_prov: Dict[str, Any],
    station_crosswalk: Optional[Dict[Any, str]] = None,
) -> Tuple[bool, str]:
    """
    Validates defensible same physical monitoring-station identity across paired 8h and 1h O3.
    - Rejects any conflicting explicit identity or namespace aliases fail closed.
    - Rejects malformed explicit station/namespace/shared metadata fail closed.
    - Requires verified provider/network namespace scoping (never permits self-declared global scope).
    - Fails closed across distinct provider namespaces until a server-controlled trusted crosswalk
      registry exists (caller-supplied crosswalks or `shared_station_id` alone never authorize pairing).
    - Rejects one-sided or conflicting `shared_station_id` consistently.
    - Never treats `sensor_id`, display names, `#N` tokens, or generic `source` strings as station identity.
    """
    if p8h_prov.get("conflicting_station_id") or p1h_prov.get("conflicting_station_id"):
        return False, "o3_pair_conflicting_station_identity_metadata"
    if p8h_prov.get("conflicting_station_namespace") or p1h_prov.get("conflicting_station_namespace"):
        return False, "o3_pair_conflicting_station_namespace_metadata"
    if (
        p8h_prov.get("explicit_station_id_malformed")
        or p1h_prov.get("explicit_station_id_malformed")
        or p8h_prov.get("explicit_namespace_malformed")
        or p1h_prov.get("explicit_namespace_malformed")
        or p8h_prov.get("explicit_shared_id_malformed")
        or p1h_prov.get("explicit_shared_id_malformed")
    ):
        return False, "o3_pair_malformed_station_identity"

    id_8h = p8h_prov.get("station_id")
    id_1h = p1h_prov.get("station_id")
    ns_8h = p8h_prov.get("station_namespace")
    ns_1h = p1h_prov.get("station_namespace")
    shared_8h = p8h_prov.get("shared_station_id")
    shared_1h = p1h_prov.get("shared_station_id")

    if not id_8h or not id_1h:
        return False, "o3_pair_missing_station_id"

    if not ns_8h or not ns_1h:
        return False, "o3_pair_unscoped_station_id"

    if ns_8h != ns_1h:
        return False, "o3_pair_cross_provider_without_trusted_crosswalk"

    if id_8h != id_1h:
        return False, "o3_pair_different_station_id"

    if (shared_8h is not None or shared_1h is not None) and shared_8h != shared_1h:
        return False, "o3_pair_different_shared_station_id"

    return True, "paired_same_scoped_station_id"


def _validate_interval_and_timestamp_consistency(
    prefix: str,
    prov: Dict[str, Any],
    w_start: datetime,
    w_start_origin: datetime,
    w_end: datetime,
    w_end_origin: datetime,
) -> Tuple[bool, Optional[str]]:
    """
    Validates optional `timestamp_semantics`, supplied `observation_timestamp`, and `reporting_date`
    against explicit interval bounds `[w_start, w_end]`.
    """
    sem_raw = prov.get("timestamp_semantics")
    sem: Optional[str] = None
    if sem_raw is not None:
        sem = str(sem_raw).strip().casefold()
        if sem not in _SUPPORTED_TIMESTAMP_SEMANTICS:
            return False, f"{prefix}_unsupported_timestamp_semantics"

    raw_ts = prov.get("observation_timestamp")
    anchor_utc = w_end
    anchor_origin = w_end_origin
    anchor_raw_ts: Any = prov.get("window_end")

    if raw_ts is not None:
        ts_utc, ts_origin, ts_err = _parse_cpcb_utc_timestamp_with_origin(raw_ts, is_interval_bound=False)
        if ts_err is not None or ts_utc is None or ts_origin is None:
            return False, f"{prefix}_{ts_err or 'malformed_observation_timestamp'}"
        if sem == "period_end" and ts_utc != w_end:
            return False, f"{prefix}_contradictory_observation_timestamp"
        if sem == "period_start" and ts_utc != w_start:
            return False, f"{prefix}_contradictory_observation_timestamp"
        if ts_utc < w_start or ts_utc > w_end:
            return False, f"{prefix}_contradictory_observation_timestamp"
        anchor_utc = ts_utc
        anchor_origin = ts_origin
        anchor_raw_ts = raw_ts

    r_ok, r_err, r_amb = _validate_single_reporting_date(
        prefix,
        anchor_raw_ts,
        anchor_utc,
        anchor_origin,
        prov.get("reporting_date"),
        prov.get("reporting_date_timezone"),
    )
    if r_amb:
        prov["reporting_date_ambiguity"] = r_amb
    if not r_ok and r_err:
        return False, r_err
    return True, None


def _validate_cpcb_o3_pair(
    p8h_prov: Dict[str, Any],
    p1h_prov: Dict[str, Any],
    *,
    station_crosswalk: Optional[Dict[Any, str]] = None,
) -> Tuple[bool, str]:
    """
    Validates that an 8-hour (>208 ug/m3) O3 observation and a candidate 1-hour O3 observation
    share a verified physical monitoring station and have explicit, timezone-aware averaging intervals
    where the 1-hour interval (`window_end - window_start == 1h`) is fully contained inside the
    8-hour interval (`window_end - window_start == 8h`).
    """
    st_ok, st_reason = _validate_cpcb_station_pair(p8h_prov, p1h_prov, station_crosswalk=station_crosswalk)
    if not st_ok:
        return False, st_reason

    w8_start_raw = p8h_prov.get("window_start")
    w8_end_raw = p8h_prov.get("window_end")
    if w8_start_raw is None or w8_end_raw is None:
        return False, "o3_8h_missing_interval_bounds"

    w1_start_raw = p1h_prov.get("window_start")
    w1_end_raw = p1h_prov.get("window_end")
    if w1_start_raw is None or w1_end_raw is None:
        return False, "o3_1h_missing_interval_bounds"

    w8_start, w8_start_origin, err = _parse_cpcb_utc_timestamp_with_origin(w8_start_raw, is_interval_bound=True)
    if err or w8_start is None or w8_start_origin is None:
        return False, f"o3_8h_{err}"
    w8_end, w8_end_origin, err = _parse_cpcb_utc_timestamp_with_origin(w8_end_raw, is_interval_bound=True)
    if err or w8_end is None or w8_end_origin is None:
        return False, f"o3_8h_{err}"

    w1_start, w1_start_origin, err = _parse_cpcb_utc_timestamp_with_origin(w1_start_raw, is_interval_bound=True)
    if err or w1_start is None or w1_start_origin is None:
        return False, f"o3_1h_{err}"
    w1_end, w1_end_origin, err = _parse_cpcb_utc_timestamp_with_origin(w1_end_raw, is_interval_bound=True)
    if err or w1_end is None or w1_end_origin is None:
        return False, f"o3_1h_{err}"

    if (w8_end - w8_start) != timedelta(hours=8):
        return False, "o3_8h_invalid_interval_duration"
    if (w1_end - w1_start) != timedelta(hours=1):
        return False, "o3_1h_invalid_interval_duration"

    if w1_start < w8_start or w1_end > w8_end:
        return False, "o3_pair_1h_interval_outside_8h_interval"

    ts8_ok, ts8_err = _validate_interval_and_timestamp_consistency(
        "o3_8h", p8h_prov, w8_start, w8_start_origin, w8_end, w8_end_origin
    )
    if not ts8_ok and ts8_err:
        return False, ts8_err

    ts1_ok, ts1_err = _validate_interval_and_timestamp_consistency(
        "o3_1h", p1h_prov, w1_start, w1_start_origin, w1_end, w1_end_origin
    )
    if not ts1_ok and ts1_err:
        return False, ts1_err

    return True, "paired_verified_station_and_interval"


def calculate_india_cpcb_aqi(
    measurements: Dict[str, Any],
    *,
    measurement_metadata: Optional[Dict[str, Any]] = None,
    model_derived_aggregates: Optional[Dict[str, Any]] = None,
    station_crosswalk: Optional[Dict[Any, str]] = None,
) -> Dict[str, Any]:
    """
    Computes India CPCB NAQI (CUPS/82/2014-15).
    Strictly enforces: minimum 3 eligible pollutants with at least one particulate matter
    (PM2.5 or PM10), plus verified scoped station & explicit interval bounds (`window_start`, `window_end`)
    when 8h O3 > 208 ug/m3 triggers paired 1h O3 evaluation.

    Provider limitation note:
    Live OpenAQ v3, WAQI, and Open-Meteo ingestion streams do not currently supply concurrent
    8-hour and 1-hour measured O3 intervals with explicit interval bounds, so paired CPCB 1h O3
    eligibility remains unavailable on those live provider payloads rather than retrofitting single
    timestamps into averaging intervals.

    Note on reliability vs methodology eligibility flags:
    - `is_reliable`: mathematical concentration sufficiency for deterministic formula
      execution (True when >=3 finite non-negative pollutant inputs incl. PM produce an index).
    - `is_methodology_eligible`: True ONLY for verified measured concentrations with valid native
      units, averaging periods, >=16h capture completeness, and valid O3 pairing (False in formula-only mode).
    - `is_regulatory_compliant`: False unless backed by formal CPCB monitoring infrastructure.
    """
    eligible_subindices: Dict[str, int] = {}
    formula_subindices: Dict[str, int] = {}
    diagnostic_subindices: Dict[str, int] = {}
    pollutant_provenance: Dict[str, Dict[str, Any]] = {}

    source_items = measurement_metadata if isinstance(measurement_metadata, dict) else measurements
    o3_8h_triggered_keys: List[str] = []
    o3_8h_eligible_keys: List[str] = []
    o3_1h_candidate_keys: List[str] = []

    if isinstance(source_items, dict):
        for raw_key, raw_item in source_items.items():
            raw_lower = str(raw_key).lower()
            info = classify_cpcb_measurement_eligibility(str(raw_key), raw_item)
            pollutant_provenance[raw_lower] = info
            norm_key = info.get("pollutant")

            if info.get("eligible_for_official_cpcb") and info.get("subindex") is not None and isinstance(norm_key, str):
                sub_val = int(info["subindex"])
                eligible_subindices[norm_key] = max(eligible_subindices.get(norm_key, -1), sub_val)
                diagnostic_subindices[norm_key] = max(diagnostic_subindices.get(norm_key, -1), sub_val)
                if norm_key == "o3":
                    o3_8h_eligible_keys.append(raw_lower)
            elif info.get("o3_8h_trigger_exceeded"):
                o3_8h_triggered_keys.append(raw_lower)
                if info.get("diagnostic_subindex") is not None:
                    diagnostic_subindices["o3"] = max(diagnostic_subindices.get("o3", -1), int(info["diagnostic_subindex"]))
            elif info.get("eligible_1h_candidate"):
                o3_1h_candidate_keys.append(raw_lower)
                if info.get("diagnostic_subindex") is not None:
                    diagnostic_subindices["o3"] = max(diagnostic_subindices.get("o3", -1), int(info["diagnostic_subindex"]))
            elif info.get("eligible_for_formula_without_origin") and info.get("subindex") is not None and isinstance(norm_key, str):
                sub_val = int(info["subindex"])
                formula_subindices[norm_key] = max(formula_subindices.get(norm_key, -1), sub_val)
                diagnostic_subindices[norm_key] = max(diagnostic_subindices.get(norm_key, -1), sub_val)
            elif info.get("diagnostic_subindex") is not None and isinstance(norm_key, str):
                diagnostic_subindices[norm_key] = max(
                    diagnostic_subindices.get(norm_key, -1),
                    int(info["diagnostic_subindex"]),
                )

    # Resolve conditional CPCB Table 3.1 O3 footnote:
    # When verified 8h O3 > 208 ug/m3 (truncated Cp), switch ONLY to a station- & window-paired measured 1h O3.
    ozone_selection_basis: Optional[str] = None
    if o3_8h_triggered_keys and o3_1h_candidate_keys:
        best_1h_sub: Optional[int] = None
        matched_1h_keys: set[str] = set()
        rejected_1h_reasons: Dict[str, List[str]] = {k1h: [] for k1h in o3_1h_candidate_keys}
        rejected_8h_reasons: Dict[str, List[str]] = {k8h: [] for k8h in o3_8h_triggered_keys}

        for k8h in o3_8h_triggered_keys:
            p8h = pollutant_provenance[k8h]
            paired_1h_for_k8h: List[str] = []
            for k1h in o3_1h_candidate_keys:
                p1h = pollutant_provenance[k1h]
                sub_1h = p1h.get("diagnostic_subindex")
                if sub_1h is None:
                    rejected_1h_reasons[k1h].append("o3_1h_subindex_unavailable")
                    continue
                pair_ok, pair_reason = _validate_cpcb_o3_pair(p8h, p1h, station_crosswalk=station_crosswalk)
                if not pair_ok:
                    rejected_1h_reasons[k1h].append(pair_reason)
                    rejected_8h_reasons[k8h].append(pair_reason)
                    continue
                best_1h_sub = max(best_1h_sub, int(sub_1h)) if best_1h_sub is not None else int(sub_1h)
                matched_1h_keys.add(k1h)
                paired_1h_for_k8h.append(k1h)
                p1h["classification"] = "methodology_eligible"
                p1h["eligible_for_official_cpcb"] = True
                p1h["subindex"] = int(sub_1h)
                p1h["paired_8h_key"] = k8h
                p1h["reason"] = "o3_1h_used_because_8h_exceeds_208"
            if paired_1h_for_k8h:
                p8h["paired_1h_key"] = paired_1h_for_k8h[0] if len(paired_1h_for_k8h) == 1 else paired_1h_for_k8h
                p8h["reason"] = "o3_8h_exceeded_208_superseded_by_paired_1h"

        for k1h in o3_1h_candidate_keys:
            if k1h not in matched_1h_keys and rejected_1h_reasons[k1h]:
                p1h = pollutant_provenance[k1h]
                p1h["eligible_for_official_cpcb"] = False
                p1h["pairing_rejection_reason"] = rejected_1h_reasons[k1h][0]
                p1h["reason"] = rejected_1h_reasons[k1h][0]

        if best_1h_sub is not None and matched_1h_keys:
            eligible_subindices["o3"] = best_1h_sub
            diagnostic_subindices["o3"] = max(diagnostic_subindices.get("o3", -1), best_1h_sub)
            ozone_selection_basis = "o3_1h_after_8h_exceeds_208"
        else:
            eligible_subindices.pop("o3", None)
            for k8h in o3_8h_triggered_keys:
                if rejected_8h_reasons[k8h]:
                    pollutant_provenance[k8h]["pairing_rejection_reason"] = rejected_8h_reasons[k8h][0]
                    pollutant_provenance[k8h]["reason"] = "o3_8h_exceeds_208_requires_compatible_paired_1h_observation"
            ozone_selection_basis = "unavailable_incompatible_paired_1h_after_8h_above_208"
    elif o3_8h_triggered_keys:
        # 8h > 208 triggered, but no eligible measured 1h O3 available -> O3 excluded from official NAQI.
        eligible_subindices.pop("o3", None)
        ozone_selection_basis = "unavailable_missing_eligible_1h_after_8h_above_208"
    elif o3_8h_eligible_keys:
        for k1h in o3_1h_candidate_keys:
            pollutant_provenance[k1h]["reason"] = "o3_8h_does_not_exceed_208_1h_not_applicable"
        ozone_selection_basis = "o3_8h_standard"
    elif o3_1h_candidate_keys:
        ozone_selection_basis = "unavailable_isolated_1h_cannot_prove_8h_trigger"

    provisional_estimates: Dict[str, Any] = {}
    if isinstance(model_derived_aggregates, dict) and isinstance(model_derived_aggregates.get("o3_8h"), dict):
        o3_8h_agg = model_derived_aggregates["o3_8h"]
        diag_o3_sub = (
            calculate_cpcb_subindex("o3", o3_8h_agg.get("value"), unit=o3_8h_agg.get("unit"), averaging_period="8h")
            if o3_8h_agg.get("status") == "available"
            else None
        )
        provisional_estimates["o3_8h"] = {
            "status": o3_8h_agg.get("status"),
            "value": o3_8h_agg.get("value"),
            "unit": o3_8h_agg.get("unit"),
            "averaging_period": o3_8h_agg.get("averaging_period", "8h"),
            "valid_hours": o3_8h_agg.get("valid_hours"),
            "expected_hours": o3_8h_agg.get("expected_hours"),
            "completeness_ratio": o3_8h_agg.get("completeness_ratio"),
            "completeness_policy": o3_8h_agg.get("completeness_policy"),
            "data_origin": "model_derived",
            "is_regulatory_observation": False,
            "is_official_cpcb_naqi": False,
            "classification": "model_derived_provisional",
            "diagnostic_cpcb_subindex": diag_o3_sub,
        }
        if diag_o3_sub is not None and "o3" not in diagnostic_subindices:
            diagnostic_subindices["o3"] = diag_o3_sub

    is_formula_only_mode = bool(formula_subindices) and not bool(eligible_subindices) and not isinstance(measurement_metadata, dict)
    active_subindices = formula_subindices if is_formula_only_mode else eligible_subindices

    has_pm = "pm25" in active_subindices or "pm10" in active_subindices
    eligible_count = len(active_subindices)
    meets_minimum_rule = eligible_count >= 3 and has_pm

    requirement_status = {
        "minimum_required": 3,
        "requires_particulate": True,
        "eligible_count": len(eligible_subindices),
        "formula_input_count": len(formula_subindices),
        "eligible_pollutants": sorted(eligible_subindices.keys()),
        "formula_pollutants": sorted(formula_subindices.keys()),
        "has_particulate": has_pm,
        "satisfied": meets_minimum_rule,
    }

    if not meets_minimum_rule:
        if not has_pm:
            reason_msg = (
                "Official CPCB NAQI unavailable: requires at least 3 eligible pollutants "
                "including PM2.5 or PM10 (no eligible particulate pollutant available)."
            )
        else:
            reason_msg = (
                f"Official CPCB NAQI unavailable: requires at least 3 eligible pollutants "
                f"including PM2.5 or PM10 (only {eligible_count} eligible pollutant(s) available)."
            )
        return {
            "standard": "INDIA_CPCB",
            "methodology_version": CPCB_METHODOLOGY_VERSION,
            "aqi": None,
            "category": "Unavailable",
            "dominant_pollutant": None,
            "color": "#64748b",
            "subindices": active_subindices,
            "diagnostic_subindices": diagnostic_subindices,
            "advisory": reason_msg,
            "is_reliable": False,
            "is_methodology_eligible": False,
            "is_formula_only": is_formula_only_mode,
            "is_regulatory_compliant": False,
            "calculation_basis": "unavailable",
            "ozone_selection_basis": ozone_selection_basis,
            "minimum_pollutant_requirement": requirement_status,
            "pollutant_provenance": pollutant_provenance,
            "provisional_estimates": provisional_estimates or None,
            "compliance_disclaimer": CPCB_COMPLIANCE_DISCLAIMER,
        }

    dominant_pollutant = max(active_subindices, key=active_subindices.get)
    overall_aqi = min(500, max(0, active_subindices[dominant_pollutant]))
    category, color, advisory = get_cpcb_category(overall_aqi)

    if is_formula_only_mode:
        calculation_basis = "formula_input_unverified_origin"
        is_methodology_eligible = False
        advisory = (
            f"Formula-only calculation (unverified unit, averaging period, and 16h completeness; "
            f"not an observed CPCB NAQI determination): {advisory}"
        )
    else:
        calculation_basis = "methodology_eligible"
        is_methodology_eligible = True

    return {
        "standard": "INDIA_CPCB",
        "methodology_version": CPCB_METHODOLOGY_VERSION,
        "aqi": overall_aqi,
        "category": category,
        "dominant_pollutant": dominant_pollutant.upper(),
        "color": color,
        "subindices": active_subindices,
        "diagnostic_subindices": diagnostic_subindices,
        "advisory": advisory,
        "is_reliable": True,
        "is_methodology_eligible": is_methodology_eligible,
        "is_formula_only": is_formula_only_mode,
        "is_regulatory_compliant": False,
        "calculation_basis": calculation_basis,
        "ozone_selection_basis": ozone_selection_basis,
        "minimum_pollutant_requirement": requirement_status,
        "pollutant_provenance": pollutant_provenance,
        "provisional_estimates": provisional_estimates or None,
        "compliance_disclaimer": CPCB_COMPLIANCE_DISCLAIMER,
    }
