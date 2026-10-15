# -*- coding: utf-8 -*-
"""
paper/capture.py  -  ValueBet Analyzer: paper trading, parte 1 (capturar alertas).
NO apuesta nada y NO toca la app. Solo anota.

Que hace:
  1. Pide a The Odds API las cuotas 1X2 de las 8 ligas entrenadas (region eu, que trae Pinnacle).
  2. A Pinnacle le quita el margen (metodo potencia, igual que backtest_pinnacle.py) = precio justo.
  3. Si otra casa paga mas que ese precio justo (valor entre 0% y 15%, cuota 1.30 a 5.00)
     y el partido empieza dentro de 1 a 72 horas, anota la alerta en paper/alertas.csv.
  4. Cada alerta (partido + casa + salida) se anota UNA sola vez: la primera vez que aparece,
     como si en ese momento hubiéramos apostado.

La cuota de cierre de Pinnacle la completa despues paper/settle.py con football-data.co.uk
(sin gastar creditos), y ahi se mide el CLV.

Costo: 1 credito por liga y por corrida = 8 creditos por corrida (solo mercado h2h).

Uso (desde la carpeta del proyecto, en PowerShell):
    $env:ODDS_API_KEY = "tu_api_key"
    py -3.11 paper\\capture.py
"""
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from data.team_names import canon_team  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

OUT_FILE = ROOT / "paper" / "alertas.csv"

# Las 8 ligas con datos de cierre en football-data (mismas que el backtest)
LIGAS = {
    "soccer_epl":                        "Premier League",
    "soccer_spain_la_liga":              "La Liga",
    "soccer_italy_serie_a":              "Serie A",
    "soccer_germany_bundesliga":         "Bundesliga",
    "soccer_france_ligue_one":           "Ligue 1",
    "soccer_belgium_first_div":          "Belgium First Div",
    "soccer_argentina_primera_division": "Liga Argentina",
    "soccer_brazil_campeonato":          "Brazil Serie A",
}

MIN_VALOR, MAX_VALOR = 0.0, 0.15     # se anota todo valor > 0; los umbrales se eligen despues
MIN_ODD, MAX_ODD = 1.30, 5.00        # cuotas 5-10 dieron CLV negativo en el backtest
VENTANA_H = (1, 72)                  # horas hasta el inicio del partido

COLUMNAS = ["capturado_utc", "kickoff_utc", "liga", "local", "visitante",
            "local_fd", "visitante_fd", "salida", "casa", "cuota",
            "pin_cuota", "pin_margen_pct", "p_justa", "valor_pct", "event_id"]


def fair_power(odds):
    """Quita el margen con el metodo POTENCIA (copia de backtest_pinnacle._fair)."""
    if any(not (isinstance(x, (int, float)) and x > 1) for x in odds):
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


def _h2h(bookmaker, home, away):
    """Devuelve {'H':cuota, 'D':cuota, 'A':cuota} de una casa, o None."""
    for m in bookmaker.get("markets", []):
        if m.get("key") != "h2h":
            continue
        o = {x.get("name"): x.get("price") for x in m.get("outcomes", [])}
        res = {"H": o.get(home), "D": o.get("Draw"), "A": o.get(away)}
        if all(isinstance(v, (int, float)) for v in res.values()):
            return res
    return None


def alertas_de_evento(ev, liga, ahora):
    """Todas las alertas de un partido (lista de dicts con COLUMNAS)."""
    try:
        kickoff = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
    except Exception:
        return []
    horas = (kickoff - ahora).total_seconds() / 3600
    if not (VENTANA_H[0] <= horas <= VENTANA_H[1]):
        return []

    home, away = ev.get("home_team", ""), ev.get("away_team", "")
    casas = {bk.get("key"): _h2h(bk, home, away) for bk in ev.get("bookmakers", [])}
    pin = casas.pop("pinnacle", None)
    if not pin:
        return []
    p = fair_power([pin["H"], pin["D"], pin["A"]])
    if p is None:
        return []
    p_justa = dict(zip("HDA", p))
    margen = sum(1 / pin[s] for s in "HDA") - 1

    out = []
    for casa, cuotas in casas.items():
        if not cuotas:
            continue
        for s in "HDA":
            cuota = cuotas[s]
            if not (MIN_ODD <= cuota <= MAX_ODD):
                continue
            valor = cuota * p_justa[s] - 1
            if not (MIN_VALOR < valor <= MAX_VALOR):
                continue
            out.append({
                "capturado_utc": ahora.strftime("%Y-%m-%d %H:%M"),
                "kickoff_utc": kickoff.strftime("%Y-%m-%d %H:%M"),
                "liga": liga, "local": home, "visitante": away,
                "local_fd": canon_team(home), "visitante_fd": canon_team(away),
                "salida": s, "casa": casa, "cuota": cuota,
                "pin_cuota": pin[s], "pin_margen_pct": round(margen * 100, 2),
                "p_justa": round(float(p_justa[s]), 4),
                "valor_pct": round(float(valor) * 100, 2), "event_id": ev.get("id", ""),
            })
    return out


def _ya_anotadas():
    if not OUT_FILE.exists():
        return set()
    with open(OUT_FILE, newline="", encoding="utf-8") as f:
        return {(r["event_id"], r["casa"], r["salida"]) for r in csv.DictReader(f)}


def main():
    key = os.getenv("ODDS_API_KEY", "").strip()
    if not key:
        print("Falta la API key. En PowerShell:  $env:ODDS_API_KEY = \"tu_api_key\"")
        sys.exit(1)

    ahora = datetime.now(timezone.utc)
    vistas = _ya_anotadas()
    nuevas, restantes = [], None

    for sport_key, liga in LIGAS.items():
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds",
                params={"apiKey": key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"},
                timeout=20,
            )
        except Exception as e:
            print(f"   {liga:18} error de conexion: {e}")
            continue
        restantes = r.headers.get("x-requests-remaining", restantes)
        if r.status_code != 200:
            print(f"   {liga:18} HTTP {r.status_code}: {r.text[:120]}")
            continue
        eventos = r.json()
        n_liga, con_pin = 0, 0
        for ev in eventos:
            if any(b.get("key") == "pinnacle" for b in ev.get("bookmakers", [])):
                con_pin += 1
            for a in alertas_de_evento(ev, liga, ahora):
                k = (a["event_id"], a["casa"], a["salida"])
                if k in vistas:
                    continue
                vistas.add(k)
                nuevas.append(a)
                n_liga += 1
        print(f"   {liga:18} {len(eventos):3d} partidos ({con_pin} con Pinnacle) -> {n_liga} alertas nuevas")

    if nuevas:
        OUT_FILE.parent.mkdir(exist_ok=True)
        nuevo = not OUT_FILE.exists()
        with open(OUT_FILE, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNAS)
            if nuevo:
                w.writeheader()
            w.writerows(nuevas)

    print(f"\nAlertas nuevas: {len(nuevas)}  |  guardadas en {OUT_FILE.relative_to(ROOT)}")
    if restantes is not None:
        print(f"Creditos que quedan en The Odds API: {restantes}")


if __name__ == "__main__":
    main()
