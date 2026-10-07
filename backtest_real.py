# -*- coding: utf-8 -*-
"""
backtest_real.py  -  ValueBet Analyzer: backtest walk-forward con cuotas reales. NO modifica nada.

Que hace:
  1. Baja los CSV de football-data (3 temporadas) con cuotas de cierre de Pinnacle
     y la mejor cuota del mercado. Los guarda en bt_cache/ (la 2da vez no baja nada).
  2. Desde FECHA_INICIO, cada semana re-entrena el modelo de produccion SOLO con
     partidos ya jugados (ventana de ~15 meses, igual que produccion) y predice la
     semana siguiente. Sin mirar el futuro.
  3. Aplica las mismas reglas que produccion (cobertura, edge 3-15%, cuota >= 1.50)
     y liquida cada apuesta con el resultado real, a stake fijo de 1 unidad.
  4. Muestra ROI, intervalo de confianza, desglose por liga/mercado/edge, y compara
     la precision del modelo contra la del mercado (Pinnacle).

Uso (desde la carpeta del proyecto):   py -3.11 backtest_real.py
Guarda el detalle de cada apuesta en backtest_apuestas.csv
"""
import io
import sys
import time
import math
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
# Windows: la consola usa cp1252 y no puede escribir caracteres como la letra griega rho
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
sys.path.insert(0, str(ROOT))

# El clima de HOY no tiene sentido para partidos pasados: lo apagamos en el backtest.
import data.weather as _weather
_weather.get_weather_for_league = lambda league: {"available": False}

from models.engine import PoissonModel, ProbabilityCalibrator, ValueBetDetector

FECHA_INICIO   = "2025-08-01"   # primer partido que se apuesta
VENTANA_DIAS   = 450            # entrenamiento: ultimos ~15 meses (como produccion)
MIN_EDGE       = ValueBetDetector.MIN_EDGE
MAX_EDGE       = ValueBetDetector.MAX_EDGE
MIN_ODD        = ValueBetDetector.MIN_ODD
CACHE          = ROOT / "bt_cache"

MAIN = {"E0": "Premier League", "SP1": "La Liga", "I1": "Serie A", "D1": "Bundesliga",
        "F1": "Ligue 1", "B1": "Belgium First Div"}
SEASONS = ["2425", "2526", "2627"]
EXTRA = {"ARG": "Liga Argentina", "BRA": "Brazil Serie A"}


# ───────────────────────────── datos ─────────────────────────────
def _get_csv(url: str, name: str) -> pd.DataFrame | None:
    CACHE.mkdir(exist_ok=True)
    f = CACHE / name
    # La temporada en curso se re-baja siempre; las cerradas se usan del cache
    if not f.exists() or "2627" in name or name in ("ARG.csv", "BRA.csv"):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                return None
            f.write_bytes(r.content)
        except Exception as e:
            print(f"   [aviso] no pude bajar {url}: {e}")
            if not f.exists():
                return None
    return pd.read_csv(io.StringIO(f.read_bytes().decode("utf-8", errors="ignore")))


def _col(df, *names):
    for n in names:
        if n in df.columns:
            return pd.to_numeric(df[n], errors="coerce")
    return pd.Series(np.nan, index=df.index)


def load_all() -> pd.DataFrame:
    frames = []
    for code, league in MAIN.items():
        for s in SEASONS:
            df = _get_csv(f"https://www.football-data.co.uk/mmz4281/{s}/{code}.csv", f"{code}_{s}.csv")
            if df is None or "HomeTeam" not in df.columns:
                continue
            df = df.dropna(subset=["HomeTeam", "AwayTeam", "FTHG", "FTAG"])
            frames.append(pd.DataFrame({
                "date": pd.to_datetime(df["Date"], dayfirst=True, errors="coerce"),
                "league": league,
                "home_team": df["HomeTeam"], "away_team": df["AwayTeam"],
                "home_goals": df["FTHG"].astype(int), "away_goals": df["FTAG"].astype(int),
                "result": df["FTR"],
                "pin_H": _col(df, "PSCH"), "pin_D": _col(df, "PSCD"), "pin_A": _col(df, "PSCA"),
                "pin_O": _col(df, "PC>2.5"), "pin_U": _col(df, "PC<2.5"),
                "max_H": _col(df, "MaxCH"), "max_D": _col(df, "MaxCD"), "max_A": _col(df, "MaxCA"),
                "max_O": _col(df, "MaxC>2.5"), "max_U": _col(df, "MaxC<2.5"),
            }))
    for code, league in EXTRA.items():
        df = _get_csv(f"https://www.football-data.co.uk/new/{code}.csv", f"{code}.csv")
        if df is None or "Home" not in df.columns:
            continue
        df = df.dropna(subset=["Home", "Away", "HG", "AG"])
        df = df[df["Season"].astype(str).isin(sorted(df["Season"].astype(str).unique())[-3:])]
        frames.append(pd.DataFrame({
            "date": pd.to_datetime(df["Date"], dayfirst=True, errors="coerce"),
            "league": league,
            "home_team": df["Home"], "away_team": df["Away"],
            "home_goals": df["HG"].astype(int), "away_goals": df["AG"].astype(int),
            "result": df["Res"],
            "pin_H": _col(df, "PSCH"), "pin_D": _col(df, "PSCD"), "pin_A": _col(df, "PSCA"),
            "pin_O": np.nan, "pin_U": np.nan,   # estas ligas no traen Over/Under
            "max_H": _col(df, "MaxCH"), "max_D": _col(df, "MaxCD"), "max_A": _col(df, "MaxCA"),
            "max_O": np.nan, "max_U": np.nan,
        }))
    all_df = pd.concat(frames, ignore_index=True).dropna(subset=["date"])
    return all_df.sort_values("date", kind="stable").reset_index(drop=True)


# ─────────────────────────── simulacion ───────────────────────────
MARKETS = [("1X2_H", "p_home", "H"), ("1X2_D", "p_draw", "D"), ("1X2_A", "p_away", "A"),
           ("OVER25", "p_over25", "O"), ("UNDER25", "p_under25", "U")]


def won(market, row):
    tg = row.home_goals + row.away_goals
    return {"1X2_H": row.result == "H", "1X2_D": row.result == "D", "1X2_A": row.result == "A",
            "OVER25": tg > 2, "UNDER25": tg <= 2}[market]


def run():
    t0 = time.time()
    print("Bajando datos de football-data (la primera vez tarda ~1 minuto)...")
    df = load_all()
    print(f"   {len(df)} partidos, {df['date'].min().date()} -> {df['date'].max().date()} "
          f"({time.time()-t0:.0f}s)")

    start = pd.Timestamp(FECHA_INICIO)
    weeks = pd.date_range(start, df["date"].max() + pd.Timedelta(days=7), freq="7D")
    bets, evalrows = [], []
    print(f"Simulando {len(weeks)-1} semanas (re-entrenando cada semana)...")

    for wi in range(len(weeks) - 1):
        w0, w1 = weeks[wi], weeks[wi + 1]
        train = df[(df["date"] < w0) & (df["date"] >= w0 - pd.Timedelta(days=VENTANA_DIAS))]
        test = df[(df["date"] >= w0) & (df["date"] < w1)]
        if len(test) == 0 or len(train) < 500:
            continue

        import contextlib, os
        with open(os.devnull, "w", encoding="utf-8") as dn, contextlib.redirect_stdout(dn):
            pm = PoissonModel(); pm.fit(train.reset_index(drop=True))
            cal = ProbabilityCalibrator()
            pl, rs = [], []
            for r in train.itertuples():
                pl.append(pm.predict_proba(r.home_team, r.away_team, r.league)); rs.append(r.result)
            cal.fit(pl, rs)

        for r in test.itertuples():
            pred = pm.predict_proba(r.home_team, r.away_team, r.league)
            if not pred["model_coverage"]["ok"]:
                continue
            raw = np.array([pred["p_home"], pred["p_draw"], pred["p_away"]])
            pred = cal.calibrate(pred)
            # Comparacion modelo vs mercado (1X2, Pinnacle sin margen)
            ph, pd_, pa = r.pin_H, r.pin_D, r.pin_A
            if all(isinstance(x, float) and x > 1 for x in (ph, pd_, pa)):
                imp = np.array([1/ph, 1/pd_, 1/pa]); imp /= imp.sum()
                mod = np.array([pred["p_home"], pred["p_draw"], pred["p_away"]])
                k = "HDA".index(r.result)
                evalrows.append({"league": r.league,
                                 "ll_model": -math.log(max(mod[k], 1e-6)),
                                 "ll_raw": -math.log(max(raw[k], 1e-6)),
                                 "ll_market": -math.log(max(imp[k], 1e-6))})
            for market, pkey, okey in MARKETS:
                p = pred[pkey]
                for scen, prefix in (("Pinnacle cierre", "pin_"), ("Mejor cuota", "max_")):
                    odd = getattr(r, prefix + okey)
                    if not (isinstance(odd, float) and odd >= MIN_ODD):
                        continue
                    edge = p - 1 / odd
                    if MIN_EDGE <= edge <= MAX_EDGE:
                        w = won(market, r)
                        bets.append({"escenario": scen, "fecha": r.date.date(), "liga": r.league,
                                     "local": r.home_team, "visitante": r.away_team,
                                     "mercado": market, "cuota": odd, "p_modelo": round(p, 4),
                                     "edge_pct": round(edge * 100, 2), "gano": int(w),
                                     "ganancia": round(odd - 1 if w else -1.0, 4)})
        if wi % 8 == 0:
            print(f"   semana {wi+1}/{len(weeks)-1} ({w0.date()})  apuestas hasta ahora: "
                  f"{sum(b['escenario']=='Pinnacle cierre' for b in bets)}")

    print(f"Simulacion terminada en {time.time()-t0:.0f}s\n")
    report(pd.DataFrame(bets), pd.DataFrame(evalrows))


# ──────────────────────────── reporte ────────────────────────────
def _roi_line(g):
    n = len(g)
    if n == 0:
        return "0 apuestas"
    roi = g["ganancia"].mean() * 100
    se = g["ganancia"].std(ddof=1) / math.sqrt(n) * 100 if n > 1 else float("nan")
    return (f"{n:4d} apuestas | acierto {g['gano'].mean()*100:5.1f}% | cuota media "
            f"{g['cuota'].mean():.2f} | ROI {roi:+6.1f}%  (IC95: {roi-1.96*se:+.1f}% a {roi+1.96*se:+.1f}%)")


def report(b: pd.DataFrame, ev: pd.DataFrame):
    sep = "=" * 92
    print(sep); print("RESULTADO DEL BACKTEST  (stake fijo 1 unidad por apuesta)"); print(sep)
    if len(b) == 0:
        print("No hubo apuestas. Revisa que bt_cache/ tenga los CSV.")
        return
    b.to_csv(ROOT / "backtest_apuestas.csv", index=False)

    for scen in ("Pinnacle cierre", "Mejor cuota"):
        g = b[b["escenario"] == scen]
        print(f"\n### {scen.upper()}")
        print("   TOTAL      ", _roi_line(g))
        print("   -- por liga --")
        for lg, gg in g.groupby("liga"):
            print(f"   {lg:20}", _roi_line(gg))
        print("   -- por mercado --")
        for m, gg in g.groupby("mercado"):
            print(f"   {m:20}", _roi_line(gg))
        print("   -- por tamano del edge --")
        g = g.assign(rango=pd.cut(g["edge_pct"], [3, 5, 8, 11, 15.01], right=False,
                                  labels=["3-5%", "5-8%", "8-11%", "11-15%"]))
        for rg, gg in g.groupby("rango", observed=True):
            print(f"   edge {str(rg):15}", _roi_line(gg))

    if len(ev):
        print(f"\n### PRECISION 1X2: MODELO vs MERCADO (log-loss, mas bajo = mejor)")
        print(f"   {'TOTAL':20} modelo {ev['ll_model'].mean():.4f} | sin calibrar {ev['ll_raw'].mean():.4f}"
              f" | Pinnacle {ev['ll_market'].mean():.4f}  ({len(ev)} partidos)")
        for lg, gg in ev.groupby("league"):
            print(f"   {lg:20} modelo {gg['ll_model'].mean():.4f} | sin calibrar {gg['ll_raw'].mean():.4f}"
                  f" | Pinnacle {gg['ll_market'].mean():.4f}")
    print("\nDetalle de cada apuesta guardado en backtest_apuestas.csv")
    print("Mandale a Claude toda esta salida.")


if __name__ == "__main__":
    run()
