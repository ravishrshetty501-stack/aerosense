from typing import Dict, Optional, Tuple

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

def get_eaqi_band(pollutant: str, conc: float) -> Optional[int]:
    pollutant = pollutant.lower().replace(".", "").replace("-", "")
    thresholds = EAQI_THRESHOLDS.get(pollutant)
    if not thresholds or conc < 0:
        return None
        
    if conc <= thresholds[1]:
        return 1
    elif conc <= thresholds[2]:
        return 2
    elif conc <= thresholds[3]:
        return 3
    elif conc <= thresholds[4]:
        return 4
    elif conc <= thresholds[5]:
        return 5
    else:
        return 6

def calculate_european_aqi(measurements: Dict[str, float]) -> Dict:
    """
    Calculates EAQI band (1 to 6) and maps to scaled score (0 to 100).
    Dominant pollutant is the one with highest band level.
    """
    subindices = {}
    for p, val in measurements.items():
        if val is not None and val >= 0:
            band = get_eaqi_band(p, val)
            if band is not None:
                subindices[p.lower()] = band
                
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
