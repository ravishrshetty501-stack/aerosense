import math
from typing import Any, Dict, Optional, Tuple

"""
European Air Quality Index (EAQI)
Reference: European Environment Agency (EEA) Air Quality Index methodology
Bands:
1: Good
2: Fair
3: Moderate
4: Poor
5: Very Poor
6: Extremely Poor
"""

EAQI_THRESHOLDS = {
    "pm25": [0, 10, 20, 25, 50, 75],    # ug/m3
    "pm10": [0, 20, 40, 50, 100, 150],  # ug/m3
    "no2":  [0, 40, 90, 120, 230, 340], # ug/m3
    "o3":   [0, 50, 100, 130, 240, 380],# ug/m3
    "so2":  [0, 100, 200, 350, 500, 750] # ug/m3
}

CATEGORY_MAP = {
    1: ("Good", "#10b981", "Air quality is good. Enjoy usual outdoor activities."),
    2: ("Fair", "#22c55e", "Air quality is fair. Standard outdoor activities are safe."),
    3: ("Moderate", "#f59e0b", "Air quality is moderate. Sensitive individuals should observe symptoms."),
    4: ("Poor", "#f97316", "Air quality is poor. Sensitive individuals should reduce intense outdoor activities."),
    5: ("Very Poor", "#ef4444", "Air quality is very poor. Anyone experiencing discomfort should consider reducing outdoor exertion."),
    6: ("Extremely Poor", "#7f1d1d", "Air quality is extremely poor. Reduce outdoor physical activity for everyone.")
}


def _extract_finite_nonneg(raw: Any) -> Optional[float]:
    """Extracts a finite non-negative float (rejecting None, bool, strings, NaN, +/-inf, negative)."""
    if raw is None or isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    try:
        numeric = float(raw)
    except (OverflowError, ValueError, TypeError):
        return None
    if not math.isfinite(numeric) or numeric < 0.0:
        return None
    return 0.0 if numeric == 0.0 else numeric


def get_eaqi_band(pollutant: str, conc: Any) -> Optional[int]:
    if not isinstance(pollutant, str):
        return None
    norm_pollutant = pollutant.lower().replace(".", "").replace("-", "")
    thresholds = EAQI_THRESHOLDS.get(norm_pollutant)
    numeric = _extract_finite_nonneg(conc)
    if not thresholds or numeric is None:
        return None

    if numeric <= thresholds[1]:
        return 1
    elif numeric <= thresholds[2]:
        return 2
    elif numeric <= thresholds[3]:
        return 3
    elif numeric <= thresholds[4]:
        return 4
    elif numeric <= thresholds[5]:
        return 5
    else:
        return 6


def _extract_eaqi_concentration(raw_item: Any) -> Optional[float]:
    """Extracts usable ug/m3 / mg/m3 concentration for EAQI while excluding provider_index and volumetric gaps."""
    if hasattr(raw_item, "model_dump") or hasattr(raw_item, "unit"):
        data_origin = getattr(raw_item, "data_origin", None)
        unit = str(getattr(raw_item, "unit", "") or "").strip().lower()
        val = getattr(raw_item, "value", None)
    elif isinstance(raw_item, dict):
        data_origin = raw_item.get("data_origin")
        unit = str(raw_item.get("unit", "") or "").strip().lower()
        val = raw_item.get("value")
    else:
        return _extract_finite_nonneg(raw_item)

    if data_origin == "provider_index" or unit in {"aqi_subindex", "waqi_iaqi_subindex", "ppm", "ppb", "unavailable"}:
        return None
    numeric = _extract_finite_nonneg(val)
    if numeric is None:
        return None
    if unit in {"mg/m3", "mg/m³", "mg/m^3"}:
        return numeric * 1000.0
    if unit in {"", "ug/m3", "µg/m³", "μg/m³", "ug/m^3"}:
        return numeric
    return None


def calculate_european_aqi(
    measurements: Dict[str, Any],
    *,
    measurement_metadata: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    Calculates EAQI band (1 to 6) and maps to scaled score (0 to 100).
    Dominant pollutant is the one with highest band level.
    """
    source_items = measurement_metadata if isinstance(measurement_metadata, dict) else measurements
    subindices = {}
    if isinstance(source_items, dict):
        for p, raw_val in source_items.items():
            conc = _extract_eaqi_concentration(raw_val)
            if conc is not None:
                band = get_eaqi_band(str(p), conc)
                if band is not None:
                    norm_key = str(p).lower().replace(".", "").replace("-", "")
                    subindices[norm_key] = max(subindices.get(norm_key, -1), band)
                
    if not subindices:
        return {
            "standard": "EUROPEAN_AQI",
            "aqi": None,
            "category": "Unavailable",
            "dominant_pollutant": None,
            "color": "#64748b",
            "subindices": {},
            "advisory": "No compatible pollutant measurements for European AQI.",
            "is_reliable": False
        }
        
    dominant_pollutant = max(subindices, key=subindices.get)
    max_band = subindices[dominant_pollutant]
    category, color, advisory = CATEGORY_MAP[max_band]
    
    # Linear scale 1-6 into standard 0-100 representation for consistent visual gauges
    scaled_score = round(((max_band - 1) / 5) * 100)
    
    return {
        "standard": "EUROPEAN_AQI",
        "aqi": scaled_score,
        "band": max_band,
        "category": category,
        "dominant_pollutant": dominant_pollutant.upper(),
        "color": color,
        "subindices": subindices,
        "advisory": advisory,
        "is_reliable": True
    }
