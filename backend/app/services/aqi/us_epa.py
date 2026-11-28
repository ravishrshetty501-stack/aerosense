from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, localcontext
import math
from typing import Any, Dict, List, Optional, Tuple

"""
US EPA Air Quality Index (AQI) Calculation Methodology
Authoritative References:
- 40 CFR Part 58, Appendix G: Uniform Air Quality Index (AQI) and Daily Reporting
  (incorporating the May 2024 PM2.5 NAAQS / AQI Final Rule update)
- US EPA Technical Assistance Document for the Reporting of Daily Air Quality -
  the Air Quality Index (AQI) (EPA-454/B-24-002, May 2024)

Key Methodology Transition Note (2012/EPA-454/B-18-007 -> May 2024/EPA-454/B-24-002):
- PM2.5 (24-hr avg, ug/m3): Good upper bound tightened 12.0 -> 9.0; Moderate lower
  bound shifted 12.1 -> 9.1 (9.1-35.4); Unhealthy upper bound tightened 150.4 -> 125.4;
  Very Unhealthy shifted 150.5-250.4 -> 125.5-225.4; Hazardous merged to 225.5-325.4 (301-500).
- Native gas units preserved without STP mass conversions:
  O3 (ppm, truncated to 0.001), CO (ppm, truncated to 0.1),
  NO2 (ppb, truncated to 1), SO2 (ppb, truncated to 1).
- Values exceeding the concentration at AQI 500 are extrapolated via Equation 1
  using the final 500-ending breakpoint segment and rounded half-up to the nearest integer
  (never capped at 500). 8-hr O3 (capped at 300) and 1-hr SO2 (capped at 200) do not
  define higher AQI tiers and require 1-hr O3 / 24-hr SO2 respectively.
"""

EPA_METHODOLOGY_VERSION = "40_CFR_Part_58_Appendix_G_May_2024"
EPA_COMPLIANCE_DISCLAIMER = (
    "Formula calculations align with 40 CFR Part 58 Appendix G (May 2024) breakpoints and Equation 1; "
    "formula execution alone does not constitute formal regulatory agency compliance or NAAQS determination."
)

_EPA_QUANTIZERS: Dict[str, Decimal] = {
    "pm25": Decimal("0.1"),
    "pm10": Decimal("1"),
    "o3": Decimal("0.001"),
    "co": Decimal("0.1"),
    "so2": Decimal("1"),
    "no2": Decimal("1"),
}

# Breakpoint tables: [(Cp_low, Cp_high, I_low, I_high)] in official EPA native units.
EPA_PM25_BREAKPOINTS: List[Tuple[float, float, int, int]] = [  # ug/m3, 24-hr (May 2024)
    (0.0, 9.0, 0, 50),
    (9.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 125.4, 151, 200),
    (125.5, 225.4, 201, 300),
    (225.5, 325.4, 301, 500),
]

EPA_PM10_BREAKPOINTS: List[Tuple[int, int, int, int]] = [  # ug/m3, 24-hr
    (0, 54, 0, 50),
    (55, 154, 51, 100),
    (155, 254, 101, 150),
    (255, 354, 151, 200),
    (355, 424, 201, 300),
    (425, 504, 301, 400),
    (505, 604, 401, 500),
]

# Footnote 2: 8-hr O3 defines AQI 0-300 only; AQI > 300 requires 1-hr O3.
EPA_O3_8H_BREAKPOINTS: List[Tuple[float, float, int, int]] = [  # ppm, 8-hr
    (0.000, 0.054, 0, 50),
    (0.055, 0.070, 51, 100),
    (0.071, 0.085, 101, 150),
    (0.086, 0.105, 151, 200),
    (0.106, 0.200, 201, 300),
]

# Footnote 1: 1-hr O3 defines AQI 101-500 (+ extrapolation >500); does not define 0-100.
EPA_O3_1H_BREAKPOINTS: List[Tuple[float, float, int, int]] = [  # ppm, 1-hr
    (0.125, 0.164, 101, 150),
    (0.165, 0.204, 151, 200),
    (0.205, 0.404, 201, 300),
    (0.405, 0.504, 301, 400),
    (0.505, 0.604, 401, 500),
]

EPA_CO_BREAKPOINTS: List[Tuple[float, float, int, int]] = [  # ppm, 8-hr
    (0.0, 4.4, 0, 50),
    (4.5, 9.4, 51, 100),
    (9.5, 12.4, 101, 150),
    (12.5, 15.4, 151, 200),
    (15.5, 30.4, 201, 300),
    (30.5, 40.4, 301, 400),
    (40.5, 50.4, 401, 500),
]

# Footnote 3: 1-hr SO2 defines AQI 0-200 only; AQI >= 201 requires 24-hr SO2.
EPA_SO2_1H_BREAKPOINTS: List[Tuple[int, int, int, int]] = [  # ppb, 1-hr
    (0, 35, 0, 50),
    (36, 75, 51, 100),
    (76, 185, 101, 150),
    (186, 304, 151, 200),
]

EPA_SO2_24H_BREAKPOINTS: List[Tuple[int, int, int, int]] = [  # ppb, 24-hr
    (305, 604, 201, 300),
    (605, 804, 301, 400),
    (805, 1004, 401, 500),
]

EPA_NO2_BREAKPOINTS: List[Tuple[int, int, int, int]] = [  # ppb, 1-hr
    (0, 53, 0, 50),
    (54, 100, 51, 100),
    (101, 360, 101, 150),
    (361, 649, 151, 200),
    (650, 1249, 201, 300),
    (1250, 1649, 301, 400),
    (1650, 2049, 401, 500),
]

EPA_BREAKPOINTS: Dict[str, List[Tuple[float, float, int, int]]] = {
    "pm25": EPA_PM25_BREAKPOINTS,
    "pm10": EPA_PM10_BREAKPOINTS,
    "o3": EPA_O3_8H_BREAKPOINTS,
    "o3_8h": EPA_O3_8H_BREAKPOINTS,
    "o3_1h": EPA_O3_1H_BREAKPOINTS,
    "co": EPA_CO_BREAKPOINTS,
    "so2": EPA_SO2_1H_BREAKPOINTS,
    "so2_1h": EPA_SO2_1H_BREAKPOINTS,
    "so2_24h": EPA_SO2_24H_BREAKPOINTS,
    "no2": EPA_NO2_BREAKPOINTS,
}

EPA_POLLUTANT_SPECS: Dict[str, Dict[str, Any]] = {
    "pm25": {"unit": "ug/m3", "averaging_period": "24h", "truncation": "0.1", "extrapolate_above_500": True},
    "pm10": {"unit": "ug/m3", "averaging_period": "24h", "truncation": "1", "extrapolate_above_500": True},
    "o3_8h": {"unit": "ppm", "averaging_period": "8h", "truncation": "0.001", "extrapolate_above_500": False, "max_aqi": 300},
    "o3_1h": {"unit": "ppm", "averaging_period": "1h", "truncation": "0.001", "extrapolate_above_500": True, "min_aqi": 101},
    "co": {"unit": "ppm", "averaging_period": "8h", "truncation": "0.1", "extrapolate_above_500": True},
    "so2_1h": {"unit": "ppb", "averaging_period": "1h", "truncation": "1", "extrapolate_above_500": False, "max_aqi": 200},
    "so2_24h": {"unit": "ppb", "averaging_period": "24h", "truncation": "1", "extrapolate_above_500": True, "min_aqi": 201},
    "no2": {"unit": "ppb", "averaging_period": "1h", "truncation": "1", "extrapolate_above_500": True},
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
    "nowcast": "nowcast",
    "instantaneous": "instantaneous",
    "unknown": "unknown",
    "provider_reported": "provider_reported",
}


def get_epa_category(aqi: int) -> Tuple[str, str, str]:
    """Returns (category_name, hex_color, health_advisory) for EPA AQI values (including >500)."""
    if aqi <= 50:
        return "Good", "#10b981", "Air quality is satisfactory, and air pollution poses little or no risk."
    elif aqi <= 100:
        return "Moderate", "#f59e0b", "Air quality is acceptable. Unusually sensitive people should consider reducing prolonged outdoor exertion."
    elif aqi <= 150:
        return "Unhealthy for Sensitive Groups", "#f97316", "Members of sensitive groups may experience health effects. The general public is less likely to be affected."
    elif aqi <= 200:
        return "Unhealthy", "#ef4444", "Some members of the general public may experience health effects; sensitive groups may experience more serious effects."
    elif aqi <= 300:
        return "Very Unhealthy", "#8b5cf6", "Health alert: The risk of health effects is increased for everyone."
    elif aqi <= 500:
        return "Hazardous", "#7f1d1d", "Health warning of emergency conditions: everyone is more likely to be affected."
    else:
        return (
            "Hazardous",
            "#7f1d1d",
            "Beyond the AQI (>500): extreme hazardous air quality emergency conditions; everyone should avoid outdoor exertion.",
        )


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


def _canonicalize_pollutant(raw_pollutant: str) -> Tuple[Optional[str], Optional[str]]:
    """Map pollutant identifier to (base_pollutant, implied_averaging_period)."""
    cleaned = raw_pollutant.strip().lower().replace(".", "").replace("-", "_")
    if cleaned in {"pm25", "pm2_5"}:
        return "pm25", None
    if cleaned == "pm10":
        return "pm10", None
    if cleaned in {"o3", "ozone"}:
        return "o3", None
    if cleaned in {"o3_8h", "o38h", "o3_8hr"}:
        return "o3", "8h"
    if cleaned in {"o3_1h", "o31h", "o3_1hr"}:
        return "o3", "1h"
    if cleaned == "co":
        return "co", None
    if cleaned == "no2":
        return "no2", None
    if cleaned == "so2":
        return "so2", None
    if cleaned in {"so2_1h", "so21h", "so2_1hr"}:
        return "so2", "1h"
    if cleaned in {"so2_24h", "so224h", "so2_24hr"}:
        return "so2", "24h"
    return None, None


def _convert_to_epa_native_decimal(
    base_pollutant: str,
    numeric: float,
    canonical_unit: str,
) -> Tuple[Optional[Decimal], Optional[str]]:
    """
    Convert finite concentration to EPA native unit using exact SI ratios only.
    Never invents STP/ambient temperature-pressure conversions between mass and volumetric gas units.
    """
    dec = Decimal(str(numeric))
    if base_pollutant in {"pm25", "pm10"}:
        if canonical_unit == "ug/m3":
            return dec, "ug/m3"
        if canonical_unit == "mg/m3":
            return dec * Decimal("1000"), "ug/m3"
        return None, f"unsupported_unit_{canonical_unit}_requires_ug_m3"

    if base_pollutant in {"o3", "co"}:
        if canonical_unit == "ppm":
            return dec, "ppm"
        if canonical_unit == "ppb":
            return dec / Decimal("1000"), "ppm"
        if canonical_unit in {"ug/m3", "mg/m3"}:
            return None, f"mass_unit_{canonical_unit}_ineligible_without_ambient_tp_for_ppm"
        return None, f"unsupported_unit_{canonical_unit}_requires_ppm_or_ppb"

    if base_pollutant in {"no2", "so2"}:
        if canonical_unit == "ppb":
            return dec, "ppb"
        if canonical_unit == "ppm":
            return dec * Decimal("1000"), "ppb"
        if canonical_unit in {"ug/m3", "mg/m3"}:
            return None, f"mass_unit_{canonical_unit}_ineligible_without_ambient_tp_for_ppb"
        return None, f"unsupported_unit_{canonical_unit}_requires_ppb_or_ppm"

    return None, "unsupported_pollutant"


def _truncate_epa_decimal(pollutant: str, value_dec: Decimal) -> Decimal:
    """Applies official US EPA ROUND_DOWN concentration truncation aligned with breakpoint precision."""
    step = _EPA_QUANTIZERS[pollutant]
    abs_val = abs(value_dec)
    int_digits = len(str(int(abs_val))) if abs_val >= 1 else 1
    with localcontext() as ctx:
        ctx.prec = max(64, int_digits + 24)
        return value_dec.quantize(step, rounding=ROUND_DOWN)


def _interpolate_equation_1(
    truncated: Decimal,
    breakpoints: List[Tuple[Any, Any, int, int]],
    *,
    allow_extrapolation_above_500: bool,
) -> Optional[int]:
    """
    Applies 40 CFR Part 58 Appendix G Equation 1 with exact Decimal arithmetic
    and standard half-up integer rounding (ROUND_HALF_UP).
    """
    int_digits = len(str(int(abs(truncated)))) if abs(truncated) >= 1 else 1
    with localcontext() as ctx:
        ctx.prec = max(64, int_digits + 24)
        for bp_lo, bp_hi, i_lo, i_hi in breakpoints:
            bp_lo_d = Decimal(str(bp_lo))
            bp_hi_d = Decimal(str(bp_hi))
            if bp_lo_d <= truncated <= bp_hi_d:
                i_lo_d = Decimal(str(i_lo))
                i_hi_d = Decimal(str(i_hi))
                raw_index = ((i_hi_d - i_lo_d) * (truncated - bp_lo_d)) / (bp_hi_d - bp_lo_d) + i_lo_d
                return int(raw_index.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

        # Extrapolate above AQI 500 only when the breakpoint table terminates at I_hi == 500
        bp_lo_last, bp_hi_last, i_lo_last, i_hi_last = breakpoints[-1]
        if allow_extrapolation_above_500 and i_hi_last == 500 and truncated > Decimal(str(bp_hi_last)):
            bp_lo_d = Decimal(str(bp_lo_last))
            bp_hi_d = Decimal(str(bp_hi_last))
            i_lo_d = Decimal(str(i_lo_last))
            i_hi_d = Decimal(str(i_hi_last))
            raw_index = ((i_hi_d - i_lo_d) * (truncated - bp_lo_d)) / (bp_hi_d - bp_lo_d) + i_lo_d
            return int(raw_index.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    return None


def calculate_epa_ozone_subindex(
    conc: Any,
    *,
    unit: Optional[str],
    averaging_period: Optional[str],
    allow_1hr_precautionary_alternative: bool = False,
) -> Optional[int]:
    """
    Computes US EPA Ozone (O3) sub-index under 40 CFR Part 58 Appendix G rules:
    - Requires explicit volumetric unit ('ppm' or 'ppb', truncated to 0.001 ppm).
    - Requires explicit averaging_period ('8h' or '1h'); rejects missing/unknown/instantaneous.
    - 8-hour O3 defines AQI 0-300 only (0.000-0.200 ppm); returns None for > 0.200 ppm.
    - 1-hour O3 defines AQI >= 301 (0.405-0.604 ppm and extrapolation > 0.604 ppm), and defines
      AQI 101-300 (0.125-0.404 ppm) ONLY when `allow_1hr_precautionary_alternative=True`.
    - 1-hour O3 does not define AQI 0-100 (< 0.125 ppm -> None).
    """
    numeric = _extract_finite_concentration(conc)
    if numeric is None or numeric < 0:
        return None

    canonical_unit = _canonicalize_unit(unit)
    canonical_period = _canonicalize_period(averaging_period)
    if canonical_unit not in {"ppm", "ppb"}:
        return None
    if canonical_period not in {"8h", "1h"}:
        return None

    native_dec, _ = _convert_to_epa_native_decimal("o3", numeric, canonical_unit)
    if native_dec is None:
        return None

    truncated = _truncate_epa_decimal("o3", native_dec)

    if canonical_period == "8h":
        return _interpolate_equation_1(
            truncated,
            EPA_O3_8H_BREAKPOINTS,
            allow_extrapolation_above_500=False,
        )

    # canonical_period == "1h"
    if truncated < Decimal("0.125"):
        return None
    if truncated <= Decimal("0.404") and not allow_1hr_precautionary_alternative:
        return None
    return _interpolate_equation_1(
        truncated,
        EPA_O3_1H_BREAKPOINTS,
        allow_extrapolation_above_500=True,
    )


def calculate_epa_subindex(
    pollutant: str,
    conc: Any,
    *,
    unit: Optional[str] = None,
    averaging_period: Optional[str] = None,
    allow_1hr_precautionary_alternative: bool = False,
) -> Optional[int]:
    """
    Calculates an individual US EPA pollutant sub-index using 40 CFR Part 58 Appendix G (May 2024).

    Native default units for scalar calls:
    - pm25, pm10: ug/m3 (24-hr)
    - co: ppm (8-hr)
    - no2: ppb (1-hr)
    - so2 / so2_1h: ppb (1-hr, 0-200 only); so2_24h or averaging_period='24h': ppb (24-hr, 201-500+)
    - o3: MUST provide explicit volumetric unit ('ppm'/'ppb') AND explicit averaging_period ('8h'/'1h');
          metadata-free or instantaneous ozone is rejected cleanly (returns None).
    """
    if not isinstance(pollutant, str):
        return None
    base_pollutant, implied_period = _canonicalize_pollutant(pollutant)
    if base_pollutant is None:
        return None

    effective_period = _canonicalize_period(averaging_period) or implied_period

    if base_pollutant == "o3":
        return calculate_epa_ozone_subindex(
            conc,
            unit=unit,
            averaging_period=effective_period,
            allow_1hr_precautionary_alternative=allow_1hr_precautionary_alternative,
        )

    numeric = _extract_finite_concentration(conc)
    if numeric is None or numeric < 0:
        return None

    # Default native unit applies only when unit metadata is omitted for non-ozone scalar calls.
    default_native_unit = EPA_POLLUTANT_SPECS["so2_1h" if base_pollutant == "so2" else base_pollutant]["unit"]
    canonical_unit = _canonicalize_unit(unit) if unit is not None else default_native_unit
    if canonical_unit is None:
        return None

    native_dec, _ = _convert_to_epa_native_decimal(base_pollutant, numeric, canonical_unit)
    if native_dec is None:
        return None

    truncated = _truncate_epa_decimal(base_pollutant, native_dec)

    if base_pollutant == "pm25":
        return _interpolate_equation_1(truncated, EPA_PM25_BREAKPOINTS, allow_extrapolation_above_500=True)
    if base_pollutant == "pm10":
        return _interpolate_equation_1(truncated, EPA_PM10_BREAKPOINTS, allow_extrapolation_above_500=True)
    if base_pollutant == "co":
        if effective_period is not None and effective_period not in {"8h"}:
            return None
        return _interpolate_equation_1(truncated, EPA_CO_BREAKPOINTS, allow_extrapolation_above_500=True)
    if base_pollutant == "no2":
        if effective_period is not None and effective_period not in {"1h"}:
            return None
        return _interpolate_equation_1(truncated, EPA_NO2_BREAKPOINTS, allow_extrapolation_above_500=True)
    if base_pollutant == "so2":
        if effective_period == "24h":
            return _interpolate_equation_1(truncated, EPA_SO2_24H_BREAKPOINTS, allow_extrapolation_above_500=True)
        if effective_period in {None, "1h"}:
            return _interpolate_equation_1(truncated, EPA_SO2_1H_BREAKPOINTS, allow_extrapolation_above_500=False)
        return None

    return None


def _extract_measurement_fields(raw_item: Any) -> Dict[str, Any]:
    """Extracts normalized metadata from a scalar, dict, or NormalizedMeasurement-like object."""
    if hasattr(raw_item, "model_dump") or hasattr(raw_item, "unit"):
        val = getattr(raw_item, "value", None)
        orig_val = getattr(raw_item, "original_value", None)
        unit = getattr(raw_item, "unit", None)
        orig_unit = getattr(raw_item, "original_unit", None)
        data_origin = getattr(raw_item, "data_origin", None)
        meas_type = getattr(raw_item, "measurement_type", None)
        period = getattr(raw_item, "averaging_period", None)
        subindex = getattr(raw_item, "provider_aqi_subindex", None)
        source = getattr(raw_item, "source", None)

        # OpenAQ preserves valid measured ppm/ppb gases with value=None and original_value=<conc>
        if val is None and data_origin == "measured" and _canonicalize_unit(unit) in {"ppm", "ppb"}:
            val = orig_val
        return {
            "has_rich_metadata": True,
            "value": val,
            "original_value": orig_val,
            "unit": unit,
            "original_unit": orig_unit,
            "data_origin": data_origin,
            "measurement_type": meas_type,
            "averaging_period": period,
            "provider_aqi_subindex": subindex,
            "source": source,
        }

    if isinstance(raw_item, dict):
        return {
            "has_rich_metadata": True,
            "value": raw_item.get("value"),
            "original_value": raw_item.get("original_value", raw_item.get("value")),
            "unit": raw_item.get("unit"),
            "original_unit": raw_item.get("original_unit", raw_item.get("unit")),
            "data_origin": raw_item.get("data_origin"),
            "measurement_type": raw_item.get("measurement_type"),
            "averaging_period": raw_item.get("averaging_period"),
            "provider_aqi_subindex": raw_item.get("provider_aqi_subindex"),
            "source": raw_item.get("source"),
        }

    return {
        "has_rich_metadata": False,
        "value": raw_item,
        "original_value": raw_item,
        "unit": None,
        "original_unit": None,
        "data_origin": None,
        "measurement_type": None,
        "averaging_period": None,
        "provider_aqi_subindex": None,
        "source": None,
    }


def classify_epa_measurement_eligibility(
    pollutant: str,
    raw_item: Any,
    *,
    allow_1hr_precautionary_alternative: bool = False,
) -> Dict[str, Any]:
    """
    Classifies a pollutant input under 40 CFR Part 58 Appendix G provenance categories:
    - regulatory_eligible
    - model_derived_provisional
    - provider_index
    - unavailable_or_insufficient
    """
    base_pollutant, implied_period = _canonicalize_pollutant(pollutant)
    fields = _extract_measurement_fields(raw_item)
    data_origin = fields["data_origin"]
    unit = _canonicalize_unit(fields["unit"])
    period = _canonicalize_period(fields["averaging_period"]) or implied_period

    if data_origin == "provider_index" or unit in {"aqi_subindex", "waqi_iaqi_subindex"}:
        return {
            "pollutant": base_pollutant or pollutant,
            "classification": "provider_index",
            "eligible_for_regulatory": False,
            "eligible_for_provisional": False,
            "native_unit": None,
            "averaging_period": period,
            "provider_aqi_subindex": fields["provider_aqi_subindex"],
            "reason": "provider_reported_subindex_excluded_from_concentration_equations",
        }

    numeric = _extract_finite_concentration(fields["value"])
    if numeric is None:
        return {
            "pollutant": base_pollutant or pollutant,
            "classification": "unavailable_or_insufficient",
            "eligible_for_regulatory": False,
            "eligible_for_provisional": False,
            "native_unit": None,
            "averaging_period": period,
            "reason": "missing_or_non_finite_value",
        }

    if base_pollutant is None:
        return {
            "pollutant": pollutant,
            "classification": "unavailable_or_insufficient",
            "eligible_for_regulatory": False,
            "eligible_for_provisional": False,
            "native_unit": None,
            "averaging_period": period,
            "reason": "unsupported_pollutant",
        }

    # For unattributed scalar inputs (e.g. /api/v1/aqi/calculate raw payload), clamp negative
    # calibration noise cleanly for non-ozone, but still classify origin as unverified.
    clean_val = max(0.0, numeric) if not fields["has_rich_metadata"] else numeric
    if clean_val < 0:
        return {
            "pollutant": base_pollutant,
            "classification": "unavailable_or_insufficient",
            "eligible_for_regulatory": False,
            "eligible_for_provisional": False,
            "native_unit": None,
            "averaging_period": period,
            "reason": "negative_concentration",
        }

    # Model-derived estimates never count as regulatory monitor observations.
    if data_origin == "model_derived":
        if unit is None:
            return {
                "pollutant": base_pollutant,
                "classification": "unavailable_or_insufficient",
                "eligible_for_regulatory": False,
                "eligible_for_provisional": False,
                "native_unit": None,
                "averaging_period": period,
                "reason": "missing_unit_metadata",
            }
        native_dec, conv_err = _convert_to_epa_native_decimal(base_pollutant, clean_val, unit)
        can_estimate = base_pollutant in {"pm25", "pm10"} and native_dec is not None
        return {
            "pollutant": base_pollutant,
            "classification": "model_derived_provisional",
            "eligible_for_regulatory": False,
            "eligible_for_provisional": can_estimate,
            "native_value": float(native_dec) if native_dec is not None else None,
            "native_unit": conv_err if native_dec is not None else None,
            "averaging_period": period,
            "reason": "model_derived_particulate_provisional_estimate" if can_estimate else (conv_err or "model_derived_gas_ineligible"),
        }

    # Ozone requires explicit volumetric unit AND explicit averaging period (never inferred).
    if base_pollutant == "o3":
        if unit is None or unit not in {"ppm", "ppb"}:
            reason = (
                "mass_unit_ineligible_without_ambient_tp_for_ppm"
                if unit in {"ug/m3", "mg/m3"}
                else "missing_or_unsupported_ozone_unit_requires_ppm_or_ppb"
            )
            return {
                "pollutant": "o3",
                "classification": "unavailable_or_insufficient",
                "eligible_for_regulatory": False,
                "eligible_for_provisional": False,
                "native_unit": None,
                "averaging_period": period,
                "reason": reason,
            }
        if period not in {"8h", "1h"}:
            return {
                "pollutant": "o3",
                "classification": "unavailable_or_insufficient",
                "eligible_for_regulatory": False,
                "eligible_for_provisional": False,
                "native_unit": "ppm",
                "averaging_period": period,
                "reason": "instantaneous_or_unspecified_ozone_averaging_period_rejected",
            }
        sub = calculate_epa_ozone_subindex(
            clean_val,
            unit=unit,
            averaging_period=period,
            allow_1hr_precautionary_alternative=allow_1hr_precautionary_alternative,
        )
        if sub is None:
            return {
                "pollutant": "o3",
                "classification": "unavailable_or_insufficient",
                "eligible_for_regulatory": False,
                "eligible_for_provisional": False,
                "native_unit": "ppm",
                "averaging_period": period,
                "reason": f"outside_applicable_{period}_o3_aqi_range_or_policy",
            }
        is_measured = data_origin == "measured"
        return {
            "pollutant": "o3",
            "classification": "regulatory_eligible" if is_measured else "unavailable_or_insufficient",
            "eligible_for_regulatory": is_measured,
            "eligible_for_formula_without_origin": not fields["has_rich_metadata"] or data_origin is None,
            "eligible_for_provisional": False,
            "native_unit": "ppm",
            "averaging_period": period,
            "subindex": sub,
            "reason": "measured_native_o3_eligible" if is_measured else "formula_input_without_verified_monitor_origin",
        }

    # Non-ozone pollutants
    effective_unit = unit
    if effective_unit is None:
        if fields["has_rich_metadata"]:
            return {
                "pollutant": base_pollutant,
                "classification": "unavailable_or_insufficient",
                "eligible_for_regulatory": False,
                "eligible_for_provisional": False,
                "native_unit": None,
                "averaging_period": period,
                "reason": "missing_unit_metadata",
            }
        effective_unit = EPA_POLLUTANT_SPECS["so2_1h" if base_pollutant == "so2" else base_pollutant]["unit"]

    native_dec, conv_err = _convert_to_epa_native_decimal(base_pollutant, clean_val, effective_unit)
    if native_dec is None:
        return {
            "pollutant": base_pollutant,
            "classification": "unavailable_or_insufficient",
            "eligible_for_regulatory": False,
            "eligible_for_provisional": False,
            "native_unit": None,
            "averaging_period": period,
            "reason": conv_err,
        }

    required_periods = {
        "pm25": {"24h", "nowcast"},
        "pm10": {"24h"},
        "co": {"8h"},
        "no2": {"1h"},
        "so2": {"1h", "24h"},
    }[base_pollutant]

    if fields["has_rich_metadata"]:
        if period not in required_periods:
            return {
                "pollutant": base_pollutant,
                "classification": "unavailable_or_insufficient",
                "eligible_for_regulatory": False,
                "eligible_for_provisional": False,
                "native_unit": conv_err,
                "averaging_period": period,
                "reason": "missing_or_ineligible_averaging_period",
            }
        if data_origin != "measured":
            return {
                "pollutant": base_pollutant,
                "classification": "unavailable_or_insufficient",
                "eligible_for_regulatory": False,
                "eligible_for_provisional": False,
                "native_unit": conv_err,
                "averaging_period": period,
                "reason": "unverified_or_non_measured_data_origin",
            }

    sub = calculate_epa_subindex(
        base_pollutant,
        clean_val,
        unit=effective_unit,
        averaging_period=period,
        allow_1hr_precautionary_alternative=allow_1hr_precautionary_alternative,
    )
    if sub is None:
        return {
            "pollutant": base_pollutant,
            "classification": "unavailable_or_insufficient",
            "eligible_for_regulatory": False,
            "eligible_for_provisional": False,
            "native_unit": conv_err,
            "averaging_period": period,
            "reason": "outside_applicable_breakpoint_range",
        }

    if fields["has_rich_metadata"]:
        return {
            "pollutant": base_pollutant,
            "classification": "regulatory_eligible",
            "eligible_for_regulatory": True,
            "eligible_for_provisional": False,
            "native_unit": conv_err,
            "averaging_period": period,
            "subindex": sub,
            "reason": "measured_native_concentration_eligible",
        }

    return {
        "pollutant": base_pollutant,
        "classification": "unavailable_or_insufficient",
        "eligible_for_regulatory": False,
        "eligible_for_formula_without_origin": True,
        "eligible_for_provisional": False,
        "native_unit": conv_err,
        "averaging_period": period,
        "subindex": sub,
        "reason": "scalar_formula_input_without_origin_or_averaging_metadata",
    }


def _select_ozone_subindex(
    o3_8h_sub: Optional[int],
    o3_1h_full_sub: Optional[int],
    *,
    allow_1hr_precautionary_alternative: bool,
) -> Tuple[Optional[int], Optional[str]]:
    """
    Applies 40 CFR Part 58 Appendix G Footnotes 1 & 2 to select the EPA Ozone sub-index:
    1. AQI >= 301 must use 1-hour O3 regardless of precautionary policy.
    2. Otherwise 8-hour O3 is standard for AQI 0-300.
    3. 1-hour O3 in AQI 101-300 is selected only if `allow_1hr_precautionary_alternative=True`.
    """
    if o3_1h_full_sub is not None and o3_1h_full_sub >= 301:
        return o3_1h_full_sub, "o3_1h_mandatory_above_300"

    if o3_8h_sub is not None:
        if allow_1hr_precautionary_alternative and o3_1h_full_sub is not None and o3_1h_full_sub > o3_8h_sub:
            return o3_1h_full_sub, "o3_1h_precautionary_alternative"
        return o3_8h_sub, "o3_8h_standard"

    if allow_1hr_precautionary_alternative and o3_1h_full_sub is not None:
        return o3_1h_full_sub, "o3_1h_precautionary_alternative"

    return None, None


def calculate_us_epa_aqi(
    measurements: Dict[str, Any],
    *,
    measurement_metadata: Optional[Dict[str, Any]] = None,
    model_derived_aggregates: Optional[Dict[str, Any]] = None,
    allow_1hr_precautionary_alternative: bool = False,
    include_provisional_model_estimates: bool = True,
) -> Dict[str, Any]:
    """
    Computes US EPA AQI using 40 CFR Part 58 Appendix G (May 2024) breakpoints and rules.

    Accepts either:
    - Raw scalar dicts (`{"pm25": 9.0, ...}`) for `/api/v1/aqi/calculate` compatibility
      (rejects metadata-free ozone cleanly), OR
    - `measurement_metadata` mapping keys to `NormalizedMeasurement` objects / metadata dicts
      for full eligibility & provenance separation.
    """
    subindices: Dict[str, int] = {}
    regulatory_subindices: Dict[str, int] = {}
    provisional_subindices: Dict[str, int] = {}
    pollutant_provenance: Dict[str, Dict[str, Any]] = {}

    o3_8h_candidates: List[Tuple[int, bool, bool]] = []
    o3_1h_candidates: List[Tuple[int, bool, bool]] = []

    source_items = measurement_metadata if isinstance(measurement_metadata, dict) else measurements

    if isinstance(source_items, dict):
        for raw_key, raw_item in source_items.items():
            base_pollutant, implied_period = _canonicalize_pollutant(str(raw_key))
            fields = _extract_measurement_fields(raw_item)

            if base_pollutant == "o3":
                unit = _canonicalize_unit(fields["unit"])
                period = _canonicalize_period(fields["averaging_period"]) or implied_period
                data_origin = fields["data_origin"]

                if data_origin == "provider_index" or unit in {"aqi_subindex", "waqi_iaqi_subindex"}:
                    pollutant_provenance[str(raw_key).lower()] = {
                        "pollutant": "o3",
                        "classification": "provider_index",
                        "eligible_for_regulatory": False,
                        "provider_aqi_subindex": fields["provider_aqi_subindex"],
                        "reason": "provider_reported_subindex_excluded_from_concentration_equations",
                    }
                    continue

                if data_origin == "model_derived":
                    pollutant_provenance[str(raw_key).lower()] = {
                        "pollutant": "o3",
                        "classification": "model_derived_provisional",
                        "eligible_for_regulatory": False,
                        "unit": unit,
                        "averaging_period": period,
                        "reason": "model_derived_ozone_ineligible_for_regulatory_epa_calculation",
                    }
                    continue

                info = classify_epa_measurement_eligibility(
                    str(raw_key),
                    raw_item,
                    allow_1hr_precautionary_alternative=True,  # evaluate 1h range; enforce policy in _select_ozone_subindex
                )
                pollutant_provenance[str(raw_key).lower()] = info

                sub_candidate = info.get("subindex")
                if sub_candidate is not None:
                    is_reg = bool(info.get("eligible_for_regulatory"))
                    is_formula = is_reg or bool(info.get("eligible_for_formula_without_origin"))
                    if period == "8h":
                        o3_8h_candidates.append((sub_candidate, is_reg, is_formula))
                    elif period == "1h":
                        o3_1h_candidates.append((sub_candidate, is_reg, is_formula))
                continue

            info = classify_epa_measurement_eligibility(
                str(raw_key),
                raw_item,
                allow_1hr_precautionary_alternative=allow_1hr_precautionary_alternative,
            )
            prov_key = str(raw_key).lower()
            pollutant_provenance[prov_key] = info

            if base_pollutant is None:
                continue

            if info["classification"] == "regulatory_eligible" and info.get("subindex") is not None:
                regulatory_subindices[base_pollutant] = max(
                    regulatory_subindices.get(base_pollutant, -1),
                    int(info["subindex"]),
                )
            elif info.get("eligible_for_formula_without_origin") and info.get("subindex") is not None:
                subindices[base_pollutant] = max(subindices.get(base_pollutant, -1), int(info["subindex"]))
            elif info["classification"] == "model_derived_provisional" and info.get("eligible_for_provisional"):
                if include_provisional_model_estimates:
                    prov_sub = calculate_epa_subindex(base_pollutant, info.get("native_value"), unit="ug/m3")
                    if prov_sub is not None:
                        info["provisional_subindex"] = prov_sub
                        provisional_subindices[base_pollutant] = max(
                            provisional_subindices.get(base_pollutant, -1),
                            prov_sub,
                        )

    # Resolve Ozone 8h vs 1h per 40 CFR Part 58 Appendix G Footnotes 1 & 2
    reg_8h = max((s for s, reg, _ in o3_8h_candidates if reg), default=None)
    reg_1h = max((s for s, reg, _ in o3_1h_candidates if reg), default=None)
    selected_reg_o3, reg_o3_basis = _select_ozone_subindex(
        reg_8h,
        reg_1h,
        allow_1hr_precautionary_alternative=allow_1hr_precautionary_alternative,
    )
    if selected_reg_o3 is not None:
        regulatory_subindices["o3"] = selected_reg_o3
    elif o3_1h_candidates and not allow_1hr_precautionary_alternative:
        for k, pinfo in pollutant_provenance.items():
            if pinfo.get("pollutant") == "o3" and pinfo.get("averaging_period") == "1h" and pinfo.get("subindex") is not None:
                pinfo["eligible_for_regulatory"] = False
                pinfo["eligible_for_formula_without_origin"] = False
                pinfo["classification"] = "unavailable_or_insufficient"
                pinfo["reason"] = "1h_o3_101_to_300_requires_explicit_precautionary_policy"

    form_8h = max((s for s, _, ok in o3_8h_candidates if ok), default=None)
    form_1h = max((s for s, _, ok in o3_1h_candidates if ok), default=None)
    selected_form_o3, form_o3_basis = _select_ozone_subindex(
        form_8h,
        form_1h,
        allow_1hr_precautionary_alternative=allow_1hr_precautionary_alternative,
    )
    if selected_reg_o3 is not None:
        subindices["o3"] = selected_reg_o3
    elif selected_form_o3 is not None and not any(reg for _, reg, _ in o3_8h_candidates + o3_1h_candidates):
        subindices["o3"] = selected_form_o3

    # Combine verified regulatory subindices, unverified formula inputs, and optional provisional estimates
    for p, val in regulatory_subindices.items():
        subindices[p] = max(subindices.get(p, -1), val)
    for p, val in provisional_subindices.items():
        if p not in subindices:
            subindices[p] = val

    # Preserve D.3.4.2a model-derived 8-hour O3 aggregate strictly as provisional metadata (never converted to ppm)
    provisional_estimates: Dict[str, Any] = {}
    if isinstance(model_derived_aggregates, dict) and isinstance(model_derived_aggregates.get("o3_8h"), dict):
        o3_8h_agg = model_derived_aggregates["o3_8h"]
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
            "classification": "model_derived_provisional",
            "epa_subindex": None,
            "note": "Preserved in native ug/m3 as a model-derived provisional estimate; not converted to ppm via arbitrary STP constants.",
        }

    if regulatory_subindices:
        calculation_basis = "regulatory_eligible"
    elif provisional_subindices and not any(
        info.get("eligible_for_formula_without_origin") for info in pollutant_provenance.values()
    ):
        calculation_basis = "model_derived_provisional"
    elif subindices:
        calculation_basis = "formula_input_unverified_origin"
    else:
        calculation_basis = "unavailable"

    if not subindices:
        return {
            "standard": "US_EPA",
            "methodology_version": EPA_METHODOLOGY_VERSION,
            "aqi": None,
            "category": "Unavailable",
            "dominant_pollutant": None,
            "color": "#64748b",
            "subindices": {},
            "advisory": "Insufficient eligible pollutant measurements to calculate US EPA AQI.",
            "is_reliable": False,
            "is_regulatory_compliant": False,
            "calculation_basis": calculation_basis,
            "pollutant_provenance": pollutant_provenance,
            "provisional_estimates": provisional_estimates or None,
            "compliance_disclaimer": EPA_COMPLIANCE_DISCLAIMER,
        }

    dominant_pollutant = max(subindices, key=subindices.get)
    overall_aqi = subindices[dominant_pollutant]
    category, color, advisory = get_epa_category(overall_aqi)
    if calculation_basis == "model_derived_provisional":
        advisory = f"Provisional model-derived estimate (not a regulatory monitor observation): {advisory}"

    return {
        "standard": "US_EPA",
        "methodology_version": EPA_METHODOLOGY_VERSION,
        "aqi": overall_aqi,
        "category": category,
        "dominant_pollutant": dominant_pollutant.upper(),
        "color": color,
        "subindices": subindices,
        "advisory": advisory,
        "is_reliable": True,
        "is_regulatory_compliant": False,
        "calculation_basis": calculation_basis,
        "ozone_selection_basis": reg_o3_basis or form_o3_basis,
        "pollutant_provenance": pollutant_provenance,
        "provisional_estimates": provisional_estimates or None,
        "compliance_disclaimer": EPA_COMPLIANCE_DISCLAIMER,
    }
