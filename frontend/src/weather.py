"""
weather.py — Módulo de clima para ValueBet Analyzer
=====================================================
- Obtiene clima actual via OpenWeatherMap API (free tier)
- Mapea ciudades/ligas a coordenadas
- Calcula factores de ajuste sobre lambda (goles esperados)

Lógica de ajuste:
  - Lluvia intensa  → -8% goles (juego más lento, menos precisión)
  - Viento fuerte   → -5% goles (afecta tiros y centros)
  - Frío extremo    → -3% goles (jugadores menos ágiles)
  - Calor extremo   → -4% goles (fatiga más rápida)
  - Nieve           → -12% goles (mayor impacto)
  - Condiciones normales → factor 1.0 (sin ajuste)
"""

import os
import requests
import logging
from functools import lru_cache
from datetime import datetime

logger = logging.getLogger(__name__)

OPENWEATHER_KEY  = os.getenv("OPENWEATHER_KEY", "")
OPENWEATHER_BASE = "https://api.openweathermap.org/data/2.5"

# ── Coordenadas aproximadas por liga ─────────────────────────────────────────
LEAGUE_COORDS = {
    "Premier League":        (51.5074, -0.1278),   # Londres
    "La Liga":               (40.4168, -3.7038),   # Madrid
    "Serie A":               (41.9028, 12.4964),   # Roma
    "Bundesliga":            (48.1351, 11.5820),   # Munich
    "Ligue 1":               (48.8566,  2.3522),   # París
    "Champions League":      (51.5074, -0.1278),   # Londres (variable)
    "Liga Argentina":        (-34.6037,-58.3816),  # Buenos Aires
    "MLS":                   (40.7128, -74.0060),  # Nueva York
    "Major League Soccer":   (40.7128, -74.0060),
    "MLS Next Pro":          (40.7128, -74.0060),
    "Liga MX":               (19.4326, -99.1332),  # Ciudad de México
    "Primera Division":      (14.0723, -87.1921),  # Tegucigalpa (Honduras)
    "Copa Colombia":         ( 4.7110, -74.0721),  # Bogotá
    "Primera B":             ( 4.7110, -74.0721),
    "USL League Two":        (37.7749,-122.4194),  # San Francisco
    "Canadian Premier League":(43.6532,-79.3832),  # Toronto
    "UEFA U19 Championship": (51.5074, -0.1278),
    "Victoria NPL":          (-37.8136, 144.9631), # Melbourne
}

DEFAULT_COORDS = (0.0, 0.0)  # fallback ecuatorial (clima neutro)


@lru_cache(maxsize=64)
def get_weather(lat: float, lon: float) -> dict:
    """
    Obtiene clima actual para las coordenadas dadas.
    Cachea resultados para no gastar requests.
    Retorna dict con: temp_c, wind_kph, rain_mm, snow_mm, condition, icon
    """
    if not OPENWEATHER_KEY:
        return _neutral_weather("Sin API key")

    try:
        r = requests.get(
            f"{OPENWEATHER_BASE}/weather",
            params={
                "lat": lat, "lon": lon,
                "appid": OPENWEATHER_KEY,
                "units": "metric",
                "lang": "es"
            },
            timeout=8
        )
        r.raise_for_status()
        d = r.json()

        temp_c   = d["main"]["temp"]
        wind_kph = d["wind"]["speed"] * 3.6  # m/s → km/h
        rain_mm  = d.get("rain", {}).get("1h", 0)
        snow_mm  = d.get("snow", {}).get("1h", 0)
        condition = d["weather"][0]["description"].capitalize()
        icon_code = d["weather"][0]["icon"]
        icon_url  = f"https://openweathermap.org/img/wn/{icon_code}.png"

        return {
            "temp_c":    round(temp_c, 1),
            "wind_kph":  round(wind_kph, 1),
            "rain_mm":   round(rain_mm, 1),
            "snow_mm":   round(snow_mm, 1),
            "condition": condition,
            "icon":      icon_url,
            "available": True,
        }
    except Exception as e:
        logger.warning(f"[Weather] Error obteniendo clima ({lat},{lon}): {e}")
        return _neutral_weather(str(e))


def _neutral_weather(reason: str = "") -> dict:
    return {
        "temp_c": 20, "wind_kph": 10, "rain_mm": 0, "snow_mm": 0,
        "condition": "Datos no disponibles", "icon": "",
        "available": False, "reason": reason,
    }


def get_weather_for_league(league: str) -> dict:
    """Obtiene clima según la liga del partido."""
    coords = LEAGUE_COORDS.get(league, DEFAULT_COORDS)
    return get_weather(coords[0], coords[1])


def weather_lambda_factor(weather: dict) -> float:
    """
    Calcula factor multiplicador sobre lambda (goles esperados).
    Factor < 1.0 = menos goles esperados por condiciones adversas.
    """
    if not weather.get("available", False):
        return 1.0

    factor = 1.0
    rain   = weather.get("rain_mm", 0)
    snow   = weather.get("snow_mm", 0)
    wind   = weather.get("wind_kph", 0)
    temp   = weather.get("temp_c", 20)

    # Lluvia
    if rain >= 5:
        factor *= 0.92   # lluvia intensa
    elif rain >= 2:
        factor *= 0.96   # lluvia moderada

    # Nieve
    if snow >= 1:
        factor *= 0.88

    # Viento
    if wind >= 50:
        factor *= 0.93
    elif wind >= 30:
        factor *= 0.97

    # Temperatura extrema
    if temp <= 0:
        factor *= 0.97
    elif temp >= 35:
        factor *= 0.96

    return round(factor, 4)


def weather_summary(weather: dict) -> str:
    """Texto corto para mostrar en UI."""
    if not weather.get("available"):
        return ""
    parts = [weather["condition"]]
    if weather["temp_c"] is not None:
        parts.append(f"{weather['temp_c']}°C")
    if weather["wind_kph"] > 20:
        parts.append(f"💨{weather['wind_kph']}km/h")
    if weather["rain_mm"] > 0:
        parts.append(f"🌧{weather['rain_mm']}mm")
    if weather["snow_mm"] > 0:
        parts.append(f"❄{weather['snow_mm']}mm")
    return " · ".join(parts)


if __name__ == "__main__":
    # Test rápido
    w = get_weather(-34.6037, -58.3816)
    print("Buenos Aires:", w)
    print("Factor lambda:", weather_lambda_factor(w))
    print("Resumen:", weather_summary(w))
