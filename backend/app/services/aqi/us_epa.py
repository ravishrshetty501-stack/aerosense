from typing import Dict, Optional, Tuple

"""
US EPA Air Quality Index (AQI) Calculation Methodology
Reference: Technical Assistance Document for the Reporting of Daily Air Quality – the Air Quality Index (AQI)
EPA 454/B-18-007
"""

# Breakpoints table: [(Cp_low, Cp_high, I_low, I_high)]
EPA_BREAKPOINTS = {
    "pm25": [  # ug/m3, 24-hr avg (truncated to 0.1)
        (0.0, 12.0, 0, 50),
        (12.1, 35.4, 51, 100),
        (35.5, 55.4, 101, 150),
        (55.5, 150.4, 151, 200),
        (150.5, 250.4, 201, 300),
        (250.5, 350.4, 301, 400),
        (350.5, 500.4, 401, 500),
    ],
    "pm10": [  # ug/m3, 24-hr avg (truncated to integer)
        (0, 54, 0, 50),
        (55, 154, 51, 100),
        (155, 254, 101, 150),
        (255, 354, 151, 200),
        (355, 424, 201, 300),
        (425, 504, 301, 400),
        (505, 604, 401, 500),
    ],
    "o3": [  # ug/m3 converted to ppm or directly in ug/m3 (approx 1 ppm = 1960 ug/m3)
        # Using ug/m3 equivalent for 8-hr:
        (0.0, 108.0, 0, 50),
        (109.0, 140.0, 51, 100),
        (141.0, 170.0, 101, 150),
        (171.0, 210.0, 151, 200),
        (211.0, 400.0, 201, 300),
        (401.0, 800.0, 301, 500),
    ],
    "no2": [  # ug/m3, 1-hr avg
        (0.0, 100.0, 0, 50),
        (101.0, 190.0, 51, 100),
        (191.0, 675.0, 101, 150),
        (676.0, 1220.0, 151, 200),
        (1221.0, 2350.0, 201, 300),
        (2351.0, 3850.0, 301, 500),
    ],
    "so2": [  # ug/m3, 1-hr avg
        (0.0, 92.0, 0, 50),
        (93.0, 197.0, 51, 100),
        (198.0, 485.0, 101, 150),
        (486.0, 797.0, 151, 200),
        (798.0, 1583.0, 201, 300),
        (1584.0, 2630.0, 301, 500),
    ],
    "co": [  # mg/m3, 8-hr avg
        (0.0, 5.0, 0, 50),
        (5.1, 10.8, 51, 100),
        (10.9, 14.2, 101, 150),
        (14.3, 17.6, 151, 200),
        (17.7, 34.8, 201, 300),
        (34.9, 57.5, 301, 500),
    ],
}

def get_epa_category(aqi: int) -> Tuple[str, str, str]:
    """Returns (category_name, hex_color, health_advisory)"""
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
    else:
        return "Hazardous", "#7f1d1d", "Health warning of emergency conditions: everyone is more likely to be affected."

def calculate_epa_subindex(pollutant: str, conc: float) -> Optional[int]:
    pollutant = pollutant.lower().replace(".", "").replace("-", "")
    breakpoints = EPA_BREAKPOINTS.get(pollutant)
    if not breakpoints or conc < 0:
        return None
    
    # Linear interpolation formula: Ip = ((Ihi - Ilo)/(BPhi - BPlo)) * (Cp - BPlo) + Ilo
    for bp_lo, bp_hi, i_lo, i_hi in breakpoints:
        if bp_lo <= conc <= bp_hi:
            index = ((i_hi - i_lo) / (bp_hi - bp_lo)) * (conc - bp_lo) + i_lo
            return round(index)
    
    # If beyond max breakpoint, extrapolate or cap at 500
    if conc > breakpoints[-1][1]:
        return 500
    return 0

def calculate_us_epa_aqi(measurements: Dict[str, float]) -> Dict:
    """
    Computes US EPA AQI based on available pollutant concentrations.
    measurements dict key: 'pm25', 'pm10', 'no2', 'so2', 'co', 'o3'
    """
    subindices = {}
    for p, val in measurements.items():
        if val is not None and val >= 0:
            sub = calculate_epa_subindex(p, val)
            if sub is not None:
                subindices[p.lower()] = sub
                
    if not subindices:
        return {
            "standard": "US_EPA",
            "aqi": None,
            "category": "Unavailable",
            "dominant_pollutant": None,
            "color": "#64748b",
            "subindices": {},
            "advisory": "Insufficient pollutant measurements to calculate official US EPA AQI.",
            "is_reliable": False
        }
        
    dominant_pollutant = max(subindices, key=subindices.get)
    overall_aqi = subindices[dominant_pollutant]
    category, color, advisory = get_epa_category(overall_aqi)
    
    return {
        "standard": "US_EPA",
        "aqi": overall_aqi,
        "category": category,
        "dominant_pollutant": dominant_pollutant.upper(),
        "color": color,
        "subindices": subindices,
        "advisory": advisory,
        "is_reliable": True
    }
