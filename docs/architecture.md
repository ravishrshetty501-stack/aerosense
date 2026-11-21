# System Architecture
**AeroSense AI — Global Urban Air Quality Intelligence Platform**

---

## 1. High-Level Architectural Diagram

```
+----------------------------------------------------------------------------------------+
|                                    CLIENT LAYER                                        |
|  React 18 + Vite + TypeScript + Tailwind CSS + MapLibre GL JS + Recharts + PWA         |
|                                                                                        |
|  [Overview Dashboard]   [Global Map]   [Trends & Spike Analytics]   [AI Assistant]    |
|  [City Comparison]      [Health Matrix][Reports & PDF Export]       [Alert Center]    |
+-------------------------------------------+--------------------------------------------+
                                            |
                                  HTTPS / REST / JSON
                                            |
+-------------------------------------------v--------------------------------------------+
|                                   BACKEND GATEWAY                                      |
|  FastAPI (ASGI) + Security Middleware + Pydantic v2 + Rate Limiting & Audit Logging    |
+-------------------------------------------+--------------------------------------------+
       |                     |                     |                     |
       v                     v                     v                     v
+--------------+      +--------------+      +--------------+      +--------------+
| Auth Service |      | AQI Engine   |      | Environmental|      | GenAI        |
| - JWT Tokens |      | - US EPA     |      | Data Manager |      | Orchestrator |
| - Bcrypt     |      | - India CPCB |      | - OpenAQ v3  |      | - Gemini API |
| - Users & DB |      | - EU EAQI    |      | - Open-Meteo |      | - Function   |
|              |      | - Dominant P.|      | - Normalizer |      |   Calling    |
+--------------+      +--------------+      +--------------+      +--------------+
       |                     |                     |                     |
+------v---------------------v---------------------v---------------------v--------------+
|                           DATABASE & PERSISTENCE LAYER                                |
|  SQLAlchemy 2.0 Async Engine (PostgreSQL in Production / aiosqlite for Local Dev)      |
|  Tables: users, locations, saved_locations, alert_rules, alert_events, reports         |
+----------------------------------------------------------------------------------------+
```

---

## 2. Key Architectural Decisions

### Layered Separation of Concerns
1. **API Router Layer** (`app/api/v1/*`): Thin controllers that validate input schemas, authenticate request context, and delegate to domain services.
2. **Domain Service Layer** (`app/services/*`): Pure business logic containing deterministic calculation routines, AI tool orchestration, alert evaluation, and PDF document generation.
3. **Data Integration Layer** (`app/services/providers/*`): Decoupled provider adapters conforming to the abstract base class `EnvironmentalProvider`. Neither frontend nor core business logic has direct coupling to external endpoints.
4. **Persistence Layer** (`app/models/*`): Normalized declarative models with primary UUID keys, foreign key constraints, UTC timestamps, and indexed query patterns.

### GenAI Controlled Function Calling
Rather than granting arbitrary network or database access to LLMs, AeroSense AI uses **backend-controlled tool execution**:
1. User prompt is sanitized and injected into a strict system prompt.
2. Google Gemini evaluates whether environmental tools are needed (`get_air_quality`, `compare_locations`, `get_health_guidance`).
3. The model returns structured tool call requests (`name`, `arguments`).
4. The backend securely executes the corresponding Python service.
5. Grounded data is returned to the model for authoritative synthesis.

### Database Portability
The SQLAlchemy configuration dynamically accepts `sqlite+aiosqlite:///` or `postgresql+asyncpg://`, enabling zero-dependency local runs out of the box while maintaining production readiness on hosted PostgreSQL instances (Neon, Supabase, Render, RDS).
