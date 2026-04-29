"""
Data Fetcher — Capa de Ingesta
================================
Estrategia FREE-FIRST:
  1. api-football.com  → 100 requests/día gratis (Free tier)
  2. The Odds API      → 500 requests/mes gratis
  3. Fallback          → genera datos históricos sintéticos realistas
     para que puedas probar el modelo HOY sin ninguna API key.

Cuando valides que el modelo funciona, pagás las APIs.
"""

import json
import math
import random
import hashlib
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# ── Configuración ──────────────────────────────────────────────────────────────
RAPIDAPI_KEY   = ""   # Completar cuando tengas key (gratis en rapidapi.com)
ODDS_API_KEY   = ""   # Completar cuando tengas key (free en the-odds-api.com)
DATA_DIR       = Path(__file__).parent / "cache"
DATA_DIR.mkdir(exist_ok=True)

# Equipos reales con estadísticas aproximadas (media goles/partido histórica)
TEAMS_DB = {
    # Liga Argentina
    "Boca Juniors":      {"att": 1.55, "def": 0.95, "elo": 1720, "league": "Liga Argentina"},
    "River Plate":       {"att": 1.70, "def": 0.85, "elo": 1755, "league": "Liga Argentina"},
    "Racing Club":       {"att": 1.40, "def": 1.05, "elo": 1680, "league": "Liga Argentina"},
    "Independiente":     {"att": 1.20, "def": 1.15, "elo": 1630, "league": "Liga Argentina"},
    "San Lorenzo":       {"att": 1.25, "def": 1.10, "elo": 1645, "league": "Liga Argentina"},
    "Estudiantes":       {"att": 1.15, "def": 1.00, "elo": 1620, "league": "Liga Argentina"},
    # Premier League
    "Manchester City":   {"att": 2.30, "def": 0.70, "elo": 1950, "league": "Premier League"},
    "Arsenal":           {"att": 2.10, "def": 0.80, "elo": 1890, "league": "Premier League"},
    "Liverpool":         {"att": 2.20, "def": 0.85, "elo": 1920, "league": "Premier League"},
    "Chelsea":           {"att": 1.75, "def": 1.00, "elo": 1830, "league": "Premier League"},
    "Tottenham":         {"att": 1.80, "def": 1.10, "elo": 1790, "league": "Premier League"},
    "Newcastle":         {"att": 1.60, "def": 1.00, "elo": 1760, "league": "Premier League"},
    # La Liga
    "Real Madrid":       {"att": 2.40, "def": 0.75, "elo": 1970, "league": "La Liga"},
    "Barcelona":         {"att": 2.25, "def": 0.80, "elo": 1940, "league": "La Liga"},
    "Atletico Madrid":   {"att": 1.65, "def": 0.70, "elo": 1880, "league": "La Liga"},
    "Athletic Bilbao":   {"att": 1.40, "def": 1.00, "elo": 1720, "league": "La Liga"},
    "Real Sociedad":     {"att": 1.50, "def": 1.05, "elo": 1740, "league": "La Liga"},
    "Villarreal":        {"att": 1.55, "def": 1.10, "elo": 1730, "league": "La Liga"},
}


class DataFetcher:

    def get_historical_matches(self, n_matches: int = 500) -> pd.DataFrame:
        """
        Genera historial sintético realista basado en las estadísticas reales
        de cada equipo. Los goles se sampean de distribuciones Poisson usando
        los parámetros att/def reales → el modelo se va a entrenar con datos
        estadísticamente coherentes.
        """
        cache_file = DATA_DIR / f"historical_{n_matches}.parquet"
        if cache_file.exists():
            print(f"[Cache] Cargando {n_matches} partidos históricos desde disco...")
            return pd.read_parquet(cache_file)

        print(f"[Generando] {n_matches} partidos históricos sintéticos...")
        rows = []
        teams = list(TEAMS_DB.keys())
        leagues = list({v["league"] for v in TEAMS_DB.values()})

        # Media global de goles (ajuste de liga)
        league_avg = {"Liga Argentina": 1.25, "Premier League": 1.52, "La Liga": 1.48}

        for i in range(n_matches):
            # Elegir dos equipos de la misma liga
            league = random.choice(leagues)
            lg_teams = [t for t, v in TEAMS_DB.items() if v["league"] == league]
            if len(lg_teams) < 2:
                continue
            home_name, away_name = random.sample(lg_teams, 2)
            home = TEAMS_DB[home_name]
            away = TEAMS_DB[away_name]
            avg = league_avg.get(league, 1.35)

            # Ventaja de local (+15% ataque, -10% defensa rivales)
            lambda_home = (home["att"] / avg) * (away["def"] / avg) * avg * 1.15
            lambda_away = (away["att"] / avg) * (home["def"] / avg) * avg * 0.90

            home_goals = np.random.poisson(lambda_home)
            away_goals = np.random.poisson(lambda_away)

            # Fecha aleatoria en los últimos 3 años
            days_back = random.randint(1, 1095)
            match_date = datetime.now() - timedelta(days=days_back)

            rows.append({
                "match_id":    f"SYN_{i:05d}",
                "date":        match_date.strftime("%Y-%m-%d"),
                "league":      league,
                "home_team":   home_name,
                "away_team":   away_name,
                "home_goals":  home_goals,
                "away_goals":  away_goals,
                "lambda_home": round(lambda_home, 3),
                "lambda_away": round(lambda_away, 3),
                "home_elo":    home["elo"],
                "away_elo":    away["elo"],
                "result":      "H" if home_goals > away_goals else ("D" if home_goals == away_goals else "A"),
                "total_goals": home_goals + away_goals,
                "over25":      int(home_goals + away_goals > 2),
            })

        df = pd.DataFrame(rows)
        df.to_parquet(cache_file)
        print(f"[OK] {len(df)} partidos generados y cacheados.")
        return df

    def get_upcoming_matches(self) -> list[dict]:
        """
        Genera partidos 'próximos' para predecir HOY.
        Cuando tengas API key, reemplaza este método con la llamada real.
        """
        upcoming = []
        leagues = list({v["league"] for v in TEAMS_DB.values()})
        for league in leagues:
            lg_teams = [t for t, v in TEAMS_DB.items() if v["league"] == league]
            pairs = []
            used = set()
            for t in lg_teams:
                if t not in used:
                    others = [x for x in lg_teams if x != t and x not in used]
                    if others:
                        opp = random.choice(others)
                        pairs.append((t, opp))
                        used.update([t, opp])
            for home, away in pairs:
                kickoff = datetime.now() + timedelta(hours=random.randint(2, 72))
                upcoming.append({
                    "match_id":  f"LIVE_{hashlib.md5(f'{home}{away}'.encode()).hexdigest()[:8]}",
                    "league":    league,
                    "home_team": home,
                    "away_team": away,
                    "kickoff":   kickoff.strftime("%Y-%m-%d %H:%M"),
                })
        return upcoming

    def get_simulated_odds(self, match: dict) -> dict:
        """
        Simula cuotas de bookmakers con un margen (vig) de ~5-8%.
        Las cuotas están levemente sesgadas respecto a las probabilidades
        reales → aquí es donde el modelo debería encontrar value.
        """
        home = TEAMS_DB.get(match["home_team"], {"elo": 1700})
        away = TEAMS_DB.get(match["away_team"], {"elo": 1700})

        # Probabilidad "verdadera" según ELO
        elo_diff = home["elo"] - away["elo"]
        p_home_true = 1 / (1 + 10 ** (-elo_diff / 400))
        p_away_true = 1 - p_home_true
        p_draw_true = 0.26 * (1 - abs(p_home_true - p_away_true))
        total = p_home_true + p_draw_true + p_away_true
        p_home_true /= total
        p_draw_true /= total
        p_away_true /= total

        # El bookmaker agrega vig (margen) + algo de ruido → aquí nace el value
        vig = random.uniform(1.05, 1.10)
        noise = lambda: random.gauss(1.0, 0.04)

        p_h_bk = p_home_true * noise() * vig
        p_d_bk = p_draw_true * noise() * vig
        p_a_bk = p_away_true * noise() * vig

        return {
            "bookmaker": random.choice(["Bet365", "William Hill", "Betfair", "Unibet"]),
            "odd_home":  round(1 / p_h_bk, 2),
            "odd_draw":  round(1 / p_d_bk, 2),
            "odd_away":  round(1 / p_a_bk, 2),
            "odd_over25":  round(random.uniform(1.75, 2.10), 2),
            "odd_under25": round(random.uniform(1.70, 2.05), 2),
        }

    # ── Método para cuando tengas API Key ──────────────────────────────────────
    def fetch_real_odds(self, sport: str = "soccer_argentina_primera_division") -> list:
        """
        The Odds API — Free tier: 500 requests/mes
        https://the-odds-api.com  → registrarse gratis, sin tarjeta
        """
        if not ODDS_API_KEY:
            print("[INFO] ODDS_API_KEY no configurada. Usando cuotas simuladas.")
            return []
        url = "https://api.the-odds-api.com/v4/sports/{}/odds/".format(sport)
        resp = requests.get(url, params={
            "apiKey": ODDS_API_KEY,
            "regions": "eu",
            "markets": "h2h,totals",
            "oddsFormat": "decimal",
        })
        if resp.status_code == 200:
            print(f"[API] Cuotas reales obtenidas. Requests restantes: {resp.headers.get('x-requests-remaining')}")
            return resp.json()
        print(f"[Error] Odds API: {resp.status_code} - {resp.text}")
        return []
