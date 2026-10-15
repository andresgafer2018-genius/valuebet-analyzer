# -*- coding: utf-8 -*-
"""
backtest_pinnacle.py  -  ValueBet Analyzer: Pinnacle como precio justo. NO modifica nada.
(v2: margen quitado con metodo potencia + tabla solo cuotas <= 3)

Idea: Pinnacle es la casa mas eficiente. Si le sacamos el margen, su cuota es una buena
estimacion de la probabilidad real. Apostamos solo cuando otra casa paga MAS que ese
precio justo. No usa el modelo Dixon-Coles para nada.

Dos escenarios:
  A) PRE-PARTIDO (el realista): precio justo = Pinnacle pre-cierre, apostamos a la cuota
     pre-cierre de la casa. Ademas medimos el CLV: si la cuota que tomamos le gana a la
     de cierre de Pinnacle (sin margen). CLV positivo sostenido = edge real.
  B) CIERRE vs CIERRE (optimista): las dos cuotas al cierre. Sirve de techo.

Casas: "Mejor cuota" (la mas alta del mercado: optimista, a veces son errores o casas
raras), "Promedio" (una casa blanda tipica) y "Bet365" (una casa real concreta).

Usa los mismos CSV de bt_cache/ que backtest_real.py (los que falten los baja).
Uso (desde la carpeta del proyecto):   py -3.11 backtest_pinnacle.py
Guarda el detalle en backtest_pinnacle.csv
"""
import io
import sys
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CACHE = ROOT / "bt_cache"
MAIN = {"E0": "Premier League", "SP1": "La Liga", "I1": "Serie A", "D1": "Bundesliga",
        "F1": "Ligue 1", "B1": "Belgium First Div"}
SEASONS = ["2425", "2526", "2627"]
EXTRA = {"ARG": "Liga Argentina", "BRA": "Brazil Serie A"}

UMBRALES = [0.00, 0.02, 0.04, 0.06]   # valor minimo exigido: cuota * p_justa - 1
MAX_VALOR = 0.15                      # mas de 15% casi siempre es un error de dato
MIN_ODD, MAX_ODD = 1.30, 10.0

# columnas de football-data: (pre-cierre, cierre) para cada salida
OUT = ["H", "D", "A", "O", "U"]
PIN = {"pre": ["PSH", "PSD", "PSA", "P>2.5", "P<2.5"],
       "cie": ["PSCH", "PSCD", "PSCA", "PC>2.5", "PC<2.5"]}
CASAS = {
    "Mejor cuota": {"pre": ["MaxH", "MaxD", "MaxA", "Max>2.5", "Max<2.5"],
                    "cie": ["MaxCH", "MaxCD", "MaxCA", "MaxC>2.5", "MaxC<2.5"]},
    "Promedio":    {"pre": ["AvgH", "AvgD", "AvgA", "Avg>2.5", "Avg<2.5"],
                    "cie": ["AvgCH", "AvgCD", "AvgCA", "AvgC>2.5", "AvgC<2.5"]},
    "Bet365":      {"pre": ["B365H", "B365D", "B365A", "B365>2.5", "B365<2.5"],
                    "cie": ["B365CH", "B365CD", "B365CA", "B365C>2.5", "B365C<2.5"]},
}


# ───────────────────────────── datos ─────────────────────────────
def _k(casa):
    return "c_" + casa.replace(" ", "_").lower()


def _get_csv(url, name):
    CACHE.mkdir(exist_ok=True)
    f = CACHE / name
    if not f.exists():
        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                return None
            f.write_bytes(r.content)
        except Exception as e:
            print(f"   [aviso] no pude bajar {url}: {e}")
            return None
    return pd.read_csv(io.StringIO(f.read_bytes().decode("utf-8", errors="ignore")))


def _col(df, name):
    if name in df.columns:
        return pd.to_numeric(df[name], errors="coerce")
    return pd.Series(np.nan, index=df.index)


def _frame(df, league, home, away, hg, ag, res):
    out = pd.DataFrame({
        "date": pd.to_datetime(df["Date"], dayfirst=True, errors="coerce"),
        "league": league, "home_team": df[home], "away_team": df[away],
        "hg": df[hg].astype(int), "ag": df[ag].astype(int), "result": df[res],
    })
    for t in ("pre", "cie"):
        for o, c in zip(OUT, PIN[t]):
            out[f"pin_{t}_{o}"] = _col(df, c)
        for casa, cols in CASAS.items():
            for o, c in zip(OUT, cols[t]):
                out[f"{_k(casa)}_{t}_{o}"] = _col(df, c)
    return out


def load_all():
    frames = []
    for code, league in MAIN.items():
        for s in SEASONS:
            df = _get_csv(f"https://www.football-data.co.uk/mmz4281/{s}/{code}.csv", f"{code}_{s}.csv")
            if df is None or "HomeTeam" not in df.columns:
                continue
            df = df.dropna(subset=["HomeTeam", "AwayTeam", "FTHG", "FTAG"])
            frames.append(_frame(df, league, "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"))
    for code, league in EXTRA.items():
        df = _get_csv(f"https://www.football-data.co.uk/new/{code}.csv", f"{code}.csv")
        if df is None or "Home" not in df.columns:
            continue
        df = df.dropna(subset=["Home", "Away", "HG", "AG"])
        df = df[df["Season"].astype(str).isin(sorted(df["Season"].astype(str).unique())[-3:])]
        frames.append(_frame(df, league, "Home", "Away", "HG", "AG", "Res"))
    all_df = pd.concat(frames, ignore_index=True).dropna(subset=["date"])
    return all_df.sort_values("date", kind="stable").reset_index(drop=True)


def _fair(odds):
    """Quita el margen con el metodo POTENCIA: p_i = (1/cuota_i)^k, con k tal que sumen 1.
    El metodo proporcional (v1) le dejaba demasiada probabilidad a las cuotas altas
    (sesgo favorito-batacazo) y fabricaba 'valor' falso en los batacazos."""
    if any(not (isinstance(x, float) and x > 1) for x in odds):
        return None
    imp = np.array([1 / x for x in odds])
    if imp.sum() <= 1:
        return imp / imp.sum()
    lo, hi = 1.0, 3.0
    for _ in range(50):
        k = (lo + hi) / 2
        if (imp ** k).sum() > 1:
            lo = k
        else:
            hi = k
    p = imp ** ((lo + hi) / 2)
    return p / p.sum()


def _won(o, r):
    tg = r.hg + r.ag
    return {"H": r.result == "H", "D": r.result == "D", "A": r.result == "A",
            "O": tg > 2, "U": tg <= 2}[o]


# ─────────────────────────── simulacion ───────────────────────────
def run():
    t0 = time.time()
    print("Leyendo datos (usa bt_cache/; si falta algo lo baja)...")
    df = load_all()
    print(f"   {len(df)} partidos, {df['date'].min().date()} -> {df['date'].max().date()}\n")

    bets = []
    for r in df.itertuples(index=False):
        rd = r._asdict()
        fair = {}
        for t in ("pre", "cie"):
            f1 = _fair([rd[f"pin_{t}_{o}"] for o in "HDA"])
            f2 = _fair([rd[f"pin_{t}_{o}"] for o in "OU"])
            fair[t] = {}
            if f1 is not None:
                fair[t].update(dict(zip("HDA", f1)))
            if f2 is not None:
                fair[t].update(dict(zip("OU", f2)))

        for esc, t in (("A) Pre-partido", "pre"), ("B) Cierre vs cierre", "cie")):
            for casa in CASAS:
                for o in OUT:
                    p = fair[t].get(o)
                    odd = rd[f"{_k(casa)}_{t}_{o}"]
                    if p is None or not (isinstance(odd, float) and MIN_ODD <= odd <= MAX_ODD):
                        continue
                    valor = odd * p - 1
                    if not (UMBRALES[0] < valor <= MAX_VALOR):
                        continue
                    w = _won(o, r)
                    pc = fair["cie"].get(o)          # CLV contra Pinnacle cierre sin margen
                    clv = odd * pc - 1 if pc else np.nan
                    bets.append({"escenario": esc, "casa": casa, "fecha": r.date.date(),
                                 "liga": r.league, "local": r.home_team, "visitante": r.away_team,
                                 "salida": o, "mercado": "1X2" if o in "HDA" else "O/U 2.5",
                                 "cuota": odd, "p_justa": round(p, 4),
                                 "valor_pct": round(valor * 100, 2),
                                 "clv_pct": round(clv * 100, 2) if clv == clv else np.nan,
                                 "gano": int(w), "ganancia": round(odd - 1 if w else -1.0, 4)})
    print(f"Listo en {time.time()-t0:.0f}s\n")
    report(pd.DataFrame(bets))


# ──────────────────────────── reporte ────────────────────────────
def _line(g):
    n = len(g)
    if n == 0:
        return "   0 apuestas"
    roi = g["ganancia"].mean() * 100
    se = g["ganancia"].std(ddof=1) / math.sqrt(n) * 100 if n > 1 else float("nan")
    clv = g["clv_pct"].mean()
    return (f"{n:5d} ap | acierto {g['gano'].mean()*100:5.1f}% | cuota {g['cuota'].mean():5.2f} | "
            f"ROI {roi:+6.1f}% (IC95 {roi-1.96*se:+.1f} a {roi+1.96*se:+.1f}) | CLV {clv:+5.1f}%")


def report(b):
    sep = "=" * 100
    if len(b) == 0:
        print("No hubo apuestas: los CSV no traen las columnas esperadas. Mandale esto a Claude.")
        return
    b.to_csv(ROOT / "backtest_pinnacle.csv", index=False)
    print(sep); print("PINNACLE COMO PRECIO JUSTO  (stake fijo 1 unidad)"); print(sep)
    print("valor = cuota de la casa x prob. justa de Pinnacle - 1   |   "
          "CLV = cuota tomada vs Pinnacle cierre sin margen\n")
    for esc, ge in b.groupby("escenario"):
        print(f"### {esc.upper()}")
        for casa in CASAS:
            gc = ge[ge["casa"] == casa]
            print(f"  -- {casa} --")
            for u in UMBRALES:
                print(f"   valor > {u*100:3.0f}%   ", _line(gc[gc["valor_pct"] > u * 100]))
            gc3 = gc[gc["cuota"] <= 3]
            for u in UMBRALES:
                print(f"   cuota<=3 v>{u*100:2.0f}%", _line(gc3[gc3["valor_pct"] > u * 100]))
        print()

    # Desglose del escenario realista, umbral 2%, casa promedio y mejor cuota
    for casa in ("Mejor cuota", "Promedio"):
        g = b[(b["escenario"] == "A) Pre-partido") & (b["casa"] == casa) & (b["valor_pct"] > 2)]
        print(f"### DESGLOSE  pre-partido | {casa} | valor > 2%")
        for lg, gg in g.groupby("liga"):
            print(f"   {lg:20}", _line(gg))
        for m, gg in g.groupby("mercado"):
            print(f"   {m:20}", _line(gg))
        g = g.assign(rango=pd.cut(g["cuota"], [1.3, 2, 3, 5, 10.01], right=False,
                                  labels=["1.30-2", "2-3", "3-5", "5-10"]))
        for rg, gg in g.groupby("rango", observed=True):
            print(f"   cuota {str(rg):14}", _line(gg))
        print()
    print("Detalle guardado en backtest_pinnacle.csv")
    print("Mandale a Claude toda esta salida.")


if __name__ == "__main__":
    run()
