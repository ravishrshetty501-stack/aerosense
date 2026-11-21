# REST API Documentation
**AeroSense AI — Version 1.0.0**

All API endpoints are prefixed with `/api/v1`.
Interactive Swagger UI is available at `/docs` and ReDoc at `/redoc`.

---

## 1. Authentication (`/api/v1/auth`)

### `POST /auth/register`
Creates a new analyst account and returns an access token.
- **Request Body**:
  ```json
  {
    "email": "analyst@aerosense.ai",
    "password": "SecurePassword123!",
    "full_name": "Dr. Environmentalist",
    "preferred_standard": "US_EPA",
    "theme": "dark"
  }
  ```
- **Response** (`201 Created`):
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "user": {
      "id": "uuid-v4",
      "email": "analyst@aerosense.ai",
      "full_name": "Dr. Environmentalist",
      "preferred_standard": "US_EPA",
      "theme": "dark",
      "is_active": true,
      "created_at": "2026-11-21T10:00:00Z"
    }
  }
  ```

### `POST /auth/login`
Authenticates user with email and password.
- **Response**: Same as `/auth/register`.

### `GET /auth/me`
Returns details of the currently authenticated user. Requires `Authorization: Bearer <token>`.

---

## 2. Locations (`/api/v1/locations`)

### `GET /locations/search?q={query}`
Searches global locations via geocoding.
- **Response**: Array of locations with `name`, `country`, `latitude`, `longitude`, `timezone`.

### `GET /locations/popular`
Returns a curated list of global mega-cities with established coordinates for instant terminal switching.

### `GET /locations/stations?lat={lat}&lon={lon}&radius={meters}`
Queries nearby physical ground-level monitoring stations via OpenAQ API v3.

---

## 3. Air Quality (`/api/v1/air-quality`)

### `GET /air-quality/current?city={city}&standard={standard}`
Retrieves real-time unified air quality for a target city or coordinate pair.
- **Query Parameters**:
  - `city` (string, optional)
  - `lat` (float, optional)
  - `lon` (float, optional)
  - `standard` (string: `US_EPA`, `INDIA_CPCB`, `EUROPEAN_AQI`)
- **Response**: Full `AirQualityResponse` including raw pollutant measurements, observation types, source attribution, multi-standard AQI calculations, dominant pollutant, data freshness in minutes, and forecast series.

---

## 4. AQI Engine (`/api/v1/aqi`)

### `POST /aqi/calculate?standard={standard}`
Deterministic calculation of AQI based on supplied raw concentrations.
- **Request Body**:
  ```json
  {
    "pm25": 35.4,
    "pm10": 70.0,
    "no2": 45.0,
    "o3": 25.0
  }
  ```
- **Response**:
  ```json
  {
    "standard": "US_EPA",
    "aqi": 100,
    "category": "Moderate",
    "dominant_pollutant": "PM25",
    "color": "#f59e0b",
    "advisory": "Air quality is acceptable...",
    "is_reliable": true
  }
  ```

### `POST /aqi/compare-standards`
Calculates and returns US EPA, India CPCB, and European AQI simultaneously for the same pollutant concentrations.

---

## 5. GenAI Assistant (`/api/v1/ai`)

### `POST /ai/chat`
Conversational endpoint orchestrating Google Gemini with backend function calling.
- **Request Body**:
  ```json
  {
    "message": "Is today safe for running in Tokyo?",
    "location_hint": "Tokyo",
    "conversation_history": []
  }
  ```
- **Response**:
  ```json
  {
    "response": "Markdown formatted grounded analysis...",
    "tool_calls": [{"name": "get_air_quality", "args": {"location": "Tokyo"}}],
    "grounding_data": {...},
    "model": "gemini-1.5-flash"
  }
  ```

---

## 6. Environmental Reports (`/api/v1/reports`)

### `GET /reports/data?city={city}&period={period}&standard={standard}`
Generates structured report metadata and pollutant summaries.

### `GET /reports/export/pdf?city={city}&period={period}&standard={standard}`
Downloads official PDF report generated on the backend with ReportLab (`Content-Type: application/pdf`).
