# AeroSense AI
### Global Urban Air Quality Intelligence & Environmental Health Assistant
*A complete, production-oriented environmental intelligence platform developed for Hack2Skill Challenge 6.*

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![MapLibre](https://img.shields.io/badge/MapLibre_GL-4.7-blue?logo=maplibre&logoColor=white)](https://maplibre.org)
[![Google Gemini](https://img.shields.io/badge/Google_Gemini-Function_Calling-4285F4?logo=google&logoColor=white)](https://ai.google.dev)
[![Testing](https://img.shields.io/badge/Tests-19%2F19%20Passed-brightgreen)](https://docs.pytest.org)

---

## 🌍 Product Vision

**AeroSense AI** transforms raw, fragmented ambient pollution measurements into actionable, reliable intelligence. Rather than offering a decorative weather widget or an ungrounded chatbot, AeroSense AI is an end-to-end environmental decision-support system serving citizens, sensitive health groups, commuters, athletes, researchers, and urban planners globally.

### Tagline
> **"Understand the air. Predict the risk. Make better decisions."**

---

## ⚡ Key Capabilities

1. **Global Overview Dashboard**: Real-time AQI gauge, multi-standard comparison, verified pollutant concentrations (PM2.5, PM10, NO₂, SO₂, CO, O₃), data freshness timers, and 24-hour predictive forecast timelines.
2. **Interactive Global Pollution Map**: MapLibre GL JS spatial map with CartoDB Dark Matter tiles, physical sensor markers from OpenAQ, and station metadata popups.
3. **GenAI Environmental Assistant**: Conversational AI powered by Google Gemini with backend-controlled function calling (`get_air_quality`, `compare_locations`, `get_pollution_history`, `get_forecast`, `get_health_guidance`). All statements are strictly grounded in retrieved environmental measurements with no hallucinated numbers.
4. **Deterministic AQI Engine**: Independent implementations of **US EPA AQI**, **India CPCB NAQI**, and **European EAQI** adhering strictly to official breakpoints, averaging times, and dominant pollutant calculations.
5. **Pollution Analytics & Spike Detection**: Contiguous 72-hour area and distribution charts with algorithmic anomaly detection alerting to sudden pollution surges (>60% above baseline).
6. **Health & Activity Advisor**: Evidence-based outdoor activity risk assessment (Running, Cycling, Walking, Outdoor Work, Pediatric/Asthma precautions).
7. **Cross-City Comparison**: Side-by-side multi-terminal comparative metrics for up to 5 global cities.
8. **Environmental Reports & PDF Export**: Instant generation of daily and weekly compliance briefings with cryptographic formatting and 1-click PDF download via ReportLab.
9. **Intelligent Alert Engine**: User-configured threshold rules and triggered alert event logs.
10. **Progressive Web App (PWA)**: Installable application shell, mobile-responsive navigation, and offline cache detection.

---

## 🏗️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Framer Motion, Recharts, MapLibre GL JS, Lucide Icons |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy, Greenlet, AsyncPG / aiosqlite, Bcrypt, PyJWT, ReportLab |
| **Data Providers** | **OpenAQ API v3** (Physical ground sensors) & **Open-Meteo Air Quality** (Global CAMS model & forecast) |
| **GenAI Platform** | **Google Gemini** (Function Calling, System Directives, Structured Output) + Fallback Deterministic Engine |
| **Testing** | Pytest (19 unit/integration tests), Vitest (Frontend unit tests) |
| **Database** | PostgreSQL ready via SQLAlchemy async engine (automatic SQLite fallback for zero-config local run) |

---

## 🚀 Quick Start (Local Setup)

### Prerequisites
- Python 3.11+
- Node.js 18+ & npm

### 1. Clone & Configure Backend
```bash
git clone https://github.com/your-username/aerosense-ai.git
cd "aerosense-ai"

# Setup virtual environment
python -m venv backend/venv

# Activate virtualenv
# On Windows:
backend\venv\Scripts\activate
# On Linux/macOS:
source backend/venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# (Optional) Create .env in backend/ or root
# GEMINI_API_KEY=your_gemini_key
# OPENAQ_API_KEY=your_openaq_key
```

### 2. Run Backend Server
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --app-dir backend
```
The FastAPI backend will start at `http://127.0.0.1:8000`.
- Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/v1/system/health`

### 3. Setup & Run Frontend
In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
The Vite development server will start at `http://localhost:5173`.

---

## 🧪 Running Automated Tests

### Backend Test Suite (Pytest)
```bash
# Run all 19 unit, provider, AQI and API tests:
backend/venv/Scripts/pytest -v
```

### Frontend Test Suite (Vitest)
```bash
cd frontend
npx vitest run
```

---

## 📚 Detailed Documentation

- [System Architecture](docs/architecture.md)
- [REST API Documentation](docs/api-documentation.md)
- [Data Sources & Integrity](docs/data-sources.md)
- [AQI Calculation Methodology](docs/aqi-methodology.md)
- [Security & Defense Architecture](docs/security.md)
- [Automated Testing Strategy](docs/testing.md)
- [Production Deployment Guide](docs/deployment.md)

---

## ⚖️ Evaluation Parameter Compliance

| Parameter | AeroSense AI Implementation |
| :--- | :--- |
| **1. Code Quality** | Modular layered FastAPI architecture, Pydantic v2 schemas, typed React TypeScript components, clean separation of concerns. |
| **2. Security** | Pure bcrypt password hashing, JWT bearer tokens, prompt injection filtering, strict backend-only tool execution, security headers (`nosniff`, `X-Frame-Options`). |
| **3. Efficiency** | Async I/O for external providers, Recharts optimizations, MapLibre GL JS vector-efficient rendering, manual code chunking (83 kB core JS bundle). |
| **4. Testing** | 19 automated Pytest suites verifying breakpoints, edge cases, provider APIs, AI function calling, and REST routes. |
| **5. Accessibility** | WCAG 2.1 AA compliant color contrasts, semantic markup, keyboard accessibility, clear focus states, screen-reader labels. |
| **6. Problem Statement** | Fully connected to real global environmental APIs (OpenAQ & Open-Meteo), genuine Gemini function calling, multi-standard AQI calculations, no fabricated readings. |
