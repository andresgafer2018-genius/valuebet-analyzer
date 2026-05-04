import pandas as pd
import numpy as np
import requests
import io
from math import exp

# Datos gratuitos: Tennis Abstract (Jeff Sackmann) - GitHub
TOUR_URLS = {
    "ATP 2024": "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2024.csv",
    "ATP 2023": "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_2023.csv",
    "WTA 2024": "https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_2024.csv",
}

SURFACE_MAP = {"Hard": "Dura", "Clay": "Tierra", "Grass": "Hierba", "Carpet": "Moqueta"}

def fetch_tour_data(url):
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.content.decode("utf-8", errors="ignore")))
    return df

def build_elo_ratings(df, k=32, initial=1500):
    ratings = {}
    surface_ratings = {}
    for _, row in df.iterrows():
        w, l = str(row.get("winner_name","")), str(row.get("loser_name",""))
        surf = str(row.get("surface","Hard"))
        if not w or not l or w=="nan" or l=="nan":
            continue
        rw = ratings.get(w, initial)
        rl = ratings.get(l, initial)
        srw = surface_ratings.get((w,surf), initial)
        srl = surface_ratings.get((l,surf), initial)
        ew = 1/(1+10**((rl-rw)/400))
        esw = 1/(1+10**((srl-srw)/400))
        ratings[w] = rw + k*(1-ew)
        ratings[l] = rl + k*(0-( 1-ew))
        surface_ratings[(w,surf)] = srw + k*(1-esw)
        surface_ratings[(l,surf)] = srl + k*(0-(1-esw))
    return ratings, surface_ratings

def win_prob_from_elo(elo_a, elo_b):
    return 1/(1+10**((elo_b-elo_a)/400))

def estimate_set_probs(p_win, best_of=3):
    """Probabilidad de ganar sets dado p_win del partido."""
    if best_of == 3:
        sets_needed = 2
        max_sets = 3
    else:
        sets_needed = 3
        max_sets = 5
    p2_0 = p_win**2
    p2_1 = 2 * p_win**2 * (1-p_win)
    p_lose = 1 - p_win
    p0_2 = p_lose**2
    p1_2 = 2 * p_lose**2 * p_win
    return {"2-0": round(p2_0,3), "2-1": round(p2_1,3),
            "0-2": round(p0_2,3), "1-2": round(p1_2,3)}

def estimate_total_games(p_win, surface):
    """Estima total de games basado en superficie y probabilidad."""
    base = {"Hard":37, "Clay":40, "Grass":34, "Carpet":36}
    competitiveness = 1 - abs(p_win - 0.5) * 2
    total = base.get(surface, 37) * (0.85 + 0.3 * competitiveness)
    return round(total, 1)

_cache = {}

def analyze_tennis(tour="ATP 2024", min_edge=0.05):
    global _cache
    url = TOUR_URLS.get(tour)
    if not url:
        return {"error": f"Tour no encontrado: {tour}"}

    cache_key = f"tennis_{tour}"
    if cache_key not in _cache:
        df = fetch_tour_data(url)
        ratings, surface_ratings = build_elo_ratings(df)
        _cache[cache_key] = (df, ratings, surface_ratings)
    else:
        df, ratings, surface_ratings = _cache[cache_key]

    recent = df.tail(60).copy()
    alerts = []
    seen = set()

    for _, row in recent.iterrows():
        w = str(row.get("winner_name",""))
        l = str(row.get("loser_name",""))
        surf = str(row.get("surface","Hard"))
        tourney = str(row.get("tourney_name",""))
        odds_w = row.get("B365W", row.get("CBW", None))
        odds_l = row.get("B365L", row.get("CBL", None))

        if w=="nan" or l=="nan":
            continue
        pair = tuple(sorted([w,l]))
        if pair in seen:
            continue
        seen.add(pair)

        elo_w = surface_ratings.get((w,surf), ratings.get(w,1500))
        elo_l = surface_ratings.get((l,surf), ratings.get(l,1500))
        p_w = win_prob_from_elo(elo_w, elo_l)
        p_l = 1 - p_w
        surf_esp = SURFACE_MAP.get(surf, surf)
        total_games = estimate_total_games(p_w, surf)
        set_probs = estimate_set_probs(p_w)

        for player, p_model, odd, role in [
            (w, p_w, odds_w, "winner"),
            (l, p_l, odds_l, "loser"),
        ]:
            if odd is None or pd.isna(odd) or odd <= 1:
                implied = 0.5
                odd = round(1/p_model * 1.05, 2)
            else:
                implied = 1/float(odd)
            edge = p_model - implied
            if edge < min_edge:
                continue
            kelly = max(0, (p_model * float(odd) - 1) / (float(odd) - 1)) * 0.25
            opponent = l if role=="winner" else w
            alerts.append({
                "sport": "tennis",
                "match": f"{w} vs {l}",
                "player": player,
                "opponent": opponent,
                "tournament": tourney,
                "surface": surf_esp,
                "market": "Ganador partido",
                "model_prob": round(p_model*100,1),
                "implied_prob": round(implied*100,1),
                "edge_pct": round(edge*100,1),
                "odd": float(odd),
                "kelly_frac": round(kelly,3),
                "confidence": "ALTA" if edge>0.10 else "MEDIA",
                "elo_player": round(elo_w if role=="winner" else elo_l),
                "total_games_est": total_games,
                "set_probs": set_probs,
                "tour": tour,
            })

    alerts.sort(key=lambda x: x["edge_pct"], reverse=True)
    return {
        "tour": tour,
        "total_players": len(ratings),
        "alerts": alerts[:20],
        "surface_breakdown": {
            SURFACE_MAP.get(s,s): round(len(df[df["surface"]==s])/len(df)*100,1)
            for s in df["surface"].dropna().unique()
        }
    }
