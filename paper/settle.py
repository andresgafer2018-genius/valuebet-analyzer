# -*- coding: utf-8 -*-
"""
paper/settle.py  -  ValueBet Analyzer: paper trading, parte 2 (liquidar y medir CLV).
NO apuesta nada y NO toca la app. Solo lee y calcula.

Que hace:
  1. Lee las alertas de paper/alertas.csv (las anota paper/capture.py).
  2. Baja de football-data.co.uk los resultados y la cuota de CIERRE de Pinnacle
     (temporada 2026-27 de las 6 ligas europeas + Argentina y Brasil). No gasta creditos.
  3. Cruza cada alerta con su partido (nombres pasados por canon_team, fecha +-1 dia).
  4. Calcula para cada alerta:
       CLV      = cuota tomada x prob. justa de Pinnacle al cierre (metodo potencia) - 1
       ganancia = cuota - 1 si gano, -1 si perdio (stake fijo 1 unidad)
  5. Guarda paper/resultados.csv y muestra el resumen.

football-data actualiza sus CSV 1 o 2 veces por semana: los partidos muy recientes
todavia no aparecen; quedan "pendientes" y se liquidan en la proxima corrida.

Uso (desde la carpeta del proyecto):   py -3.11 paper\\settle.py
"""
import io
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from data.team_names import canon_team  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ALERTAS = ROOT / "paper" / "alertas.csv"
RESULTADOS = ROOT / "paper" / "resultados.csv"

TEMPORADA = "2627"
MAIN = {"E0": "Premier League", "SP1": "La Liga", "I1": "Serie A", "D1": "Bundesliga",
        "F1": "Ligue 1", "B1": "Belgium First Div"}
EXTRA = {"ARG": "Liga Argentina", "BRA": "Brazil Serie A"}


# ───────────────────────────── datos ─────────────────────────────
def _get(url):
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            print(f"   [aviso] HTTP {r.status_code} en {url}")
            return None
        return pd.read_csv(io.StringIO(r.content.decode("utf-8", errors="ignore")))
    except Exception as e:
        print(f"   [aviso] no pude bajar {url}: {e}")
        return None


def _num(df, col):
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce")
    return pd.Series(np.nan, index=df.index)


def _norm(df, liga, home, away, res):
    return pd.DataFrame({
        "fecha": pd.to_datetime(df["Date"], dayfirst=True, errors="coerce"),
        "liga": liga,
        "local_fd": df[home].map(canon_team),
        "visitante_fd": df[away].map(canon_team),
        "resultado": df[res],
        "pc_H": _num(df, "PSCH"), "pc_D": _num(df, "PSCD"), "pc_A": _num(df, "PSCA"),
    })


def cargar_resultados():
    frames = []
    for code, liga in MAIN.items():
        df = _get(f"https://www.football-data.co.uk/mmz4281/{TEMPORADA}/{code}.csv")
        if df is not None and "HomeTeam" in df.columns:
            df = df.dropna(subset=["HomeTeam", "AwayTeam", "FTR"])
            frames.append(_norm(df, liga, "HomeTeam", "AwayTeam", "FTR"))
    for code, liga in EXTRA.items():
        df = _get(f"https://www.football-data.co.uk/new/{code}.csv")
        if df is not None and "Home" in df.columns:
            df = df.dropna(subset=["Home", "Away", "Res"])
            frames.append(_norm(df, liga, "Home", "Away", "Res"))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).dropna(subset=["fecha"])


def fair_power(odds):
    """Quita el margen con el metodo POTENCIA (igual que capture.py y el backtest)."""
    if any(not (isinstance(x, (int, float)) and x > 1 and x == x) for x in odds):
        return None
    imp = np.array([1 / x for x in odds], dtype=float)
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


# ─────────────────────────── liquidacion ───────────────────────────
def liquidar(alertas, res):
    """Agrega a cada alerta: estado, resultado, pin_cierre, clv_pct, gano, ganancia."""
    idx = {}
    for r in res.itertuples(index=False):
        idx.setdefault((r.liga, r.local_fd, r.visitante_fd), []).append(r)

    filas = []
    for a in alertas.to_dict("records"):
        a = dict(a)
        a.update({"estado": "pendiente", "resultado": "", "pin_cierre": np.nan,
                  "clv_pct": np.nan, "gano": np.nan, "ganancia": np.nan})
        kickoff = pd.to_datetime(a["kickoff_utc"])
        cands = [r for r in idx.get((a["liga"], a["local_fd"], a["visitante_fd"]), [])
                 if abs((r.fecha.normalize() - kickoff.normalize()).days) <= 1]
        if cands:
            r = cands[0]
            s = a["salida"]
            a["estado"] = "liquidada"
            a["resultado"] = r.resultado
            a["gano"] = int(r.resultado == s)
            a["ganancia"] = round(a["cuota"] - 1 if a["gano"] else -1.0, 4)
            p = fair_power([r.pc_H, r.pc_D, r.pc_A])
            if p is not None:
                a["pin_cierre"] = getattr(r, f"pc_{s}")
                a["clv_pct"] = round((a["cuota"] * dict(zip("HDA", p))[s] - 1) * 100, 2)
        filas.append(a)
    return pd.DataFrame(filas)


# ──────────────────────────── reporte ────────────────────────────
def _linea(g):
    n = len(g)
    if n == 0:
        return "    0 ap"
    roi = g["ganancia"].mean() * 100
    se = g["ganancia"].std(ddof=1) / math.sqrt(n) * 100 if n > 1 else float("nan")
    c = g["clv_pct"].dropna()
    cse = c.std(ddof=1) / math.sqrt(len(c)) if len(c) > 1 else float("nan")
    return (f"{n:5d} ap | acierto {g['gano'].mean()*100:5.1f}% | cuota {g['cuota'].mean():5.2f} | "
            f"CLV {c.mean():+5.2f}% (±{1.96*cse:.2f}) | ROI {roi:+6.1f}% (±{1.96*se:.1f})")


def reporte(df):
    sep = "=" * 100
    liq = df[df["estado"] == "liquidada"]
    print(sep); print("PAPER TRADING  -  Pinnacle como precio justo  (stake fijo 1 unidad)"); print(sep)
    print(f"Alertas: {len(df)}  |  liquidadas: {len(liq)}  |  pendientes: {(df['estado'] == 'pendiente').sum()}")
    if len(liq) == 0:
        print("\nTodavia no hay alertas liquidadas (football-data no publico esos partidos).")
        return
    print("\nCLV = lo que importa (positivo sostenido = edge real). El ROI con pocas apuestas es ruido.\n")
    print("   TOTAL               ", _linea(liq))
    for titulo, col in (("por casa", "casa"), ("por liga", "liga")):
        print(f"\n  -- {titulo} --")
        for k, g in liq.groupby(col):
            print(f"   {str(k):20}", _linea(g))
    print("\n  -- por valor al capturar --")
    for u in (0, 2, 4, 6):
        print(f"   valor > {u}%           ", _linea(liq[liq["valor_pct"] > u]))

    # Pendientes viejas = probable nombre de equipo sin mapear
    pend = df[df["estado"] == "pendiente"].copy()
    pend["kick"] = pd.to_datetime(pend["kickoff_utc"])
    viejas = pend[pend["kick"] < pd.Timestamp.now() - pd.Timedelta(days=10)]
    if len(viejas):
        print("\n[revisar] Partidos de hace mas de 10 dias sin cruzar (nombre a agregar en data/team_names.py?):")
        for _, r in viejas.drop_duplicates(["local", "visitante"]).iterrows():
            print(f"   {r['kickoff_utc'][:10]} {r['liga']:18} {r['local']} -> {r['local_fd']}  vs  "
                  f"{r['visitante']} -> {r['visitante_fd']}")


def main():
    if not ALERTAS.exists():
        print("No existe paper/alertas.csv: primero corre paper\\capture.py")
        sys.exit(1)
    alertas = pd.read_csv(ALERTAS)
    print(f"Alertas leidas: {len(alertas)}. Bajando resultados de football-data...")
    res = cargar_resultados()
    print(f"   {len(res)} partidos de la temporada con resultado\n")
    df = liquidar(alertas, res)
    df.to_csv(RESULTADOS, index=False)
    reporte(df)
    print(f"\nDetalle guardado en {RESULTADOS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
