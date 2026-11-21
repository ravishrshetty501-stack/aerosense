# AeroSense AI — Comprehensive Repository & Functionality Audit Report
**Date:** November 21, 2026  
**Auditor:** Senior Software Architect, Environmental Data Engineer & UI/UX Director  
**Evaluation Scope:** Code Quality, Security, Efficiency, Testing, Accessibility, Problem Statement Alignment

---

## Executive Summary

AeroSense AI has an operational foundation including FastAPI routing, an asynchronous SQLAlchemy database, Open-Meteo atmospheric model ingestion, WAQI physical sensor ingestion, and multi-standard AQI formulas. However, the audit reveals several critical deficiencies:
1. **Mock and Hardcoded Data Injections:** `METRO_REFERENCE_STATIONS` and synthetic spatial offsets in `backend/app/api/v1/locations.py` fabricated station markers when provider keys were absent.
2. **Misleading Status Claims:** Network panels and dashboard headers claimed "VERIFIED", "CONNECTED", and "AUTHENTIC" without dynamic backend connectivity health validation.
3. **Map Rendering & Basemap Failure:** CartoDB basemap raster URLs produced `"API KEY REQUIRED"` watermarks across the globe, and map stations frequently showed `(0)` due to provider decoupling.
4. **City Comparison Duplication:** When viewing comparison metrics for cities like Delhi, the active city logic resulted in duplicate cards (e.g., `Delhi, London, Delhi`).
5. **Generic "AI Slop" UI/UX:** The user interface suffered from monospace typography overload, repetitive dark rectangular panels, glowing cyan outlines, excessive empty padding, and identical card structures across disparate functional modules.
6. **Incomplete GenAI Function Calling:** The assistant lacked declared handlers for `get_station_details`, `get_pollution_trends`, and `create_environmental_report`.

---

## 1. Feature Classification

| Status | Feature / Module | Audit Finding & Action Required |
| :--- | :--- | :--- |
| **Working** | US EPA AQI Engine | Correct breakpoints and piecewise linear interpolation. |
| **Working** | Open-Meteo Ingestion | Real global CAMS atmospheric data and 72-hour forecasts. |
| **Working** | WAQI Feed Integration | Real-time observation ingestion when `WAQI_API_KEY` is present. |
| **Partially Working** | India CPCB NAQI | Breakpoints correct, but requires dynamic handling for individual pollutant validity flags. |
| **Partially Working** | European EAQI | Band hierarchy implemented, but needs explicit band-to-index documentation. |
| **Partially Working** | GenAI Assistant | Function calling functional for basic tools, but missing station inspector, trend analyzer, and report creator tools. |
| **Partially Working** | PDF Report Generation | ReportLab compiles, but relies on static layout and lacks dynamic attribution details. |
| **Broken / Mocked** | Map Station Discovery | OpenAQ was failing with 401; fallback to `METRO_REFERENCE_STATIONS` fabricated static stations. **Must query live WAQI bounds and never fabricate.** |
| **Broken** | Map Basemap Tiles | `cartocdn.com` tiles show `"API KEY REQUIRED"` watermarks. Must use Esri World Dark Gray Canvas and clean OpenStreetMap vector/raster. |
| **Broken** | City Comparison | Default city selection allowed duplicate entries (`Delhi, London, Delhi`). No canonical deduplication on backend. |
| **Misleading** | Network Health Panel | Displayed hardcoded "CONNECTED" status for OpenAQ even when OpenAQ returned 401 unauthorized. |
| **UI/UX Problem** | Interface Aesthetic | Generic dark-mode SaaS dashboard with repetitive rectangular cards, monospaced fonts everywhere, and cyan glow. Needs total redesign with clean editorial layout and dark/light modes. |

---

## 2. Deep-Dive Audit Findings

### 2.1 Environmental Data Integration (WAQI & Open-Meteo)
* **Finding:** OpenAQ API v3 now requires an active API key with specific credit tiers, failing with HTTP 401 for unauthenticated public requests. WAQI was added as an alternative, but the station query endpoint (`/locations/stations`) was initially hardcoded to fall back to `METRO_REFERENCE_STATIONS`.
* **Action:**
  1. Designate **WAQI as the primary physical ground-station provider**.
  2. Implement WAQI's official `/v2/map/bounds/` and `/search/` endpoints with strict rate-limit protection.
  3. Designate **Open-Meteo as the secondary model-based estimate and forecast provider**.
  4. Completely remove `METRO_REFERENCE_STATIONS` and synthetic spatial coordinate offsets.

### 2.2 Data Integrity & Misleading Claims
* **Finding:** The dashboard displayed badges like `"PHYSICAL GROUND STATION ACTIVE"`, `"AUTHENTIC"`, and `"VERIFIED"` even when data was model-based, and network status showed `"CONNECTED"` statically.
* **Action:**
  1. Create a dynamic `/api/v1/system/network-status` endpoint that checks real provider pings (`connected`, `degraded`, `unavailable`, `not_configured`, with `last_successful_retrieval`).
  2. Clearly tag every value as `ground_observation`, `model_estimate`, or `forecast`.
  3. Show "Unavailable" for missing parameters instead of replacing them with 0 or mock data.

### 2.3 AQI Calculation Engine
* **Finding:** While breakpoints in `us_epa.py` and `india_cpcb.py` were mathematically sound, CPCB NAQI rules require explicit validation of at least 3 pollutants with at least one PM parameter. Furthermore, European EAQI should clearly distinguish between official band numbers (1 to 6) and normalized index scales.
* **Action:**
  1. Add strict unit tests with known government reference examples (EPA, CPCB, EEA).
  2. Implement canonical location identification so comparisons never compare identical coordinate nodes.

### 2.4 Map Implementation
* **Finding:** The map basemap used `cartocdn.com/dark_all` raster tiles, which produced persistent `"API KEY REQUIRED"` watermark tiles across the entire viewport. Furthermore, when stations failed to load, the UI rendered `(0)` stations or fell back to 4 hardcoded points.
* **Action:**
  1. Replace basemap with **Esri World Dark Gray Canvas & Reference System**, which is 100% open, high-contrast, free, and watermark-free.
  2. Use live WAQI station coordinates with numerical AQI badges directly inside map pins.

### 2.5 UI/UX Design System
* **Finding:** The current interface relies on repetitive rounded rectangular cards, glowing cyan borders, and monospaced typography for virtually all text. This creates a monotonous "AI-generated" look that fails Hack2Skill evaluation parameter 1 (Code Quality) and 5 (Accessibility & Design).
* **Action:**
  1. Establish a sophisticated dual-theme palette: Deep ink/slate for dark surfaces, clean warm neutral for light mode, with restrained cyan/teal and semantic AQI colors.
  2. Combine modern sans-serif typography for headings and prose with monospaced typography reserved exclusively for measurements, coordinates, and timestamps.
  3. Provide distinct visual architectures for each module (Overview, Map, Analytics, AI Assistant, City Comparison, Health Advisor, Reports, Alerts).

---

## 3. Remediation Execution Plan (Phases 2 – 9)

- **Phase 2:** Repair WAQI & Open-Meteo providers, remove all mock data, implement real dynamic network health checks.
- **Phase 3:** Audit and verify AQI calculation math and analytics aggregation.
- **Phase 4:** Rebuild the entire frontend design system (typography, color tokens, light/dark themes, distinctive module layouts).
- **Phase 5:** Rebuild the Interactive Map with watermark-free Esri Canvas tiles and live station clustering, and fix City Comparison canonical deduplication.
- **Phase 6:** Expand GenAI function calling with full suite of 8 backend tools and enhance chat interface.
- **Phase 7:** Rebuild Health Advisor, Alert Engine, and PDF report generator.
- **Phase 8:** Responsive layout verification, accessibility audit (WCAG AA), and security check.
- **Phase 9:** Comprehensive test suite execution and deployment verification.


---

## 4. Remediation & Verification Log

### 4.1 Ground Sensor Provider (WAQI) & Open-Meteo Integration
- **Primary Provider:** Configured WAQI API (`https://api.waqi.info`) using user-provided backend `WAQI_API_KEY`. Live bounding box queries (`/v2/map/bounds/`) return dozens of physical stations with authentic numerical AQI values.
- **Secondary Provider:** Open-Meteo Air Quality API provides 72-hour contiguous model forecasts and historical reanalysis without requiring external API tokens.
- **OpenAQ Handling:** Since OpenAQ API v3 requires active account authentication that returned 401, the system honestly labels OpenAQ as `not_configured` / standby. It **never claims OpenAQ is active** when it is not.
- **Mock Data Elimination:** Completely eradicated `METRO_REFERENCE_STATIONS` and synthetic spatial offset generation. If no physical station exists, the system returns an empty list and honestly indicates model estimate status.

### 4.2 Dynamic Network Health & Integrity
- Implemented `/api/v1/system/network-status` performing live asynchronous health checks:
  - WAQI: `connected` (ping verified).
  - Open-Meteo: `connected` (European AQI endpoint verified).
  - Gemini AI: `connected` (API key verified with function declarations).
  - OpenAQ: `not_configured` (truthful standby status).
- Removed all misleading badges (`"AUTHENTIC"`, `"VERIFIED"`, `"LIVE"`) across the UI. Every displayed value identifies source attribution, coordinate provenance, and data freshness.

### 4.3 Interactive Map Without Watermarks
- Replaced CartoDB tiles (which displayed intrusive `"API KEY REQUIRED"` watermarks) with **Esri World Dark Gray Canvas and Reference Overlay**.
- Added live station markers color-coded to US EPA severity tiers displaying exact numerical AQI scores.
- Added a station inspector drawer showing latitude/longitude, reported station name, and network operator.

### 4.4 Multi-Standard AQI Engine & Canonical Deduplication
- Validated piecewise linear breakpoints for:
  - **US EPA AQI:** 40 CFR Part 58 breakpoints across 6 pollutants.
  - **India CPCB NAQI:** Enforces 24-hr averaging breakpoints and 3-pollutant minimum validity criteria.
  - **European EAQI:** 6-tier air quality bands (1–6) normalized to standard indices.
- **Resolved City Comparison Bug:** Implemented canonical deduplication in `backend/app/api/v1/analytics.py` and `CityComparisonView.tsx` ensuring queries like `?cities=Delhi&cities=London&cities=Delhi` compare each city exactly once without duplicate cards.

### 4.5 GenAI Assistant with 8 Real Backend Function Calling Tools
Expanded `AEROSENSE_TOOLS` to include all 8 core tools executed strictly on the backend:
1. `get_air_quality`
2. `compare_locations`
3. `get_pollution_history`
4. `get_forecast`
5. `get_health_guidance`
6. `get_station_details`
7. `get_pollution_trends`
8. `create_environmental_report`
All assistant answers cite actual measurements and distinguish between physical observations and model estimates.

### 4.6 UI/UX Redesign Away from Generic "AI Slop"
- **Typography:** Shifted away from monospace overuse. General prose, headings, and tables use clean, modern sans-serif (`Inter`, system UI font); monospace is strictly reserved for measurements, coordinates, and timestamps.
- **Layout Architecture:** Eliminated repetitive uniform cards. Each of the 8 core modules has an individualized, purpose-built layout:
  - *Overview:* Hero AQI dial with WHO guideline comparison matrix and hourly forecast ribbon.
  - *Map:* Full-bleed Esri canvas with station clustering, filter pills, and inspector drawer.
  - *Analytics:* Recharts area trajectory with recent spike surge detection and multi-pollutant distribution bars.
  - *Assistant:* Conversational thread with markdown tables, suggested inquiry pills, and expandable grounding details.
  - *Comparison:* Side-by-side cards with relative best/worst highlighting and cross-reference table.
  - *Health Advisor:* Evidence-based activity matrix (running, cycling, walking, labor, sensitive demographics) with medical disclaimer.
  - *Reports:* On-demand compliance preview with ReportLab PDF export.
  - *Alerts:* In-app threshold rules and breach log.

### 4.7 Testing & Build Verification
- **Backend Tests:** 19/19 pytest tests passing (`test_ai_tools.py`, `test_api_endpoints.py`, `test_aqi_engine.py`, `test_providers.py`).
- **Frontend Tests:** 3/3 vitest tests passing.
- **Frontend Build:** `npm run build` compiled cleanly without TypeScript or chunking errors.
- **FastAPI Unified Server:** Running on port 8000, serving both the API (`/api/v1/*`) and the built single-page application.
