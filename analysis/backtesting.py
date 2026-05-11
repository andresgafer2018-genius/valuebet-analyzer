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

# ─────────────────────────────────────────────────────────────────────────────
# WALK-FORWARD VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def walk_forward_validation(league_name: str, window_months: int = 3,
                             step_months: int = 1, min_edge: float = 0.05,
                             initial_bankroll: float = 1000.0):
    """
    Walk-Forward Validation (WFV).

    En lugar de un split fijo, simula el uso real del modelo en el tiempo:
      - Ventana N: entrena con datos hasta mes X, testea en mes X+1..X+step
      - Ventana N+1: entrena hasta mes X+1, testea en mes X+2..X+step+1
      - ... y así hasta agotar los datos

    Esto detecta overfitting temporal que el backtesting simple no detecta.

    Parámetros:
      window_months  : meses de entrenamiento por ventana (default 3)
      step_months    : meses que avanza la ventana (default 1)
      min_edge       : edge mínimo para apostar (default 0.05)
      initial_bankroll: bankroll inicial por ventana (default 1000)

    Retorna dict con métricas agregadas + detalle por ventana.
    """
    url = LEAGUES.get(league_name)
    if not url:
        return {"error": f"Liga no encontrada: {league_name}"}

    df = fetch_league_data(url)

    # Necesitamos columna de fecha
    if "Date" not in df.columns:
        return {"error": "El CSV no tiene columna Date"}

    # Parsear fecha — football-data.co.uk usa DD/MM/YY o DD/MM/YYYY
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Date", "FTHG", "FTAG", "B365H", "B365D", "B365A"])
    df = df.sort_values("Date").reset_index(drop=True)

    if len(df) < 60:
        return {"error": "Datos insuficientes para Walk-Forward (mínimo 60 partidos)"}

    min_date = df["Date"].min()
    max_date = df["Date"].max()

    windows = []
    cursor = min_date + pd.DateOffset(months=window_months)

    while cursor + pd.DateOffset(months=step_months) <= max_date:
        train_end  = cursor
        test_start = cursor
        test_end   = cursor + pd.DateOffset(months=step_months)

        train_df = df[df["Date"] < train_end]
        test_df  = df[(df["Date"] >= test_start) & (df["Date"] < test_end)]

        if len(train_df) < 20 or len(test_df) < 5:
            cursor += pd.DateOffset(months=step_months)
            continue

        # Entrenar promedios con datos de entrenamiento solamente
        home_avg = train_df["FTHG"].mean()
        away_avg = train_df["FTAG"].mean()

        # Simular apuestas en ventana de test
        wins = losses = 0
        bankroll_kelly = initial_bankroll
        bankroll_flat  = initial_bankroll
        flat_bet = initial_bankroll * 0.02
        bets = 0

        for _, row in test_df.iterrows():
            try:
                hw, dr, aw = poisson_prob(home_avg, away_avg)
                actual = "H" if row["FTHG"] > row["FTAG"] else ("D" if row["FTHG"] == row["FTAG"] else "A")

                for outcome, model_prob, odd, label in [
                    ("H", hw, row["B365H"], "Local"),
                    ("D", dr, row["B365D"], "Empate"),
                    ("A", aw, row["B365A"], "Visitante"),
                ]:
                    imp  = implied_prob(odd)
                    edge = model_prob - imp
                    if edge < min_edge:
                        continue

                    kelly_frac = max(0, (model_prob * odd - 1) / (odd - 1)) * 0.25
                    bet_kelly  = min(bankroll_kelly * kelly_frac, bankroll_kelly * 0.10)
                    bets += 1

                    won = (actual == outcome)
                    if won:
                        wins += 1
                        bankroll_kelly += bet_kelly * (odd - 1)
                        bankroll_flat  += flat_bet * (odd - 1)
                    else:
                        losses += 1
                        bankroll_kelly -= bet_kelly
                        bankroll_flat  -= flat_bet
            except Exception:
                continue

        total = wins + losses
        roi_kelly = round((bankroll_kelly - initial_bankroll) / initial_bankroll * 100, 2) if total > 0 else 0
        roi_flat  = round((bankroll_flat  - initial_bankroll) / initial_bankroll * 100, 2) if total > 0 else 0
        win_rate  = round(wins / total * 100, 1) if total > 0 else 0

        windows.append({
            "period"         : f"{test_start.strftime('%b %Y')}",
            "train_size"     : len(train_df),
            "test_size"      : len(test_df),
            "bets"           : bets,
            "wins"           : wins,
            "losses"         : losses,
            "win_rate"       : win_rate,
            "roi_kelly"      : roi_kelly,
            "roi_flat"       : roi_flat,
            "bankroll_kelly" : round(bankroll_kelly, 2),
            "bankroll_flat"  : round(bankroll_flat, 2),
        })

        cursor += pd.DateOffset(months=step_months)

    if not windows:
        return {"error": "No se generaron ventanas válidas"}

    # Métricas agregadas
    all_rois_kelly = [w["roi_kelly"] for w in windows]
    all_rois_flat  = [w["roi_flat"]  for w in windows]
    profitable_windows = sum(1 for r in all_rois_kelly if r > 0)

    return {
        "league"              : league_name,
        "window_months"       : window_months,
        "step_months"         : step_months,
        "total_windows"       : len(windows),
        "profitable_windows"  : profitable_windows,
        "pct_profitable"      : round(profitable_windows / len(windows) * 100, 1),
        "avg_roi_kelly"       : round(sum(all_rois_kelly) / len(all_rois_kelly), 2),
        "avg_roi_flat"        : round(sum(all_rois_flat)  / len(all_rois_flat),  2),
        "best_roi_kelly"      : max(all_rois_kelly),
        "worst_roi_kelly"     : min(all_rois_kelly),
        "std_roi_kelly"       : round(pd.Series(all_rois_kelly).std(), 2),
        "windows"             : windows,
    }
