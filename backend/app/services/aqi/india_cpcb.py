from typing import Dict, Optional, Tuple

"""
India Central Pollution Control Board (CPCB) National Air Quality Index (NAQI)
Reference: National Air Quality Index (NAQI) Report, CPCB Ministry of Environment, Forest and Climate Change, 2014.
Rule: AQI can only be calculated if at least 3 pollutants are monitored, one of which MUST be PM2.5 or PM10.
"""

CPCB_BREAKPOINTS = {
    "pm25": [  # ug/m3, 24-hr avg
        (0, 30, 0, 50),
        (31, 60, 51, 100),
        (61, 90, 101, 200),
        (91, 120, 201, 300),
        (121, 250, 301, 400),
        (251, 350, 401, 500),
    ],
    "pm10": [  # ug/m3, 24-hr avg
        (0, 50, 0, 50),
        (51, 100, 51, 100),
        (101, 250, 101, 200),
        (251, 350, 201, 300),
        (351, 430, 301, 400),
        (431, 500, 401, 500),
    ],
    "no2": [  # ug/m3, 24-hr avg
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 180, 101, 200),
        (181, 280, 201, 300),
        (281, 400, 301, 400),
        (401, 500, 401, 500),
    ],
    "so2": [  # ug/m3, 24-hr avg
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 380, 101, 200),
        (381, 800, 201, 300),
        (801, 1600, 301, 400),
        (1601, 2000, 401, 500),
    ],
    "co": [  # mg/m3, 8-hr avg
        (0, 1.0, 0, 50),
        (1.1, 2.0, 51, 100),
        (2.1, 10.0, 101, 200),
        (10.1, 17.0, 201, 300),
        (17.1, 34.0, 301, 400),
        (34.1, 50.0, 401, 500),
    ],
    "o3": [  # ug/m3, 8-hr avg
        (0, 50, 0, 50),
        (51, 100, 51, 100),
        (101, 168, 101, 200),
        (169, 208, 201, 300),
        (209, 748, 301, 400),
        (749, 1000, 401, 500),
    ],
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

def calculate_cpcb_subindex(pollutant: str, conc: float) -> Optional[int]:
    pollutant = pollutant.lower().replace(".", "").replace("-", "")
    breakpoints = CPCB_BREAKPOINTS.get(pollutant)
    if not breakpoints or conc < 0:
        return None
        
    for bp_lo, bp_hi, i_lo, i_hi in breakpoints:
        if bp_lo <= conc <= bp_hi:
            index = ((i_hi - i_lo) / (bp_hi - bp_lo)) * (conc - bp_lo) + i_lo
            return round(index)
            
    if conc > breakpoints[-1][1]:
        return 500
    return 0

def calculate_india_cpcb_aqi(measurements: Dict[str, float]) -> Dict:
    """
    Computes India CPCB NAQI.
    Enforces CPCB requirement: Minimum 3 pollutants with at least one particulate matter (PM2.5 or PM10).
    """
    subindices = {}
    for p, val in measurements.items():
        if val is not None and val >= 0:
            sub = calculate_cpcb_subindex(p, val)
            if sub is not None:
                subindices[p.lower()] = sub
                
    has_pm = "pm25" in subindices or "pm10" in subindices
    has_min_three = len(subindices) >= 3
    
    if not subindices or not has_pm:
        return {
            "standard": "INDIA_CPCB",
            "aqi": None,
            "category": "Unavailable",
            "dominant_pollutant": None,
            "color": "#64748b",
            "subindices": subindices,
            "advisory": "CPCB NAQI requires at least one particulate matter (PM2.5 or PM10). Data insufficient.",
            "is_reliable": False
        }
        
    dominant_pollutant = max(subindices, key=subindices.get)
    overall_aqi = subindices[dominant_pollutant]
    category, color, advisory = get_cpcb_category(overall_aqi)
    
    # If fewer than 3 pollutants, label as provisional estimate
    is_reliable = has_min_three and has_pm
    if not has_min_three:
        advisory += " (Provisional: CPCB guidelines officially require 3+ monitored parameters)."
        
    return {
        "standard": "INDIA_CPCB",
        "aqi": overall_aqi,
        "category": category,
        "dominant_pollutant": dominant_pollutant.upper(),
        "color": color,
        "subindices": subindices,
        "advisory": advisory,
        "is_reliable": is_reliable
    }
