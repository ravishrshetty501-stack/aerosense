# Automated Testing Strategy
**AeroSense AI — Quality Assurance Documentation**

---

## 1. Testing Architecture Overview

AeroSense AI enforces automated verification across all layers:
- **AQI Calculation Engine Tests**: Mathematical unit tests verifying breakpoints, edge cases, and CPCB particulate requirements.
- **Provider Adapter Tests**: Real network integration tests verifying OpenAQ and Open-Meteo API response schemas.
- **AI Tool Tests**: Verification of backend-controlled tool execution (`get_air_quality`, `compare_locations`, `get_health_guidance`).
- **REST API Endpoint Tests**: End-to-end ASGI test requests verifying auth registration, logins, location search, and health endpoints.
- **Frontend Vitest Tests**: Unit verification of color band scales, standard mappings, and provider distinction logic.

---

## 2. Running Automated Tests

### Full Backend Pytest Suite
```bash
# From workspace root:
& backend/venv/Scripts/pytest -v
```

### Verified Test Cases (19 / 19 Passing)
```
backend/tests/test_ai_tools.py::test_tool_get_air_quality PASSED         [  5%]
backend/tests/test_ai_tools.py::test_tool_compare_locations PASSED       [ 10%]
backend/tests/test_ai_tools.py::test_tool_get_health_guidance PASSED     [ 15%]
backend/tests/test_ai_tools.py::test_ai_chat_grounded_response PASSED    [ 21%]
backend/tests/test_api_endpoints.py::test_health_endpoint PASSED         [ 26%]
backend/tests/test_api_endpoints.py::test_location_search_endpoint PASSED [ 31%]
backend/tests/test_api_endpoints.py::test_aqi_calculate_endpoint PASSED  [ 36%]
backend/tests/test_api_endpoints.py::test_auth_registration_and_me PASSED [ 42%]
backend/tests/test_aqi_engine.py::test_epa_subindex_pm25 PASSED          [ 47%]
backend/tests/test_aqi_engine.py::test_us_epa_overall_aqi PASSED         [ 52%]
backend/tests/test_aqi_engine.py::test_cpcb_subindex_pm25 PASSED         [ 57%]
backend/tests/test_aqi_engine.py::test_cpcb_rule_missing_pm PASSED       [ 63%]
backend/tests/test_aqi_engine.py::test_cpcb_valid_calculation PASSED     [ 68%]
backend/tests/test_aqi_engine.py::test_european_aqi_bands PASSED         [ 73%]
backend/tests/test_aqi_engine.py::test_european_aqi_overall PASSED       [ 78%]
backend/tests/test_aqi_engine.py::test_unified_engine_dispatch PASSED    [ 84%]
backend/tests/test_providers.py::test_open_meteo_geocoding PASSED        [ 89%]
backend/tests/test_providers.py::test_open_meteo_air_quality PASSED      [ 94%]
backend/tests/test_providers.py::test_unified_data_manager PASSED        [100%]
```

### Frontend Vitest Suite
```bash
cd frontend
npx vitest run
```
```
✓ src/tests/App.test.ts (3 tests) 3ms
Test Files  1 passed (1)
Tests       3 passed (3)
```
