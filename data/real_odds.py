import os
from dotenv import load_dotenv
load_dotenv()
from scipy.stats import poisson as scipy_poisson
from data.fetcher import get_odds, get_fixtures_league, get_team_stats

SUPPORTED_LEAGUES = {
    "Liga Argentina":  "soccer_argentina_primera_division",
    "Brazil Serie A":  "soccer_brazil_campeonato",
    "Chile Primera":   "soccer_chile_campeonato",
    "Austria Bundesliga": "soccer_austria_bundesliga",
    "Belgium First":   "soccer_belgium_first_div",
}

def poisson_match_probs(home_avg, away_avg, max_goals=6):
    home_win = draw = away_win = 0.0
    for i in range(max_goals+1):
        for j in range(max_goals+1):
            p = scipy_poisson.pmf(i, home_avg) * scipy_poisson.pmf(j, away_avg)
            if i > j:   home_win += p
            elif i==j:  draw     += p
            else:       away_win += p
    return {"home_win": home_win, "draw": draw, "away_win": away_win}

def get_real_alerts(league_name="Liga Argentina", min_edge=0.03):
    sport_key = SUPPORTED_LEAGUES.get(league_name)
    if not sport_key:
        return {"error": f"Liga no soportada: {league_name}", "alerts": [], "total": 0}

    try:
        odds_data = get_odds(sport=sport_key, regions="eu", markets="h2h")
    except Exception as e:
        return {"error": f"Error The Odds API: {e}", "alerts": [], "total": 0}

    if not odds_data:
        return {"error": "Sin partidos disponibles", "alerts": [], "total": 0}

    alerts = []
    for game in odds_data:
        home_team = game.get("home_team", "")
        away_team = game.get("away_team", "")
        commence  = game.get("commence_time", "")
        bookmakers = game.get("bookmakers", [])
        if not bookmakers:
            continue

        best = {"home": None, "draw": None, "away": None}
        for bm in bookmakers[:4]:
            for market in bm.get("markets", []):
                if market["key"] != "h2h":
                    continue
                for outcome in market["outcomes"]:
                    name  = outcome["name"]
                    price = outcome["price"]
                    if name == home_team:
                        if best["home"] is None or price > best["home"]: best["home"] = price
                    elif name == away_team:
                        if best["away"] is None or price > best["away"]: best["away"] = price
                    elif name == "Draw":
                        if best["draw"] is None or price > best["draw"]: best["draw"] = price

        if not all(best.values()):
            continue

        probs = poisson_match_probs(1.4, 1.1)

        for outcome, model_p, odd, label in [
            ("home", probs["home_win"], best["home"], f"Victoria {home_team}"),
            ("draw", probs["draw"],     best["draw"], "Empate"),
            ("away", probs["away_win"], best["away"], f"Victoria {away_team}"),
        ]:
            if odd is None or odd <= 1:
                continue
            implied = 1 / odd
            edge    = model_p - implied
            if edge < min_edge:
                continue
            kelly = max(0, (model_p * odd - 1) / (odd - 1)) * 0.25
            alerts.append({
                "match":        f"{home_team} vs {away_team}",
                "league":       league_name,
                "market":       label,
                "outcome":      outcome,
                "model_prob":   round(model_p * 100, 1),
                "implied_prob": round(implied * 100, 1),
                "edge_pct":     round(edge * 100, 1),
                "odd":          odd,
                "kelly_frac":   round(kelly, 3),
                "confidence":   "ALTA" if edge > 0.10 else "MEDIA",
                "commence_time": commence,
                "data_source":  "real",
            })

    alerts.sort(key=lambda x: x["edge_pct"], reverse=True)
    return {
        "league":      league_name,
        "alerts":      alerts[:20],
        "total":       len(alerts),
        "data_source": "The Odds API (cuotas reales)",
    }
