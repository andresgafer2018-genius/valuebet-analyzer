import pandas as pd
import numpy as np
import requests
import io

LEAGUES = {
    "Premier League": "https://www.football-data.co.uk/mmz4281/2324/E0.csv",
    "La Liga":        "https://www.football-data.co.uk/mmz4281/2324/SP1.csv",
    "Serie A":        "https://www.football-data.co.uk/mmz4281/2324/I1.csv",
    "Bundesliga":     "https://www.football-data.co.uk/mmz4281/2324/D1.csv",
}

def fetch_league_data(url):
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.content.decode("utf-8", errors="ignore")))
    df = df.dropna(subset=["HomeTeam","AwayTeam","FTHG","FTAG","B365H","B365D","B365A"])
    return df

def implied_prob(odd):
    return 1.0 / odd if odd > 1 else 0.0

def poisson_prob(home_goals_avg, away_goals_avg, max_goals=6):
    from math import exp, factorial
    home_win = draw = away_win = 0.0
    for i in range(max_goals+1):
        for j in range(max_goals+1):
            p = (exp(-home_goals_avg) * home_goals_avg**i / factorial(i)) * \
                (exp(-away_goals_avg) * away_goals_avg**j / factorial(j))
            if i > j:   home_win += p
            elif i == j: draw    += p
            else:        away_win += p
    return home_win, draw, away_win

def run_backtest(league_name, initial_bankroll=1000.0, min_edge=0.05):
    url = LEAGUES.get(league_name)
    if not url:
        return {"error": f"Liga no encontrada: {league_name}"}

    df = fetch_league_data(url)

    home_avg = df["FTHG"].mean()
    away_avg = df["FTAG"].mean()

    results_kelly = []
    results_flat  = []
    bankroll_kelly = initial_bankroll
    bankroll_flat  = initial_bankroll
    flat_bet = initial_bankroll * 0.02

    wins = losses = 0
    current_streak = best_streak = worst_streak = 0
    streak_type = None

    bets_by_type = {"Local": {"wins":0,"total":0}, "Empate": {"wins":0,"total":0}, "Visitante": {"wins":0,"total":0}}

    for _, row in df.iterrows():
        hw, dr, aw = poisson_prob(home_avg, away_avg)
        actual = "H" if row["FTHG"] > row["FTAG"] else ("D" if row["FTHG"] == row["FTAG"] else "A")

        for outcome, model_prob, odd, label in [
            ("H", hw, row["B365H"], "Local"),
            ("D", dr, row["B365D"], "Empate"),
            ("A", aw, row["B365A"], "Visitante"),
        ]:
            imp = implied_prob(odd)
            edge = model_prob - imp
            if edge < min_edge:
                continue

            kelly_frac = max(0, (model_prob * odd - 1) / (odd - 1)) * 0.25
            bet_kelly = bankroll_kelly * kelly_frac
            bet_kelly = min(bet_kelly, bankroll_kelly * 0.10)

            won = (actual == outcome)
            bets_by_type[label]["total"] += 1

            if won:
                bankroll_kelly += bet_kelly * (odd - 1)
                bankroll_flat  += flat_bet * (odd - 1)
                wins += 1
                bets_by_type[label]["wins"] += 1
                if streak_type == "win":
                    current_streak += 1
                else:
                    current_streak = 1
                    streak_type = "win"
                best_streak = max(best_streak, current_streak)
            else:
                bankroll_kelly -= bet_kelly
                bankroll_flat  -= flat_bet
                losses += 1
                if streak_type == "loss":
                    current_streak += 1
                else:
                    current_streak = 1
                    streak_type = "loss"
                worst_streak = max(worst_streak, current_streak)

            results_kelly.append(round(bankroll_kelly, 2))
            results_flat.append(round(bankroll_flat, 2))

    total_bets = wins + losses
    roi_kelly = round((bankroll_kelly - initial_bankroll) / initial_bankroll * 100, 2)
    roi_flat  = round((bankroll_flat  - initial_bankroll) / initial_bankroll * 100, 2)

    accuracy_by_type = {
        k: round(v["wins"] / v["total"] * 100, 1) if v["total"] > 0 else 0
        for k, v in bets_by_type.items()
    }

    step = max(1, len(results_kelly) // 50)
    chart_kelly = results_kelly[::step]
    chart_flat  = results_flat[::step]

    return {
        "league": league_name,
        "total_bets": total_bets,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / total_bets * 100, 1) if total_bets > 0 else 0,
        "roi_kelly": roi_kelly,
        "roi_flat": roi_flat,
        "final_bankroll_kelly": round(bankroll_kelly, 2),
        "final_bankroll_flat": round(bankroll_flat, 2),
        "best_streak": best_streak,
        "worst_streak": worst_streak,
        "accuracy_by_type": accuracy_by_type,
        "chart_kelly": chart_kelly,
        "chart_flat": chart_flat,
        "initial_bankroll": initial_bankroll,
    }
