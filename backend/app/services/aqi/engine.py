from typing import Any, Dict, Optional
from app.services.aqi.us_epa import calculate_us_epa_aqi
from app.services.aqi.india_cpcb import calculate_india_cpcb_aqi
from app.services.aqi.european_aqi import calculate_european_aqi

def normalize_standard_name(standard: Optional[str]) -> str:
    """Canonicalizes user/API standard aliases into ['US_EPA', 'INDIA_CPCB', 'EUROPEAN_AQI']."""
    norm_std = str(standard or "").upper().strip()
    if norm_std in {"US_EPA", "US", "EPA"}:
        return "US_EPA"
    if norm_std in {"INDIA_CPCB", "CPCB", "INDIA", "NAQI"}:
        return "INDIA_CPCB"
    if norm_std in {"EUROPEAN_AQI", "EU", "EAQI", "EUROPE"}:
        return "EUROPEAN_AQI"
    return "US_EPA"


class AQIEngine:
    """
    Unified deterministic AQI engine dispatching to US EPA, India CPCB, and European AQI methodologies.
    Strictly preserves raw pollutant units, handles missing data, and identifies dominant pollutant.
    """
    
    @staticmethod
    def calculate(
        measurements: Dict[str, Any],
        standard: str = "US_EPA",
        *,
        measurement_metadata: Optional[Dict[str, Any]] = None,
        model_derived_aggregates: Optional[Dict[str, Any]] = None,
        allow_1hr_precautionary_alternative: bool = False,
    ) -> Dict:
        norm_std = str(standard or "").upper().strip()
        
        if norm_std in ["US_EPA", "US", "EPA"]:
            result = calculate_us_epa_aqi(
                measurements,
                measurement_metadata=measurement_metadata,
                model_derived_aggregates=model_derived_aggregates,
                allow_1hr_precautionary_alternative=allow_1hr_precautionary_alternative,
            )
        elif norm_std in ["INDIA_CPCB", "CPCB", "INDIA", "NAQI"]:
            result = calculate_india_cpcb_aqi(
                measurements,
                measurement_metadata=measurement_metadata,
                model_derived_aggregates=model_derived_aggregates,
            )
        elif norm_std in ["EUROPEAN_AQI", "EU", "EAQI", "EUROPE"]:
            result = calculate_european_aqi(
                measurements,
                measurement_metadata=measurement_metadata,
            )
        else:
            # Default to US EPA with notice
            result = calculate_us_epa_aqi(
                measurements,
                measurement_metadata=measurement_metadata,
                model_derived_aggregates=model_derived_aggregates,
                allow_1hr_precautionary_alternative=allow_1hr_precautionary_alternative,
            )
            result["standard_note"] = f"Standard '{standard}' unrecognized, defaulted to US EPA."
            
        return result

    @staticmethod
    def calculate_all_standards(
        measurements: Dict[str, Any],
        *,
        measurement_metadata: Optional[Dict[str, Any]] = None,
        model_derived_aggregates: Optional[Dict[str, Any]] = None,
        allow_1hr_precautionary_alternative: bool = False,
    ) -> Dict[str, Dict]:
        """Calculates AQI for all 3 standards simultaneously for comparison."""
        return {
            "US_EPA": calculate_us_epa_aqi(
                measurements,
                measurement_metadata=measurement_metadata,
                model_derived_aggregates=model_derived_aggregates,
                allow_1hr_precautionary_alternative=allow_1hr_precautionary_alternative,
            ),
            "INDIA_CPCB": calculate_india_cpcb_aqi(
                measurements,
                measurement_metadata=measurement_metadata,
                model_derived_aggregates=model_derived_aggregates,
            ),
            "EUROPEAN_AQI": calculate_european_aqi(
                measurements,
                measurement_metadata=measurement_metadata,
            )
        }

aqi_engine = AQIEngine()
