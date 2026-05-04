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

def get_fixtures_league(league_id, season=2024):
    r = requests.get(f"{APISPORTS_BASE}/fixtures", headers=_h(),
                     params={"league": league_id, "season": season, "next": 10}, timeout=15)
    r.raise_for_status()
    return r.json().get("response", [])

def get_team_stats(team_id, league_id, season=2024):
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
        try:
            matches = []
            for f in get_fixtures_today()[:20]:
                home = f["teams"]["home"]["name"]
                away = f["teams"]["away"]["name"]
                matches.append({
                    "home_team": home,
                    "away_team": away,
                    "match_id": home + "_" + away,
                    "league": f["league"]["name"],
                    "date": f["fixture"]["date"],
                    "home_id": f["teams"]["home"]["id"],
                    "away_id": f["teams"]["away"]["id"],
                    "league_id": f["league"]["id"],
                })
            return matches
        except:
            return []

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
