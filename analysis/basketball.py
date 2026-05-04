import pandas as pd
import numpy as np
import requests
import io

# Datos gratuitos: basketball-reference via Sports-Reference CSV exports
# Usamos datos simulados realistas basados en estadísticas NBA/FIBA históricas
# cuando no hay API disponible gratuitamente

LEAGUES = {
    "NBA": {"pace": 100.0, "avg_points": 114.0, "std_points": 12.0},
    "Euroliga": {"pace": 88.0, "avg_points": 80.0, "std_points": 9.0},
    "FIBA": {"pace": 85.0, "avg_points": 77.0, "std_points": 10.0},
}

def fetch_nba_data():
    """Intenta obtener datos reales de baloncesto de fuentes gratuitas."""
    try:
        url = "https://raw.githubusercontent.com/fivethirtyeight/data/master/nba-raptor/modern_RAPTOR_by_team.csv"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return pd.read_csv(io.StringIO(resp.text))
    except:
        pass
    return None

def team_strength(off_rating, def_rating, league_avg_off=114, league_avg_def=114):
    """Convierte ratings ofensivos/defensivos a fuerza relativa."""
    off_factor = off_rating / league_avg_off
    def_factor = league_avg_def / def_rating
    return (off_factor + def_factor) / 2

def predict_game(home_off, home_def, away_off, away_def, league="NBA", home_advantage=3.5):
    cfg = LEAGUES.get(league, LEAGUES["NBA"])
    avg_pts = cfg["avg_points"]
    pace_factor = cfg["pace"] / 100.0
    home_exp = ((home_off / 100) * (away_def / 100) * avg_pts * pace_factor) + home_advantage
    away_exp = (away_off / 100) * (home_def / 100) * avg_pts * pace_factor
    total_exp = home_exp + away_exp
    diff_exp = home_exp - away_exp
    p_home = 1 / (1 + np.exp(-diff_exp / 10))
    return {
        "home_points": round(home_exp, 1),
        "away_points": round(away_exp, 1),
        "total_points": round(total_exp, 1),
        "point_diff": round(diff_exp, 1),
        "p_home_win": round(p_home, 3),
        "p_away_win": round(1 - p_home, 3),
    }

# Equipos simulados con ratings realistas
NBA_TEAMS = [
    {"name": "Boston Celtics",      "off": 120, "def": 108, "league": "NBA"},
    {"name": "Oklahoma City Thunder","off": 118, "def": 109, "league": "NBA"},
    {"name": "Denver Nuggets",       "off": 117, "def": 112, "league": "NBA"},
    {"name": "Cleveland Cavaliers",  "off": 116, "def": 107, "league": "NBA"},
    {"name": "Minnesota Timberwolves","off": 113,"def": 106, "league": "NBA"},
    {"name": "New York Knicks",      "off": 112, "def": 110, "league": "NBA"},
    {"name": "LA Lakers",            "off": 115, "def": 113, "league": "NBA"},
    {"name": "Golden State Warriors","off": 116, "def": 114, "league": "NBA"},
    {"name": "Dallas Mavericks",     "off": 119, "def": 115, "league": "NBA"},
    {"name": "Phoenix Suns",         "off": 114, "def": 116, "league": "NBA"},
]

EURO_TEAMS = [
    {"name": "Real Madrid",     "off": 88, "def": 74, "league": "Euroliga"},
    {"name": "Fenerbahce",      "off": 86, "def": 76, "league": "Euroliga"},
    {"name": "Olympiacos",      "off": 85, "def": 75, "league": "Euroliga"},
    {"name": "Panathinaikos",   "off": 84, "def": 77, "league": "Euroliga"},
    {"name": "Bayern Munich",   "off": 83, "def": 76, "league": "Euroliga"},
    {"name": "Barcelona",       "off": 87, "def": 75, "league": "Euroliga"},
]

def analyze_basketball(league="NBA", min_edge=0.05):
    teams = NBA_TEAMS if league == "NBA" else EURO_TEAMS
    cfg = LEAGUES.get(league, LEAGUES["NBA"])
    alerts = []
    matchups = []

    np.random.seed(42)
    n = len(teams)
    used = set()
    for i in range(n):
        for j in range(i+1, n):
            if len(matchups) >= 8:
                break
            matchups.append((teams[i], teams[j]))

    for home, away in matchups[:8]:
        pred = predict_game(
            home["off"], home["def"],
            away["off"], away["def"],
            league=league
        )
        total_line = pred["total_points"]
        spread_line = -pred["point_diff"]
        std = cfg["std_points"]

        from scipy import stats
        p_over = 1 - stats.norm.cdf(total_line, loc=pred["total_points"], scale=std)
        p_under = 1 - p_over

        for market, p_model, line in [
            ("Ganador partido", pred["p_home_win"], None),
            ("Ganador partido", pred["p_away_win"], None),
            (f"Over {total_line:.0f} pts", max(p_over, 0.45), total_line),
            (f"Under {total_line:.0f} pts", max(p_under, 0.45), total_line),
            (f"Handicap {home['name']} {spread_line:+.1f}", pred["p_home_win"], spread_line),
        ]:
            odd = round(1 / p_model * (1 + np.random.uniform(0.02, 0.08)), 2)
            implied = 1 / odd
            edge = p_model - implied
            if edge < min_edge:
                continue
            kelly = max(0, (p_model * odd - 1) / (odd - 1)) * 0.25
            is_home = "Ganador" in market and p_model == pred["p_home_win"]
            team = home["name"] if is_home or "Handicap" in market else away["name"]
            alerts.append({
                "sport": "basketball",
                "match": f"{home['name']} vs {away['name']}",
                "team": team,
                "league": league,
                "market": market,
                "model_prob": round(p_model*100, 1),
                "implied_prob": round(implied*100, 1),
                "edge_pct": round(edge*100, 1),
                "odd": odd,
                "kelly_frac": round(kelly, 3),
                "confidence": "ALTA" if edge > 0.10 else "MEDIA",
                "home_pts_est": pred["home_points"],
                "away_pts_est": pred["away_points"],
                "total_pts_est": pred["total_points"],
                "point_diff_est": pred["point_diff"],
            })

    alerts.sort(key=lambda x: x["edge_pct"], reverse=True)
    return {
        "league": league,
        "total_teams": len(teams),
        "alerts": alerts[:20],
        "avg_total_points": round(np.mean([a["total_pts_est"] for a in alerts]) if alerts else 0, 1),
    }
