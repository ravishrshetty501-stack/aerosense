from typing import Dict, Optional
from app.services.aqi.us_epa import calculate_us_epa_aqi
from app.services.aqi.india_cpcb import calculate_india_cpcb_aqi
from app.services.aqi.european_aqi import calculate_european_aqi

class AQIEngine:
    """
    Unified deterministic AQI engine dispatching to US EPA, India CPCB, and European AQI methodologies.
    Strictly preserves raw pollutant units, handles missing data, and identifies dominant pollutant.
    """
    
    @staticmethod
    def calculate(measurements: Dict[str, float], standard: str = "US_EPA") -> Dict:
        norm_std = standard.upper().strip()
        
        if norm_std in ["US_EPA", "US", "EPA"]:
            result = calculate_us_epa_aqi(measurements)
        elif norm_std in ["INDIA_CPCB", "CPCB", "INDIA", "NAQI"]:
            result = calculate_india_cpcb_aqi(measurements)
        elif norm_std in ["EUROPEAN_AQI", "EU", "EAQI", "EUROPE"]:
            result = calculate_european_aqi(measurements)
        else:
            # Default to US EPA with notice
            result = calculate_us_epa_aqi(measurements)
            result["standard_note"] = f"Standard '{standard}' unrecognized, defaulted to US EPA."
            
        return result

    @staticmethod
    def calculate_all_standards(measurements: Dict[str, float]) -> Dict[str, Dict]:
        """Calculates AQI for all 3 standards simultaneously for comparison."""
        return {
            "US_EPA": calculate_us_epa_aqi(measurements),
            "INDIA_CPCB": calculate_india_cpcb_aqi(measurements),
            "EUROPEAN_AQI": calculate_european_aqi(measurements)
        }

aqi_engine = AQIEngine()
