import os
import requests
import io
import pandas as pd
import numpy as np

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
APISPORTS_KEY = os.getenv("APISPORTS_KEY", "")
ODDS_BASE = "https://api.the-odds-api.com/v4"
APISPORTS_BASE = "https://v3.football.api-sports.io"

LEAGUE_IDS = {
    "Premier League": 39, "La Liga": 140, "Serie A": 135,
    "Bundesliga": 78, "Ligue 1": 61, "Champions League": 2, "Liga Argentina": 128,
}
ODDS_SPORT_KEYS = {
    "Premier League": "soccer_epl",
    "La Liga": "soccer_spain_la_liga",
    "Serie A": "soccer_italy_serie_a",
    "Bundesliga": "soccer_germany_bundesliga",
    "Champions League": "soccer_uefa_champs_league",
    "Liga Argentina": "soccer_argentina_primera_division",
    "Brazil Serie A": "soccer_brazil_campeonato",
    "Chile Primera": "soccer_chile_campeonato",
}
TEAMS_DB = {}

def get_sports():
    r = requests.get(f"{ODDS_BASE}/sports", params={"apiKey": ODDS_API_KEY}, timeout=10)
    r.raise_for_status()
    return r.json()

def get_odds(sport="soccer_epl", regions="eu", markets="h2h", odds_format="decimal"):
    r = requests.get(f"{ODDS_BASE}/sports/{sport}/odds", params={
        "apiKey": ODDS_API_KEY, "regions": regions,
        "markets": markets, "oddsFormat": odds_format,
    }, timeout=15)
    r.raise_for_status()
    return r.json()

def get_remaining_requests():
    r = requests.get(f"{ODDS_BASE}/sports", params={"apiKey": ODDS_API_KEY}, timeout=10)
    return {
        "remaining": r.headers.get("x-requests-remaining", "?"),
        "used": r.headers.get("x-requests-used", "?"),
    }

def _h():
    return {"x-apisports-key": APISPORTS_KEY}

def get_fixtures_today():
    from datetime import date
    r = requests.get(f"{APISPORTS_BASE}/fixtures", headers=_h(),
                     params={"date": date.today().isoformat()}, timeout=15)
    r.raise_for_status()
    return r.json().get("response", [])

def get_fixtures_league(league_id, season=2025):
    r = requests.get(f"{APISPORTS_BASE}/fixtures", headers=_h(),
                     params={"league": league_id, "season": season, "next": 10}, timeout=15)
    r.raise_for_status()
    return r.json().get("response", [])

def get_team_stats(team_id, league_id, season=2025):
    r = requests.get(f"{APISPORTS_BASE}/teams/statistics", headers=_h(),
                     params={"team": team_id, "league": league_id, "season": season}, timeout=15)
    r.raise_for_status()
    return r.json().get("response", {})

class DataFetcher:
    def get_historical_matches(self, n=400):
        urls = [
            "https://www.football-data.co.uk/mmz4281/2324/E0.csv",
            "https://www.football-data.co.uk/mmz4281/2324/SP1.csv",
            "https://www.football-data.co.uk/mmz4281/2324/I1.csv",
            "https://www.football-data.co.uk/mmz4281/2324/D1.csv",
        ]
        dfs = []
        for url in urls:
            try:
                r = requests.get(url, timeout=10)
                df = pd.read_csv(io.StringIO(r.content.decode("utf-8", errors="ignore")))
                df = df.dropna(subset=["HomeTeam", "AwayTeam", "FTHG", "FTAG"])
                df["league"] = url.split("/")[-1].replace(".csv", "")
                dfs.append(df)
            except:
                pass
        if not dfs:
            return pd.DataFrame()
        c = pd.concat(dfs, ignore_index=True)
        return c.rename(columns={
            "HomeTeam": "home_team", "AwayTeam": "away_team",
            "FTHG": "home_goals", "FTAG": "away_goals", "FTR": "result"
        }).tail(n)

    def get_upcoming_matches(self):
        """
        Obtiene próximos partidos. Estrategia en cascada:
          1. Partidos de hoy via API-Sports
          2. Próximos 10 partidos por cada liga configurada (next=10)
          3. Fallback simulado si la API falla o no hay key
        """
        matches = []

        # ── Intentar API-Sports ────────────────────────────────────────────
        if APISPORTS_KEY:
            try:
                # 1. Partidos de hoy
                for f in get_fixtures_today()[:20]:
                    m = self._fixture_to_match(f)
                    if m:
                        matches.append(m)
            except Exception as e:
                import logging; logging.getLogger(__name__).warning(f"[Fetcher] fixtures_today error: {e}")

            # 2. Si no hay partidos hoy, buscar próximos por liga
            if not matches:
                for league_name, league_id in LEAGUE_IDS.items():
                    try:
                        fixtures = get_fixtures_league(league_id, season=2025)
                        for f in fixtures[:5]:
                            m = self._fixture_to_match(f)
                            if m and m not in matches:
                                matches.append(m)
                    except Exception as e:
                        import logging; logging.getLogger(__name__).warning(
                            f"[Fetcher] fixtures_league {league_name} error: {e}"
                        )

        # ── Fallback simulado si no hay API key o no hay partidos ──────────
        if not matches:
            import logging
            logging.getLogger(__name__).warning(
                "[Fetcher] Sin partidos de API-Sports, usando partidos simulados"
            )
            matches = self._get_simulated_matches()

        return matches

    def _fixture_to_match(self, f: dict) -> dict | None:
        """Convierte un fixture de API-Sports a formato interno."""
        try:
            home = f["teams"]["home"]["name"]
            away = f["teams"]["away"]["name"]
            return {
                "home_team":  home,
                "away_team":  away,
                "match_id":   f"{home}_{away}",
                "league":     f["league"]["name"],
                "kickoff":    f["fixture"]["date"],
                "home_id":    f["teams"]["home"]["id"],
                "away_id":    f["teams"]["away"]["id"],
                "league_id":  f["league"]["id"],
            }
        except Exception:
            return None

    def _get_simulated_matches(self) -> list[dict]:
        """
        Genera partidos simulados representativos cuando no hay API disponible.
        Cubre las principales ligas para que el sistema siempre tenga algo que analizar.
        """
        from datetime import datetime, timedelta
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        simulated = [
            # Premier League
            ("Arsenal",        "Chelsea",          "Premier League"),
            ("Manchester City", "Liverpool",        "Premier League"),
            ("Tottenham",      "Manchester United", "Premier League"),
            # La Liga
            ("Real Madrid",    "Barcelona",         "La Liga"),
            ("Atletico Madrid","Sevilla",            "La Liga"),
            # Serie A
            ("Juventus",       "Inter",             "Serie A"),
            ("AC Milan",       "Napoli",            "Serie A"),
            # Bundesliga
            ("Bayern Munich",  "Borussia Dortmund", "Bundesliga"),
            ("RB Leipzig",     "Bayer Leverkusen",  "Bundesliga"),
            # Ligue 1
            ("Paris Saint-Germain", "Marseille",    "Ligue 1"),
            # Liga Argentina
            ("Boca Juniors",   "River Plate",       "Liga Argentina"),
            ("Racing Club",    "Independiente",     "Liga Argentina"),
        ]

        return [
            {
                "home_team": home,
                "away_team": away,
                "match_id":  f"{home}_{away}",
                "league":    league,
                "kickoff":   tomorrow,
                "simulated": True,
            }
            for home, away, league in simulated
        ]

    def get_simulated_odds(self, match):
        np.random.seed(hash(str(match)) % 2**32)
        return {
            "odd_home":    round(1.8 + np.random.uniform(-0.3, 0.3), 2),
            "odd_draw":    round(3.4 + np.random.uniform(-0.4, 0.4), 2),
            "odd_away":    round(4.2 + np.random.uniform(-0.5, 0.5), 2),
            "odd_over25":  round(1.9 + np.random.uniform(-0.2, 0.2), 2),
            "odd_under25": round(1.9 + np.random.uniform(-0.2, 0.2), 2),
            "bookmaker":   "simulated",
        }

    def get_closing_odds(self, match, opening_odds: dict, prediction: dict) -> dict:
        """
        Simula las cuotas de cierre (closing line) de forma realista.
        
        El mercado se "afina" hacia el final: las cuotas de cierre reflejan
        mejor la probabilidad real que las de apertura. Simulamos esto
        ajustando las cuotas de apertura hacia la probabilidad del modelo
        con un pequeño ruido residual.
        
        CLV positivo = apostaste antes de que el mercado se moviera a tu favor.
        """
        # Seed distinto al de apertura para simular movimiento de mercado
        np.random.seed((hash(str(match)) + 1) % 2**32)

        def _close(odd_open: float, p_model: float) -> float:
            """
            Cuota de cierre = promedio ponderado entre cuota apertura
            y cuota "justa" del modelo, con ruido pequeño.
            - 40% peso al modelo (mercado se mueve hacia la prob real)
            - 60% peso a la cuota apertura (inercia del mercado)
            - ±2% ruido residual
            """
            fair_odd = round(1 / p_model, 2) if p_model > 0 else odd_open
            # Margin bookmaker ~5% sobre la cuota justa
            fair_odd_with_margin = fair_odd * 0.95
            closing = 0.6 * odd_open + 0.4 * fair_odd_with_margin
            noise = np.random.uniform(-0.02, 0.02) * closing
            return round(max(closing + noise, 1.01), 2)

        return {
            "odd_home":    _close(opening_odds["odd_home"],    prediction.get("p_home",   0.35)),
            "odd_draw":    _close(opening_odds["odd_draw"],    prediction.get("p_draw",   0.28)),
            "odd_away":    _close(opening_odds["odd_away"],    prediction.get("p_away",   0.37)),
            "odd_over25":  _close(opening_odds["odd_over25"],  prediction.get("p_over25", 0.52)),
            "odd_under25": _close(opening_odds["odd_under25"], prediction.get("p_under25",0.48)),
            "bookmaker":   "closing",
        }
