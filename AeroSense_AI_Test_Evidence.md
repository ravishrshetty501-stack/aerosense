# AeroSense AI — Final Test Evidence & Verification Logs
**Hack2Skill Challenge 6: Urban Air Quality Assistant**
**Date & Timestamp:** 2026-11-22T02:30:00Z  
**Platform Version:** AeroSense AI v1.0.0-production  
**Repository Branch:** `main` (clean working tree)

---

## 1. Automated Test Suite Execution Evidence

### 1.1 Backend Test Suite (Pytest + AsyncIO + Coverage)
- **Command:** `cd backend && pytest --cov=app --cov-report=term-missing`
- **Runner:** Python 3.11.9, pytest-9.2.0, anyio-4.16.0, asyncio-1.5.0, cov-7.1.0
- **Duration:** 66.49s
- **Total Tests:** 33
- **Passed:** 33 (100%)
- **Failed:** 0
- **Errors:** 0

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\ravis\OneDrive\Desktop\Airsense ai
configfile: pytest.ini
plugins: anyio-4.16.0, asyncio-1.5.0, cov-7.1.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collected 33 items

tests\test_ai_tools.py ....                                              [ 12%]
tests\test_analytics_and_intelligence.py ...                             [ 21%]
tests\test_api_endpoints.py ....                                         [ 33%]
tests\test_aqi_engine.py ........                                        [ 57%]
tests\test_fault_injection_and_edge_cases.py .....                       [ 72%]
tests\test_providers.py ...                                              [ 81%]
tests\test_security_resilience.py ......                                 [100%]

======================== 33 passed in 66.49s (0:01:06) ========================
```

#### Statement Coverage Summary (pytest-cov)
- **Total Statements:** 1,502
- **Covered Statements:** 1,062
- **Coverage Ratio:** 70.7% (~71%)
- **Key Modules:**
  - `app/services/aqi/us_epa.py`: 96%
  - `app/services/aqi/india_cpcb.py`: 94%
  - `app/core/security.py`: 100%
  - `app/core/rate_limit.py`: 100%
  - `app/api/v1/auth.py`: 95%
  - `app/services/ai_service.py`: 86%

---

### 1.2 Frontend Test Suite (Vitest)
- **Command:** `cd frontend && npm test -- --run`
- **Runner:** Vitest v2.1.9, Node.js v20+
- **Duration:** 485ms
- **Test Files:** 2 passed (2)
- **Total Tests:** 8 passed (100%)

```text
 RUN  v2.1.9 C:/Users/ravis/OneDrive/Desktop/Airsense ai/frontend

 ✓ src/tests/App.test.ts (3 tests) 3ms
 ✓ src/tests/aqi_intelligence.test.ts (5 tests) 2ms

 Test Files  2 passed (2)
      Tests  8 passed (8)
   Start at  07:58:19
   Duration  485ms (transform 42ms, setup 0ms, collect 71ms, tests 5ms, environment 0ms, prepare 287ms)
```

---

## 2. 20-Workflow End-to-End Production Smoke Test Evidence

- **Command:** `python scratch/smoke_test_20.py`
- **Target URL:** `http://127.0.0.1:8000` (FastAPI production daemon)
- **Result:** **20 of 20 PASSED (100%)**

```text
[PASS] Workflow 01: Application Initial Shell Load - Status: 200, Length: 1375 bytes
[PASS] Workflow 02: System Health Check Endpoints - /health: 200, /api/v1/system/health: 200
[PASS] Workflow 03: Prometheus Metrics Scrape - Status: 200, Format: text/plain, Metrics scraped: 3
[PASS] Workflow 04: Interactive OpenAPI Documentation - Status: 200, Endpoints indexed: 28
[PASS] Workflow 05: Current Air Quality (Tokyo, US_EPA) - AQI: 61, Category: Moderate, Ground: True
[PASS] Workflow 06: Current Air Quality (Delhi, CPCB) - AQI: 388, Category: Very Poor
[PASS] Workflow 07: Standard Selection US_EPA - Standard: US_EPA, AQI: 61, Color: #f59e0b
[PASS] Workflow 08: Standard Selection INDIA_CPCB - Standard: INDIA_CPCB, AQI: 117, Dominant: CO
[PASS] Workflow 09: Physical Monitoring Stations Discovery - Stations discovered: 40, Provider: WAQI Physical Sensor Network, Sample: Karuizawa, Kamagaya, Chiba, Japan (鎌ケ谷軽井沢鎌ケ谷市)
[PASS] Workflow 10: Historical Air Quality Reanalysis - Contiguous historical points: 48
[PASS] Workflow 11: 24h Atmospheric Forecast Timeline - Forecast intervals: 60
[PASS] Workflow 12: Health & Activity Risk Advisory - Advisory length: 106 chars: 'Air quality is acceptable. Unusually sensitive people should...'
[PASS] Workflow 13: Environmental Compliance Summary Report - City: Tokyo, AQI: 61, Source: WAQI Ground Station (Chuo, Nakano, Tokyo, Japan (山手通り東中野中野区)) (Physical Ground Sensor)
[PASS] Workflow 14: System Network & Telemetry Status - Status: operational, WAQI: connected, Open-Meteo: connected, Gemini: connected
[PASS] Workflow 15: User Account Registration - Status: 201, User: smoke_user_c91615@aerosense.ai, Token generated: True
[PASS] Workflow 16: User Authentication & JWT Token Issuance - Token Type: bearer, Token preview: eyJhbGciOiJI...
[PASS] Workflow 17: Intelligent Alert Rule Creation - Status: 201, Rule ID: 6d586fe0-df18-472e-a357-480f2ff597c6
[PASS] Workflow 18: Alert Rules Retrieval - Status: 200, Rules active: 1
[PASS] Workflow 19: AI Assistant Grounded Reasoning - Status: 200, Reply length: 811 chars, Grounded preview: ### Environmental Intelligence Briefing: Tokyo

**Current Ai...
[PASS] Workflow 20: Static Assets & PWA Service Worker - /sw.js: 200, /favicon.svg: 200

==========================================
DEPLOYMENT SMOKE TEST SUMMARY: 20/20 PASSED
==========================================
```

---

## 3. Web Accessibility (axe-core WCAG 2.2 AA) Audit Evidence

- **Engine:** axe-core v4.9.1 injected into headless Chromium via Playwright
- **Viewport:** 1920x1080
- **Audited Views:** 7 major application views

| Application View | Passed WCAG Rules | Incomplete Rules | Violations | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Intelligent Alerts** | 17 | 0 | **0** | **100% CLEAN** |
| **Pollution Analytics** | 20 | 1 | **0** | **100% CLEAN** |
| **Environmental Reports** | 18 | 0 | **0** | **100% CLEAN** |
| **Overview Dashboard** | 23 | 1 | 1 | Contrast on dynamic AQI badge |
| **Global Map** | 21 | 1 | 1 | MapLibre marker wrapper role |
| **AI Assistant** | 17 | 1 | 1 | Sub-pixel bold text (4.44:1) |
| **Health Advisor** | 18 | 0 | 1 | Dynamic severity badge color |

### axe-core Detailed Console Transcript
```text
--- Running Axe WCAG 2.2 AA Audit on: Overview Dashboard ---
  Passed Rules: 23
  Incomplete/Manual Review Rules: 1
  Violations: 1 (AQI severity badge dynamic contrast)

--- Running Axe WCAG 2.2 AA Audit on: Global Map ---
  Passed Rules: 21
  Incomplete/Manual Review Rules: 1
  Violations: 1 (MapLibre DOM marker wrapper aria-label)

--- Running Axe WCAG 2.2 AA Audit on: Pollution Analytics ---
  Passed Rules: 20
  Incomplete/Manual Review Rules: 1
  Violations: 0
  [SUCCESS] ZERO WCAG Violations found on this page!

--- Running Axe WCAG 2.2 AA Audit on: AI Assistant ---
  Passed Rules: 17
  Incomplete/Manual Review Rules: 1
  Violations: 1 (Grounded response strong tag 4.44:1)

--- Running Axe WCAG 2.2 AA Audit on: Health Advisor ---
  Passed Rules: 18
  Incomplete/Manual Review Rules: 0
  Violations: 1 (Activity card caution pill text)

--- Running Axe WCAG 2.2 AA Audit on: Intelligent Alerts ---
  Passed Rules: 17
  Incomplete/Manual Review Rules: 0
  Violations: 0
  [SUCCESS] ZERO WCAG Violations found on this page!

--- Running Axe WCAG 2.2 AA Audit on: Environmental Reports ---
  Passed Rules: 18
  Incomplete/Manual Review Rules: 0
  Violations: 0
  [SUCCESS] ZERO WCAG Violations found on this page!
```

---

## 4. Bundle & Code-Splitting Verification Evidence

- **Vite Build:** 2,186 modules transformed in 6.96s
- **Initial App Shell:** 43.15 KB (11.07 KB gzip)
- **Async Vendors Isolated:**
  - `react-vendor`: 171.62 KB (53.95 KB gzip)
  - `recharts`: 367.33 KB (101.37 kB gzip)
  - `maplibre-gl`: 801.65 KB (217.61 KB gzip) — Loaded strictly on-demand on Map view

```text
dist/index.html                               1.38 kB │ gzip:   0.69 kB
dist/assets/index-dnBybLt1.css               46.61 kB │ gzip:   8.25 kB
dist/assets/chevron-up-smhkzxEE.js            0.30 kB │ gzip:   0.25 kB
dist/assets/plus-BQZmTQyB.js                  0.32 kB │ gzip:   0.25 kB
dist/assets/info-D_qEw2cx.js                  0.37 kB │ gzip:   0.28 kB
dist/assets/download-B3nxs1Qw.js              0.43 kB │ gzip:   0.32 kB
dist/assets/trash-2-DCDoo4rb.js               0.53 kB │ gzip:   0.35 kB
dist/assets/radio-DWbYyeYY.js                 0.53 kB │ gzip:   0.35 kB
dist/assets/ReportsView-CGsw99XU.js           8.05 kB │ gzip:   2.09 kB
dist/assets/AnalyticsView-DfTrvBFa.js         8.65 kB │ gzip:   2.87 kB
dist/assets/CityComparisonView-DeT6NVb2.js   10.71 kB │ gzip:   2.94 kB
dist/assets/AlertsView-DLmJYosy.js           10.90 kB │ gzip:   2.84 kB
dist/assets/HealthAdvisorView-wjaOEDM7.js    11.96 kB │ gzip:   3.80 kB
dist/assets/AIAssistantView-B6hvw878.js      12.90 kB │ gzip:   3.85 kB
dist/assets/OverviewDashboard-CjEhpUj4.js    22.54 kB │ gzip:   5.02 kB
dist/assets/GlobalPollutionMap-CsDvftTh.js   24.97 kB │ gzip:   6.19 kB
dist/assets/index-BdPDJ124.js                43.15 kB │ gzip:  11.07 kB
dist/assets/react-vendor-CWavQDlM.js        171.62 kB │ gzip:  53.95 kB
dist/assets/recharts-Zo5sifne.js            367.33 kB │ gzip: 101.37 kB
dist/assets/maplibre-B2W_8ViP.js            801.65 kB │ gzip: 217.61 kB
```

---

## 5. PostgreSQL Production Engine & Dialect Verification Evidence

- **Command:** `python scratch/verify_postgres_config.py`
- **Dialect:** PostgreSQL (via `asyncpg`)
- **Schema Entities:** 12 tables verified

```text
--- Verifying PostgreSQL Configuration & Schema Readiness ---
[PASS] Scheme Translation: postgresql://user:password@db.example.com:5432/aerosense -> postgresql+asyncpg://user:password@db.example.com:5432/aerosense
[PASS] Engine Connection Pool Options: {'pool_size': 10, 'max_overflow': 20, 'pool_pre_ping': True, 'pool_recycle': 3600}
[PASS] Discovered SQLAlchemy Models/Tables (12): ['users', 'saved_locations', 'locations', 'monitoring_stations', 'measurements', 'aqi_calculations', 'alert_rules', 'alert_events', 'chat_sessions', 'chat_messages', 'environmental_reports', 'api_usage_logs']
[PASS] All 12 table DDLs successfully compiled against PostgreSQL dialect!

[EVALUATION] Live PostgreSQL Server Connection Status:
  - Static Driver (asyncpg): INSTALLED & VERIFIED
  - Connection Pooling: CONFIGURED (pool_size=10, max_overflow=20, pre_ping=True)
  - Model Schema DDLs: 100% COMPILED FOR POSTGRESQL DIALECT
  - External Live Server: BLOCKED / NOT CONFIGURED (Requires external cloud credentials; local environment uses persistent aiosqlite)
```

---

## 6. Live Upstream Provider Verification Evidence

### Scenario A: Normal Operating Telemetry (WAQI + Gemini)
```text
=== Scenario A: Live Physical Sensor Retrieval ===
WAQI Physical Feed Result:
  Station Name: Chuo, Nakano, Tokyo, Japan (山手通り東中野中野区)
  Observed PM2.5: 17.0 ug/m3
  Raw WAQI AQI: 61
  Last Recorded Observation: 2026-11-22 09:00:00+09:00
  Verification Result: PASS (Authentic physical sensor data successfully ingested)
```

### Scenario B: Upstream Outage / 503 Fallback Telemetry
```text
=== Scenario B: Simulated WAQI Sensor Outage (503 Service Unavailable) ===
Fallback Engine Triggered:
  Station Name: Tokyo (Modelled Atmospheric Estimate)
  Observed PM2.5: 22.4 ug/m3 (Copernicus CAMS Reanalysis)
  Calculated US EPA AQI: 73
  Data Quality Flag: is_ground_observation = False
  HTTP Status Code: 200 OK (Graceful degradation, zero crash)
  Verification Result: PASS (Application successfully fell back to atmospheric model)
```

---

## 7. Security & Secret Scan Evidence

- **Scanner:** Automated regex pattern scan across source code and Git history
- **Patterns Checked:** Google Gemini API keys (`AIzaSy...`), WAQI tokens (`[a-f0-9]{40}`), JWT secrets, database connection passwords
- **Violations Found in Source Code:** **0** (All secrets strictly sourced from environment variables)
- **CORS Allowed Origins:** Explicit origin list (`http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:8000`, `http://127.0.0.1:8000`), credentials permitted with no wildcard `*`.
