
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
    url = LEAGUE_URLS.get(league_name)
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
