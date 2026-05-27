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
    # Ligas disponibles en plan gratuito de The Odds API
    "Premier League":        "soccer_epl",
    "La Liga":               "soccer_spain_la_liga",
    "Serie A":               "soccer_italy_serie_a",
    "Bundesliga":            "soccer_germany_bundesliga",
    "Champions League":      "soccer_uefa_champs_league",
    "Liga Argentina":        "soccer_argentina_primera_division",
    "Brazil Serie A":        "soccer_brazil_campeonato",
    "Chile Primera":         "soccer_chile_campeonato",
    # Ligas confirmadas activas en plan gratuito
    "Copa Libertadores":     "soccer_conmebol_copa_libertadores",
    "Copa Sudamericana":     "soccer_conmebol_copa_sudamericana",
    "Ligue 1":               "soccer_france_ligue_one",
    "Belgium First Div":     "soccer_belgium_first_div",
    "Serie B":               "soccer_italy_serie_b",
    "J League":              "soccer_japan_j_league",
    "Super League China":    "soccer_china_superleague",
    "Champions League":      "soccer_uefa_champs_league",
    "Europa League":         "soccer_uefa_europa_league",
    "Conference League":     "soccer_uefa_europa_conference_league",
    "Norway Eliteserien":    "soccer_norway_eliteserien",
    "Sweden Allsvenskan":    "soccer_sweden_allsvenskan",
    "Finland Veikkausliiga": "soccer_finland_veikkausliiga",
    "Ireland Premier":       "soccer_league_of_ireland",
}
TEAMS_DB = {}

# Bookmakers EU disponibles en Argentina con sus URLs directas
BOOKMAKER_URLS = {
    "bet365":       "https://www.bet365.com",
    "betway":       "https://betway.com.ar",
    "1xbet":        "https://1xbet.com",
    "unibet":       "https://www.unibet.com",
    "pinnacle":     "https://www.pinnacle.com",
    "marathonbet":  "https://www.marathonbet.com",
    "betsafe":      "https://www.betsafe.com",
    "betclic":      "https://www.betclic.com",
    "williamhill":  "https://www.williamhill.com",
    "betfair":      "https://www.betfair.com",
    "draftkings":   "https://www.draftkings.com",
    "fanduel":      "https://www.fanduel.com",
    "betsson":      "https://www.betsson.com",
    "nordicbet":    "https://www.nordicbet.com",
    "coolbet":      "https://www.coolbet.com",
    "casumo":       "https://www.casumo.com",
    "suprabets":    "https://suprabets.com",
    "sport888":     "https://www.888sport.com",
}

BOOKMAKER_DISPLAY = {
    "bet365":      "Bet365",
    "betway":      "Betway",
    "1xbet":       "1xBet",
    "unibet":      "Unibet",
    "pinnacle":    "Pinnacle",
    "marathonbet": "MarathonBet",
    "betsafe":     "Betsafe",
    "betclic":     "Betclic",
    "williamhill": "William Hill",
    "betfair":     "Betfair",
    "betsson":     "Betsson",
    "sport888":    "888sport",
}

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
            # Copa Libertadores (cubierta por The Odds API)
            ("Boca Juniors",   "Flamengo",          "Copa Libertadores"),
            ("River Plate",    "Palmeiras",         "Copa Libertadores"),
            # Copa Sudamericana (cubierta por The Odds API)
            ("Independiente",  "Santos",            "Copa Sudamericana"),
            ("Racing Club",    "Nacional",          "Copa Sudamericana"),
            # Brazil Serie A (cubierta por The Odds API)
            ("Flamengo",       "Palmeiras",         "Brazil Serie A"),
            ("Corinthians",    "Sao Paulo",         "Brazil Serie A"),
            # Chile (cubierta por The Odds API)
            ("Colo-Colo",      "Universidad de Chile", "Chile Primera"),
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

    def get_real_odds_for_match(self, match: dict, sport_key: str = None) -> list[dict]:
        """
        Busca cuotas reales de The Odds API para un partido específico.
        Retorna lista de bookmakers con sus cuotas, ordenados por mejor cuota.
        """
        if not ODDS_API_KEY:
            return []
        try:
            league = match.get("league", "")
            sk = sport_key or ODDS_SPORT_KEYS.get(league)
            if not sk:
                return []

            r = requests.get(
                f"{ODDS_BASE}/sports/{sk}/odds",
                params={
                    "apiKey": ODDS_API_KEY,
                    "regions": "eu",
                    "markets": "h2h,totals",
                    "oddsFormat": "decimal",
                },
                timeout=15,
            )
            if r.status_code != 200:
                return []

            home = match.get("home_team", "").lower()
            away = match.get("away_team", "").lower()
            events = r.json()
            results = []

            for event in events:
                h = event.get("home_team", "").lower()
                a = event.get("away_team", "").lower()
                # Match fuzzy por nombre (primeras 5 letras)
                if home[:5] not in h and away[:5] not in a:
                    continue
                for bk in event.get("bookmakers", []):
                    bk_key = bk.get("key", "")
                    bk_name = BOOKMAKER_DISPLAY.get(bk_key, bk.get("title", bk_key))
                    bk_url  = BOOKMAKER_URLS.get(bk_key, "https://www.google.com/search?q=" + bk_name)
                    odds_entry = {
                        "bookmaker_key":  bk_key,
                        "bookmaker_name": bk_name,
                        "bookmaker_url":  bk_url,
                        "odd_home":    None,
                        "odd_draw":    None,
                        "odd_away":    None,
                        "odd_over25":  None,
                        "odd_under25": None,
                    }
                    for market in bk.get("markets", []):
                        key = market.get("key")
                        outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
                        if key == "h2h":
                            odds_entry["odd_home"] = outcomes.get(event.get("home_team"))
                            odds_entry["odd_draw"] = outcomes.get("Draw")
                            odds_entry["odd_away"] = outcomes.get(event.get("away_team"))
                        elif key == "totals":
                            for o in market.get("outcomes", []):
                                if o.get("point") == 2.5:
                                    if o["name"] == "Over":
                                        odds_entry["odd_over25"] = o["price"]
                                    elif o["name"] == "Under":
                                        odds_entry["odd_under25"] = o["price"]
                    results.append(odds_entry)
                break  # Solo el primer evento que matchee

            return results
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[OddsAPI] Error: {e}")
            return []

    def get_best_bookmaker(self, match: dict, market: str = "home") -> dict:
        """
        Devuelve el bookmaker con la mejor cuota para un mercado específico.
        market: 'home', 'draw', 'away', 'over25', 'under25'
        """
        bookmakers = self.get_real_odds_for_match(match)
        if not bookmakers:
            return {}
        odd_key = f"odd_{market}"
        best = max(
            (b for b in bookmakers if b.get(odd_key) is not None),
            key=lambda b: b.get(odd_key, 0),
            default={}
        )
        return best

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
