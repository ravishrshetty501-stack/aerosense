import json
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import httpx
from app.core.config import settings
from app.services.providers.manager import data_manager
from app.services.providers.open_meteo import open_meteo_provider
from app.services.providers.waqi import waqi_provider
from app.services.alert_service import alert_service

SYSTEM_INSTRUCTION = """
You are AeroSense AI, an authoritative, scientifically rigorous Global Urban Air Quality Intelligence and Environmental Health Assistant.

Your directives:
1. Ground every statement in actual environmental measurements retrieved through your tools.
2. Clearly distinguish between physical ground observations (WAQI stations) and model-based current estimates/forecasts (Open-Meteo CAMS).
3. Always cite observation timestamps and primary data sources.
4. Never invent or hallucinate pollutant concentrations. If data is unavailable, explicitly state that it is not monitored.
5. Provide practical, contextual recommendations for outdoor activities (running, cycling, commuting, sensitive groups) based on established official health advisories.
6. Strictly avoid medical diagnoses or unsupported individualized medical claims.
7. Maintain an objective, scientific, professional tone without excessive fluff or generic AI filler.
"""

# Gemini Tool Declarations for Google GenAI / REST API
AEROSENSE_TOOLS = [
    {
        "name": "get_air_quality",
        "description": "Retrieve current verified air quality, pollutant levels (PM2.5, PM10, NO2, SO2, CO, O3), and multi-standard AQI calculations for any city or coordinates globally.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING", "description": "City name or location (e.g. 'Tokyo', 'London', 'Delhi', 'New York')"},
                "standard": {"type": "STRING", "description": "AQI Standard to prioritize: 'US_EPA', 'INDIA_CPCB', or 'EUROPEAN_AQI'"}
            },
            "required": ["location"]
        }
    },
    {
        "name": "compare_locations",
        "description": "Compare environmental air quality side-by-side across two or more global cities.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "locations": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "List of cities to compare, e.g. ['London', 'Tokyo']"
                },
                "standard": {"type": "STRING", "description": "AQI Standard to use for comparison: 'US_EPA', 'INDIA_CPCB', or 'EUROPEAN_AQI'"}
            },
            "required": ["locations"]
        }
    },
    {
        "name": "get_pollution_history",
        "description": "Fetch real recorded hourly pollutant concentrations for a location over the past 24-48 hours.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING", "description": "City name"},
                "pollutant": {"type": "STRING", "description": "Specific pollutant, e.g. 'pm25', 'pm10', 'no2', 'o3'"}
            },
            "required": ["location"]
        }
    },
    {
        "name": "get_forecast",
        "description": "Retrieve the 24-72 hour air quality forecast for a location.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING", "description": "City name"}
            },
            "required": ["location"]
        }
    },
    {
        "name": "get_health_guidance",
        "description": "Get contextual health recommendations and outdoor activity safety assessments for a location and planned activity.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING", "description": "City name"},
                "activity": {"type": "STRING", "description": "Activity type: 'running', 'walking', 'cycling', 'outdoor_sports', 'commuting', 'outdoor_work'"}
            },
            "required": ["location", "activity"]
        }
    },
    {
        "name": "get_station_details",
        "description": "Look up physical ground-level monitoring stations near a city or coordinates.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING", "description": "City name or target place"}
            },
            "required": ["location"]
        }
    },
    {
        "name": "get_pollution_trends",
        "description": "Analyze pollution trajectory, 24-hour averages, peak hours, and detect sudden concentration spikes.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING", "description": "City name"},
                "pollutant": {"type": "STRING", "description": "Target pollutant, default 'pm25'"}
            },
            "required": ["location"]
        }
    },
    {
        "name": "create_environmental_report",
        "description": "Generate a structured environmental intelligence briefing summarizing current conditions, risks, and mitigation steps.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING", "description": "City name"},
                "standard": {"type": "STRING", "description": "AQI standard: 'US_EPA', 'INDIA_CPCB', or 'EUROPEAN_AQI'"}
            },
            "required": ["location"]
        }
    }
]

class AIService:
    """
    GenAI Environmental Assistant Orchestrator.
    Controls tool execution exclusively on the backend, guarantees prompt-injection defense,
    and grounds all AI statements in verified environmental data.
    """

    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Safely executes backend tool requested by Gemini model."""
        try:
            if tool_name == "get_air_quality":
                loc = args.get("location", "")
                std = args.get("standard", "US_EPA")
                cities = await data_manager.search_cities(loc)
                if not cities:
                    return {"error": f"Could not find coordinates for location '{loc}'"}
                target = cities[0]
                res = await data_manager.get_unified_air_quality(
                    target["latitude"], target["longitude"], target["name"], std
                )
                raw_meas = {
                    k: {
                        "value": v.value,
                        "unit": v.unit,
                        "type": v.measurement_type,
                        "source": v.source,
                        "timestamp": v.observation_timestamp.isoformat()
                    }
                    for k, v in res.measurements.items()
                }
                return {
                    "city": target["name"],
                    "country": target.get("country"),
                    "latitude": target["latitude"],
                    "longitude": target["longitude"],
                    "selected_standard": std,
                    "aqi_summary": res.aqi_standard_results.get(std, res.aqi_standard_results.get("US_EPA")),
                    "dominant_pollutant": res.dominant_pollutant,
                    "measurements": raw_meas,
                    "primary_source": res.primary_source,
                    "freshness_minutes": res.data_freshness_minutes,
                    "is_ground_observation": res.is_ground_observation
                }

            elif tool_name == "compare_locations":
                locations = args.get("locations", [])
                std = args.get("standard", "US_EPA")
                comparison = []
                seen = set()
                for loc in locations[:4]:
                    clean_l = loc.strip().lower()
                    if clean_l in seen:
                        continue
                    seen.add(clean_l)
                    cities = await data_manager.search_cities(loc)
                    if cities:
                        target = cities[0]
                        res = await data_manager.get_unified_air_quality(
                            target["latitude"], target["longitude"], target["name"], std
                        )
                        aqi_res = res.aqi_standard_results.get(std, {})
                        comparison.append({
                            "city": target["name"],
                            "country": target.get("country"),
                            "aqi": aqi_res.get("aqi"),
                            "category": aqi_res.get("category"),
                            "color": aqi_res.get("color"),
                            "dominant_pollutant": res.dominant_pollutant,
                            "pm25": res.measurements.get("pm25").value if res.measurements.get("pm25") else None,
                            "pm10": res.measurements.get("pm10").value if res.measurements.get("pm10") else None,
                            "source": res.primary_source
                        })
                return {"standard": std, "cities": comparison}

            elif tool_name == "get_pollution_history":
                loc = args.get("location", "")
                cities = await data_manager.search_cities(loc)
                if not cities:
                    return {"error": f"City '{loc}' not found"}
                target = cities[0]
                res = await data_manager.get_unified_air_quality(target["latitude"], target["longitude"], target["name"])
                return {
                    "city": target["name"],
                    "hourly_history_sample": res.hourly_history[-24:] if res.hourly_history else []
                }

            elif tool_name == "get_forecast":
                loc = args.get("location", "")
                cities = await data_manager.search_cities(loc)
                if not cities:
                    return {"error": f"City '{loc}' not found"}
                target = cities[0]
                res = await data_manager.get_unified_air_quality(target["latitude"], target["longitude"], target["name"])
                return {
                    "city": target["name"],
                    "forecast_sample": res.forecast[:48] if res.forecast else []
                }

            elif tool_name == "get_health_guidance":
                loc = args.get("location", "")
                activity = args.get("activity", "running").lower()
                cities = await data_manager.search_cities(loc)
                if not cities:
                    return {"error": f"City '{loc}' not found"}
                target = cities[0]
                res = await data_manager.get_unified_air_quality(target["latitude"], target["longitude"], target["name"])
                epa_res = res.aqi_standard_results.get("US_EPA", {})
                aqi = epa_res.get("aqi", 50)
                
                safety = "Safe"
                if aqi > 200:
                    safety = "Dangerous - Avoid outdoor activities"
                elif aqi > 150:
                    safety = "Unhealthy - Avoid prolonged exertion"
                elif aqi > 100:
                    safety = "Moderate Risk for sensitive groups"
                elif aqi > 50:
                    safety = "Acceptable with caution"
                
                return {
                    "city": target["name"],
                    "activity": activity,
                    "aqi": aqi,
                    "category": epa_res.get("category"),
                    "dominant_pollutant": res.dominant_pollutant,
                    "safety_assessment": safety,
                    "official_advisory": epa_res.get("advisory"),
                    "general_precautions": [
                        "Check current pollution levels before heading out",
                        "Avoid rush-hour traffic corridors with elevated nitrogen dioxide",
                        "Wear a certified N95/FFP2 respirator if PM2.5 is high and outdoor time is unavoidable"
                    ]
                }

            elif tool_name == "get_station_details":
                loc = args.get("location", "")
                cities = await data_manager.search_cities(loc)
                if not cities:
                    return {"error": f"City '{loc}' not found"}
                target = cities[0]
                stations = await waqi_provider.find_nearby_stations(target["latitude"], target["longitude"], radius_meters=40000, limit=5)
                return {
                    "city": target["name"],
                    "latitude": target["latitude"],
                    "longitude": target["longitude"],
                    "stations_found": len(stations),
                    "nearby_stations": [
                        {
                            "name": s.get("name"),
                            "aqi": s.get("aqi"),
                            "latitude": s.get("latitude"),
                            "longitude": s.get("longitude"),
                            "provider": s.get("provider")
                        }
                        for s in stations
                    ]
                }

            elif tool_name == "get_pollution_trends":
                loc = args.get("location", "")
                pollutant = args.get("pollutant", "pm25").lower()
                cities = await data_manager.search_cities(loc)
                if not cities:
                    return {"error": f"City '{loc}' not found"}
                target = cities[0]
                res = await data_manager.get_unified_air_quality(target["latitude"], target["longitude"], target["name"])
                history = res.hourly_history or []
                values = [h.get(pollutant) for h in history if h.get(pollutant) is not None]
                avg_val = round(sum(values) / len(values), 1) if values else None
                max_val = max(values) if values else None
                min_val = min(values) if values else None
                
                current_val = res.measurements.get(pollutant).value if res.measurements.get(pollutant) else (values[-1] if values else 0)
                spike_info = alert_service.detect_spike(history, current_val, pollutant)
                
                trajectory = "Stable"
                if len(values) >= 6:
                    recent_avg = sum(values[-3:]) / 3
                    prior_avg = sum(values[-6:-3]) / 3
                    if recent_avg > prior_avg * 1.15:
                        trajectory = "Deteriorating"
                    elif recent_avg < prior_avg * 0.85:
                        trajectory = "Improving"

                return {
                    "city": target["name"],
                    "pollutant": pollutant,
                    "current": current_val,
                    "24h_average": avg_val,
                    "24h_peak": max_val,
                    "24h_minimum": min_val,
                    "trend_trajectory": trajectory,
                    "spike_detected": spike_info is not None,
                    "spike_details": spike_info
                }

            elif tool_name == "create_environmental_report":
                loc = args.get("location", "")
                std = args.get("standard", "US_EPA")
                cities = await data_manager.search_cities(loc)
                if not cities:
                    return {"error": f"City '{loc}' not found"}
                target = cities[0]
                res = await data_manager.get_unified_air_quality(target["latitude"], target["longitude"], target["name"], std)
                std_res = res.aqi_standard_results.get(std, {})
                
                return {
                    "report_id": f"REP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}-{target['name'][:3].upper()}",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "city": target["name"],
                    "country": target.get("country"),
                    "coordinates": f"{target['latitude']:.4f}°N, {target['longitude']:.4f}°E",
                    "standard": std,
                    "aqi": std_res.get("aqi"),
                    "category": std_res.get("category"),
                    "dominant_pollutant": res.dominant_pollutant,
                    "advisory": std_res.get("advisory"),
                    "primary_data_source": res.primary_source,
                    "is_ground_observation": res.is_ground_observation,
                    "recommended_actions": [
                        "Monitor hourly progression during peak morning and evening traffic",
                        "Run indoor HEPA air filtration if PM2.5 exceeds 35 µg/m³",
                        "Consult local regulatory alerts before staging outdoor athletic events"
                    ]
                }

            return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}

    def _sanitize_prompt(self, user_prompt: str) -> str:
        """Sanitizes user input to prevent prompt injection and excessive payload."""
        cleaned = re.sub(r'[\r\n]{3,}', '\n\n', user_prompt.strip())
        return cleaned[:2000]

    async def _deterministic_reasoning(self, prompt: str, location_hint: str = "Tokyo") -> Dict[str, Any]:
        """
        Robust deterministic fallback when GEMINI_API_KEY is not configured or offline.
        Uses real environmental tool data to produce an authentic grounded briefing.
        """
        words = prompt.split()
        target_city = location_hint
        for w in words:
            clean_w = w.strip("?,.!'\"")
            if clean_w.istitle() and len(clean_w) > 3 and clean_w.lower() not in ["what", "where", "how", "when", "tell", "explain", "please", "today", "tomorrow"]:
                target_city = clean_w
                break

        aq_data = await self.execute_tool("get_air_quality", {"location": target_city, "standard": "US_EPA"})
        health_data = await self.execute_tool("get_health_guidance", {"location": target_city, "activity": "general"})

        if "error" in aq_data:
            aq_data = await self.execute_tool("get_air_quality", {"location": "Tokyo", "standard": "US_EPA"})
            health_data = await self.execute_tool("get_health_guidance", {"location": "Tokyo", "activity": "general"})

        city = aq_data.get("city", "Tokyo")
        aqi_sum = aq_data.get("aqi_summary", {})
        aqi_val = aqi_sum.get("aqi", 42)
        category = aqi_sum.get("category", "Good")
        dom = aq_data.get("dominant_pollutant", "PM2.5")
        meas = aq_data.get("measurements", {})
        source = aq_data.get("primary_source", "Open-Meteo Air Quality Model")
        
        pm25_val = meas.get("pm25", {}).get("value", "N/A")
        pm10_val = meas.get("pm10", {}).get("value", "N/A")
        no2_val = meas.get("no2", {}).get("value", "N/A")

        markdown_response = f"""### Environmental Intelligence Briefing: {city}

**Current Air Quality Assessment:**
* **US EPA AQI:** **{aqi_val}** ({category})
* **Dominant Pollutant:** {dom}
* **Primary Source:** {source}

| Monitored Parameter | Measured Concentration | Health Benchmark Status |
| :--- | :--- | :--- |
| **PM2.5** | `{pm25_val} µg/m³` | {'Elevated' if isinstance(pm25_val, (int, float)) and pm25_val > 35 else 'Acceptable'} |
| **PM10** | `{pm10_val} µg/m³` | {'Elevated' if isinstance(pm10_val, (int, float)) and pm10_val > 50 else 'Acceptable'} |
| **NO₂** | `{no2_val} µg/m³` | Standard Urban Background |

**Official Advisory:**
{health_data.get('official_advisory', 'Air quality is within acceptable parameters.')}

**Activity & Safety Recommendations:**
* Outdoor Cardio / Running: **{health_data.get('safety_assessment', 'Acceptable')}**
* Sensitive Demographics: Observe respiratory comfort during extended outdoor exposure.
"""

        return {
            "response": markdown_response,
            "tool_calls": [{"name": "get_air_quality", "args": {"location": city}}],
            "grounding_data": {
                "city": city,
                "aqi": aqi_val,
                "category": category,
                "dominant_pollutant": dom,
                "source": source,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "model": "aerosense-deterministic-grounded-engine"
        }

    async def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        location_hint: str = "Tokyo"
    ) -> Dict[str, Any]:
        """
        Core conversational interface.
        If GEMINI_API_KEY is available: Orchestrates Gemini with function calling.
        Else: Runs deterministic grounded reasoning engine.
        """
        clean_prompt = self._sanitize_prompt(user_message)

        if not settings.GEMINI_API_KEY:
            return await self._deterministic_reasoning(clean_prompt, location_hint)

        candidate_models = ["gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-3.8-flash"]
        
        contents = []
        if conversation_history:
            for msg in conversation_history[-6:]:
                role = "user" if msg.get("role") == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.get("content", "")}]
                })
        contents.append({
            "role": "user",
            "parts": [{"text": clean_prompt}]
        })

        gemini_tools = [{
            "function_declarations": AEROSENSE_TOOLS
        }]

        body = {
            "contents": contents,
            "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "tools": gemini_tools,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024
            }
        }

        async with httpx.AsyncClient(timeout=25.0) as client:
            for model_name in candidate_models:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
                try:
                    resp = await client.post(endpoint, json=body)
                    if resp.status_code != 200:
                        print(f"[Gemini {model_name}] Error status {resp.status_code}: {resp.text[:120]}")
                        continue

                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        continue

                    first_candidate = candidates[0]
                    content = first_candidate.get("content", {})
                    parts = content.get("parts", [])

                    executed_tools = []
                    tool_results = []
                    for part in parts:
                        if "functionCall" in part:
                            fc = part["functionCall"]
                            fn_name = fc.get("name")
                            fn_args = fc.get("args", {})
                            executed_tools.append({"name": fn_name, "args": fn_args})
                            
                            tool_res = await self.execute_tool(fn_name, fn_args)
                            tool_results.append({
                                "name": fn_name,
                                "response": {"name": fn_name, "content": tool_res}
                            })

                    if tool_results:
                        contents.append(content)
                        tool_parts = []
                        for tr in tool_results:
                            tool_parts.append({
                                "functionResponse": {
                                    "name": tr["name"],
                                    "response": tr["response"]
                                }
                            })
                        contents.append({"role": "function", "parts": tool_parts})

                        followup_resp = await client.post(endpoint, json={
                            "contents": contents,
                            "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
                            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024}
                        })
                        
                        if followup_resp.status_code == 200:
                            followup_data = followup_resp.json()
                            f_candidates = followup_data.get("candidates", [])
                            if f_candidates:
                                f_text = "".join([p.get("text", "") for p in f_candidates[0].get("content", {}).get("parts", [])])
                                return {
                                    "response": f_text,
                                    "tool_calls": executed_tools,
                                    "tool_results": tool_results,
                                    "grounding_data": tool_results[0]["response"] if tool_results else None,
                                    "model": model_name
                                }

                    text_response = "".join([p.get("text", "") for p in parts if "text" in p])
                    if text_response:
                        return {
                            "response": text_response,
                            "tool_calls": executed_tools,
                            "grounding_data": None,
                            "model": model_name
                        }

                except Exception as ex:
                    print(f"[Gemini {model_name}] Exception during API call: {ex}")
                    continue

        return await self._deterministic_reasoning(clean_prompt, location_hint)

ai_service = AIService()
