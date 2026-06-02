"""
API REST â€“ ProducciÃ³n (Railway)
================================
- CORS configurado para aceptar el dominio de Vercel
- Variables de entorno para API keys
- Entrenamiento al startup (con cache en disco)
- Compatible con Gunicorn
"""

import os, sys, logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data.fetcher import DataFetcher
from models.engine import PoissonModel, LogisticModel, ValueBetDetector, ArbitrageDetector, ProbabilityCalibrator
from database.db import init_db, create_user_settings_table
from models.retrain import run_retrain_async, get_retrain_status
from database.models import get_bankroll, update_bankroll, save_alerts, get_alerts_history, get_bets, get_bet_stats, save_bet, resolve_bet, update_bet_result, delete_bet, get_settings, save_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

import sys as _sys
STATIC_DIR = str(Path(_sys.executable).parent / "static") if getattr(_sys, "frozen", False) else str(Path(__file__).parent.parent / "static")
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/")
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    os.getenv("FRONTEND_URL", "*"),
]
CORS(app, origins=ALLOWED_ORIGINS)

# Inicializar PostgreSQL
_db_available = False
try:
    init_db()
    create_user_settings_table()
    _db_available = True
    log.info('PostgreSQL conectado correctamente')
except Exception as _e:
    log.warning(f'Sin PostgreSQL, usando memoria: {_e}')

_state = {
    "alerts": None, "predictions": None, "arb": [],
    "bankroll": get_bankroll() if _db_available else float(os.getenv("INITIAL_BANKROLL", "1000")),
}

def _get_matches_with_real_odds() -> list:
    """
    Obtiene partidos FUTUROS de The Odds API con cuotas reales.
    Solo incluye partidos con al menos 1 hora para apostar.
    """
    from datetime import datetime, timezone, timedelta
    import requests as _req

    odds_key = os.getenv("ODDS_API_KEY", "")
    if not odds_key:
        return []

    sport_keys = [
        "soccer_conmebol_copa_libertadores",
        "soccer_conmebol_copa_sudamericana",
        "soccer_brazil_campeonato",
        "soccer_argentina_primera_division",
        "soccer_chile_campeonato",
        "soccer_france_ligue_one",
        "soccer_uefa_champs_league",
        "soccer_uefa_europa_league",
        "soccer_belgium_first_div",
        "soccer_epl",
        "soccer_spain_la_liga",
        "soccer_italy_serie_a",
        "soccer_germany_bundesliga",
    ]
    sport_key_to_league = {
        "soccer_conmebol_copa_libertadores": "Copa Libertadores",
        "soccer_conmebol_copa_sudamericana": "Copa Sudamericana",
        "soccer_brazil_campeonato":          "Brazil Serie A",
        "soccer_argentina_primera_division": "Liga Argentina",
        "soccer_chile_campeonato":           "Chile Primera",
        "soccer_france_ligue_one":           "Ligue 1",
        "soccer_uefa_champs_league":         "Champions League",
        "soccer_uefa_europa_league":         "Europa League",
        "soccer_belgium_first_div":          "Belgium First Div",
        "soccer_epl":                        "Premier League",
        "soccer_spain_la_liga":              "La Liga",
        "soccer_italy_serie_a":              "Serie A",
        "soccer_germany_bundesliga":         "Bundesliga",
    }
    bookmaker_urls = {
        "bet365": "https://www.bet365.com", "betway": "https://betway.com.ar",
        "1xbet": "https://1xbet.com", "unibet": "https://www.unibet.com",
        "pinnacle": "https://www.pinnacle.com", "marathonbet": "https://www.marathonbet.com",
        "williamhill": "https://www.williamhill.com", "betfair": "https://www.betfair.com",
        "betsson": "https://www.betsson.com", "sport888": "https://www.888sport.com",
        "nordicbet": "https://www.nordicbet.com", "betclic": "https://www.betclic.com",
    }
    bookmaker_names = {
        "bet365": "Bet365", "betway": "Betway", "1xbet": "1xBet",
        "unibet": "Unibet", "pinnacle": "Pinnacle", "marathonbet": "MarathonBet",
        "williamhill": "William Hill", "betfair": "Betfair", "betsson": "Betsson",
        "sport888": "888sport", "nordicbet": "NordicBet", "betclic": "Betclic",
    }

    now = datetime.now(timezone.utc)
    min_kickoff = now + timedelta(hours=1)
    matches = []

    for sport_key in sport_keys:
        try:
            r = _req.get(
                f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds",
                params={"apiKey": odds_key, "regions": "eu", "markets": "h2h,totals", "oddsFormat": "decimal"},
                timeout=10,
            )
            if r.status_code != 200:
                continue
            for event in r.json():
                try:
                    kickoff = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
                except Exception:
                    continue
                if kickoff < min_kickoff:
                    continue
                home   = event.get("home_team", "")
                away   = event.get("away_team", "")
                league = sport_key_to_league.get(sport_key, sport_key)
                best = {}
                for bk in event.get("bookmakers", []):
                    bk_key  = bk.get("key", "")
                    bk_name = bookmaker_names.get(bk_key, bk.get("title", bk_key))
                    bk_url  = bookmaker_urls.get(bk_key, f"https://www.google.com/search?q={bk_name}+apuestas")
                    for market in bk.get("markets", []):
                        mkey = market.get("key")
                        outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
                        if mkey == "h2h":
                            for team, field in [(home, "odd_home"), ("Draw", "odd_draw"), (away, "odd_away")]:
                                val = outcomes.get(team)
                                if val and val > best.get(field, {}).get("odd", 0):
                                    best[field] = {"odd": val, "bk_key": bk_key, "bk_name": bk_name, "bk_url": bk_url}
                        elif mkey == "totals":
                            for o in market.get("outcomes", []):
                                if o.get("point") == 2.5:
                                    field = "odd_over25" if o["name"] == "Over" else "odd_under25"
                                    if o["price"] > best.get(field, {}).get("odd", 0):
                                        best[field] = {"odd": o["price"], "bk_key": bk_key, "bk_name": bk_name, "bk_url": bk_url}
                bk_ref = best.get("odd_home") or best.get("odd_over25")
                if not bk_ref:
                    continue
                matches.append({
                    "home_team": home, "away_team": away,
                    "match_id":  f"{home}_{away}",
                    "league":    league,
                    "kickoff":   event["commence_time"],
                    "simulated": False,
                    "real_odds": {
                        "odd_home":    best.get("odd_home",    {}).get("odd"),
                        "odd_draw":    best.get("odd_draw",    {}).get("odd") or 3.4,
                        "odd_away":    best.get("odd_away",    {}).get("odd"),
                        "odd_over25":  best.get("odd_over25",  {}).get("odd") or 1.9,
                        "odd_under25": best.get("odd_under25", {}).get("odd") or 1.9,
                        "bookmaker":      bk_ref["bk_key"],
                        "bookmaker_name": bk_ref["bk_name"],
                        "bookmaker_url":  bk_ref["bk_url"],
                        "best_by_market": best,
                    },
                })
        except Exception as e:
            log.warning(f"[OddsAPI] Error en {sport_key}: {e}")

    log.info(f"[OddsAPI] {len(matches)} partidos futuros con cuotas reales")
    return matches


def _train_and_analyze():
    global pm, lm, cal, fetcher
    log.info("Entrenando modelos...")
    fetcher = DataFetcher()
    df      = fetcher.get_historical_matches(400)
    pm = PoissonModel(); pm.fit(df)
    lm = LogisticModel(); lm.fit(df)

    cal = ProbabilityCalibrator()
    proba_list, results = [], []
    for _, row in df.iterrows():
        if "result" in row and row["result"] in ("H", "D", "A"):
            p = pm.predict_proba(row["home_team"], row["away_team"], row["league"])
            proba_list.append(p)
            results.append(row["result"])
    cal.fit(proba_list, results)

    det     = ValueBetDetector()
    arb_det = ArbitrageDetector()

    # Fuente principal: The Odds API (partidos reales + cuotas)
    real_matches = _get_matches_with_real_odds()
    if real_matches:
        upcoming = real_matches
        log.info(f"[OddsAPI] Usando {len(upcoming)} partidos reales")
    else:
        upcoming = fetcher.get_upcoming_matches()
        log.info(f"[Fallback] Usando {len(upcoming)} partidos simulados/APISPORTS")

    all_alerts, all_preds, arbs = [], [], []
    for match in upcoming:
        pred = pm.predict_proba(match["home_team"], match["away_team"], match["league"])
        form_home = pred.get("form_home", {})
        form_away = pred.get("form_away", {})
        h2h       = pred.get("h2h", {})
        pred_lr = lm.predict_proba(
            match["home_team"], match["away_team"],
            pred["lambda_home"], pred["lambda_away"],
            form_att_home=form_home.get("form_factor_att", 1.0),
            form_att_away=form_away.get("form_factor_att", 1.0),
            h2h_home_wr=h2h.get("home_win_rate", 0.33),
            h2h_away_wr=h2h.get("away_win_rate", 0.33),
        )
        if pred_lr:
            ph = pred["p_home"]*0.6 + pred_lr["lr_p_home"]*0.4
            pd = pred["p_draw"]*0.6 + pred_lr["lr_p_draw"]*0.4
            pa = pred["p_away"]*0.6 + pred_lr["lr_p_away"]*0.4
            t  = ph+pd+pa
            pred.update({"p_home": round(ph/t,4), "p_draw": round(pd/t,4), "p_away": round(pa/t,4)})
        pred = cal.calibrate(pred)
        match_enriched = {**match, "form_home": form_home, "form_away": form_away, "h2h": h2h}
        real_odds = match.get("real_odds")

        if real_odds and real_odds.get("odd_home"):
            best_by_market = real_odds.get("best_by_market", {})
            closing_base = {
                "odd_home":    real_odds.get("odd_home"),
                "odd_draw":    real_odds.get("odd_draw") or 3.4,
                "odd_away":    real_odds.get("odd_away"),
                "odd_over25":  real_odds.get("odd_over25") or 1.9,
                "odd_under25": real_odds.get("odd_under25") or 1.9,
                "bookmaker":   real_odds["bookmaker"],
            }
            closing_odds = fetcher.get_closing_odds(match, closing_base, pred)
            market_map = {
                "1X2_H": "odd_home", "1X2_D": "odd_draw", "1X2_A": "odd_away",
                "OVER25": "odd_over25", "UNDER25": "odd_under25",
            }
            for market_id, odd_field in market_map.items():
                bk_info = best_by_market.get(odd_field)
                if not bk_info:
                    continue
                market_odds = {
                    **closing_base,
                    "bookmaker":      bk_info["bk_key"],
                    "bookmaker_name": bk_info["bk_name"],
                    "bookmaker_url":  bk_info["bk_url"],
                }
                for a in det.detect(pred, market_odds, match_enriched, closing_odds):
                    if a.get("market") == market_id:
                        all_alerts.append(a)
            arb = arb_det.detect_arb([closing_base])
        else:
            sim = fetcher.get_simulated_odds(match)
            odds_list = [{**sim, "bookmaker_name": "Simulado", "bookmaker_url": ""}]
            closing_odds = fetcher.get_closing_odds(match, odds_list[0], pred)
            for odds in odds_list:
                all_alerts.extend(det.detect(pred, odds, match_enriched, closing_odds))
            arb = arb_det.detect_arb(odds_list)

        if arb:
            arbs.append({**arb, "match": f"{match['home_team']} vs {match['away_team']}", "league": match["league"]})
        all_preds.append({**match, **pred})

    seen = {}
    for a in sorted(all_alerts, key=lambda x: x["edge_pct"], reverse=True):
        k = f"{a['match_id']}_{a['market']}"
        if k not in seen: seen[k] = a
    _state["alerts"]      = sorted(seen.values(), key=lambda x: x["edge_pct"], reverse=True)
    _state["predictions"] = all_preds
    _state["arb"]         = arbs
    log.info(f"Listo: {len(_state['alerts'])} VBs, {len(arbs)} arbitrajes.")

_train_and_analyze()

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "alerts": len(_state["alerts"] or []), "version": "1.1.0"})

@app.route("/api/data-sources")
def data_sources():
    """Estado real de cada fuente de datos segun env vars y conectividad."""
    import requests as _req

    sources = []

    # 1. Datos historicos (siempre activo)
    sources.append({
        "name": "Datos historicos de partidos",
        "status": "active",
        "label": "Activo",
        "detail": "Datos sinteticos generados con distribucion Poisson",
        "matches": len(_state.get("predictions") or []),
    })

    # 2. The Odds API
    odds_key = os.getenv("ODDS_API_KEY") or os.getenv("THE_ODDS_API_KEY")
    sources.append({
        "name": "The Odds API (cuotas reales)",
        "status": "active" if odds_key else "inactive",
        "label": "Activa" if odds_key else "Sin configurar",
        "detail": "500 solicitudes/mes en plan gratuito",
    })

    # 3. API-Football / APISPORTS
    apisports_key = os.getenv("APISPORTS_KEY") or os.getenv("API_FOOTBALL_KEY")
    sources.append({
        "name": "API-Football (estadisticas)",
        "status": "active" if apisports_key else "inactive",
        "label": "Activa" if apisports_key else "Sin configurar",
        "detail": "100 solicitudes/dia - partidos reales conectados",
    })

    # 4. OpenWeatherMap — verificar con llamada real
    weather_key = os.getenv("OPENWEATHER_KEY") or os.getenv("OPENWEATHERMAP_KEY")
    weather_ok = False
    if weather_key:
        try:
            r = _req.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"lat": -34.6, "lon": -58.4, "appid": weather_key},
                timeout=5
            )
            weather_ok = r.status_code == 200
        except Exception:
            weather_ok = False
    sources.append({
        "name": "OpenWeatherMap (clima)",
        "status": "active" if weather_ok else ("pending" if weather_key else "inactive"),
        "label": "Activa" if weather_ok else ("Key configurada" if weather_key else "Sin configurar"),
        "detail": "1000 solicitudes/dia en plan gratuito",
    })

    # 5. PostgreSQL
    sources.append({
        "name": "PostgreSQL (base de datos)",
        "status": "active" if _db_available else "inactive",
        "label": "Conectada" if _db_available else "No disponible",
        "detail": "Historial de apuestas, bankroll y configuracion",
    })

    return jsonify({"sources": sources})

@app.route("/api/alerts")
def get_alerts():
    alerts   = list(_state["alerts"] or [])
    league   = request.args.get("league")
    conf     = request.args.get("confidence")
    min_edge = float(request.args.get("min_edge", 0))
    if league:   alerts = [a for a in alerts if a["league"].lower() == league.lower()]
    if conf:     alerts = [a for a in alerts if a["confidence"] == conf.upper()]
    alerts = [a for a in alerts if a["edge_pct"] >= min_edge]
    return jsonify({"count": len(alerts), "alerts": alerts})

@app.route("/api/predictions")
def get_predictions():
    preds  = list(_state["predictions"] or [])
    league = request.args.get("league")
    if league: preds = [p for p in preds if p["league"].lower() == league.lower()]
    return jsonify({"count": len(preds), "predictions": preds})

@app.route("/api/arbitrage")
def get_arbitrage():
    return jsonify({"count": len(_state["arb"]), "opportunities": _state["arb"]})

@app.route("/api/bankroll", methods=["GET","POST"])
def bankroll():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        _state["bankroll"] = float(data.get("bankroll", _state["bankroll"]))
    bk = _state["bankroll"]
    alerts = _state["alerts"] or []
    exp = min(sum(a["kelly_frac"] for a in alerts[:10]), 0.20) * bk
    return jsonify({"bankroll": bk, "suggested_exposure": round(exp,2),
                    "max_exposure_pct": 20.0, "active_alerts": len(alerts),
                    "avg_edge": round(sum(a["edge_pct"] for a in alerts)/max(len(alerts),1), 2)})

def _enrich_with_real_odds():
    """Enriquece las alertas actuales con cuotas reales de The Odds API."""
    if not _state["alerts"]:
        return
    # Agrupar alertas por partido para minimizar llamadas API
    matches_seen = {}
    for alert in _state["alerts"]:
        mid = alert["match_id"]
        if mid not in matches_seen:
            matches_seen[mid] = {
                "home_team": alert["home_team"],
                "away_team": alert["away_team"],
                "league":    alert["league"],
                "match_id":  mid,
            }
    # Obtener cuotas reales por partido
    real_odds_by_match = {}
    for mid, match in matches_seen.items():
        try:
            bk_list = fetcher.get_real_odds_for_match(match)
            if bk_list:
                real_odds_by_match[mid] = bk_list
        except Exception:
            pass
    # Actualizar alertas con el mejor bookmaker por mercado
    market_to_odd = {
        "1X2_H": "odd_home", "1X2_D": "odd_draw", "1X2_A": "odd_away",
        "OVER25": "odd_over25", "UNDER25": "odd_under25",
    }
    updated = []
    for alert in _state["alerts"]:
        mid = alert["match_id"]
        bk_list = real_odds_by_match.get(mid, [])
        odd_key = market_to_odd.get(alert["market"])
        if bk_list and odd_key:
            best_bk = max(
                (b for b in bk_list if b.get(odd_key)),
                key=lambda b: b.get(odd_key, 0),
                default=None
            )
            if best_bk:
                alert = {**alert,
                    "bookmaker":      best_bk.get("bookmaker_key") or best_bk.get("bk_key", "simulated"),
                    "bookmaker_name": best_bk.get("bookmaker_name") or best_bk.get("bk_name", "Bookmaker"),
                    "bookmaker_url":  best_bk.get("bookmaker_url") or best_bk.get("bk_url", ""),
                    "odd":            best_bk[odd_key],
                }
        updated.append(alert)
    _state["alerts"] = sorted(updated, key=lambda x: x["edge_pct"], reverse=True)
    log.info(f"[OddsAPI] Cuotas reales enriquecidas para {len(real_odds_by_match)} partidos")


@app.route("/api/refresh", methods=["POST"])
def refresh():
    _state["alerts"] = None
    _train_and_analyze()
    # Enriquecer alertas con cuotas reales si hay ODDS_API_KEY
    _odds_key = os.getenv("ODDS_API_KEY", "")
    if _odds_key and _state["alerts"]:
        _enrich_with_real_odds()
    return jsonify({"status": "refreshed", "alerts": len(_state["alerts"] or []),
                    "real_odds": bool(_odds_key)})

@app.route("/api/leagues")
def get_leagues():
    return jsonify({"leagues": sorted({a["league"] for a in (_state["alerts"] or [])})})

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/<path:path>")
def static_files(path):
    from flask import send_from_directory
    static_dir = Path(_sys.executable).parent / "static" if getattr(_sys, "frozen", False) else Path(__file__).parent.parent / "static"
    if (static_dir / path).exists():
        return send_from_directory(str(static_dir), path)
    return app.send_static_file("index.html")




@app.route("/api/form-h2h", methods=["GET"])
def form_h2h():
    """
    Retorna datos reales de Forma y H2H para un partido usando API-Sports.
    Query params: home=<equipo>&away=<equipo>&league=<liga>
    Opcionalmente: home_id=<id>&away_id=<id>&league_id=<id>
    """
    home_team = request.args.get("home", "")
    away_team = request.args.get("away", "")
    league    = request.args.get("league", "")
    home_id   = request.args.get("home_id")
    away_id   = request.args.get("away_id")
    league_id = request.args.get("league_id")

    if not home_team or not away_team:
        return jsonify({"error": "Se requieren parámetros home y away", "available": False}), 400

    match = {
        "home_team": home_team,
        "away_team": away_team,
        "league":    league,
    }
    if home_id:   match["home_id"]   = int(home_id)
    if away_id:   match["away_id"]   = int(away_id)
    if league_id: match["league_id"] = int(league_id)

    try:
        result = fetcher.get_form_and_h2h(match)
        return jsonify(result)
    except Exception as e:
        log.error(f"[form-h2h] Error: {e}")
        return jsonify({"error": str(e), "available": False}), 500

@app.route("/api/retrain", methods=["POST"])
def trigger_retrain():
    status = get_retrain_status()
    if status["is_running"]:
        return jsonify({"message": "Ya en curso", "status": status}), 409
    run_retrain_async(pm, lm, cal, fetcher)
    return jsonify({"message": "Iniciado", "status": status})

@app.route("/api/retrain/status", methods=["GET"])
def retrain_status():
    return jsonify(get_retrain_status())

if __name__ == "__main__":
    import threading, webbrowser
    port = int(os.getenv("PORT", 5050))
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{port}")
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=port, debug=False)

from analysis.backtesting import run_backtest, walk_forward_validation

@app.route("/api/backtest", methods=["GET"])
def backtest():
    league = request.args.get("league", "Premier League")
    bankroll = float(request.args.get("bankroll", 1000))
    min_edge = float(request.args.get("min_edge", 0.05))
    result = run_backtest(league, initial_bankroll=bankroll, min_edge=min_edge)
    return jsonify(result)

@app.route("/api/backtest/leagues", methods=["GET"])
def backtest_leagues():
    from analysis.backtesting import LEAGUES
    return jsonify({"leagues": list(LEAGUES.keys())})

from analysis.tennis import analyze_tennis, TOUR_URLS
from analysis.basketball import analyze_basketball, LEAGUES as BBALL_LEAGUES

@app.route("/api/tennis", methods=["GET"])
def tennis():
    tour = request.args.get("tour", "ATP 2024")
    min_edge = float(request.args.get("min_edge", 0.05))
    result = analyze_tennis(tour=tour, min_edge=min_edge)
    return jsonify(result)

@app.route("/api/tennis/tours", methods=["GET"])
def tennis_tours():
    return jsonify({"tours": list(TOUR_URLS.keys())})

@app.route("/api/basketball", methods=["GET"])
def basketball():
    league = request.args.get("league", "NBA")
    min_edge = float(request.args.get("min_edge", 0.05))
    result = analyze_basketball(league=league, min_edge=min_edge)
    return jsonify(result)

@app.route("/api/basketball/leagues", methods=["GET"])
def basketball_leagues():
    return jsonify({"leagues": list(BBALL_LEAGUES.keys())})

from data.real_odds import get_real_alerts, SUPPORTED_LEAGUES

@app.route("/api/real-odds", methods=["GET"])
def real_odds():
    league = request.args.get("league", "Liga Argentina")
    min_edge = float(request.args.get("min_edge", 0.03))
    result = get_real_alerts(league_name=league, min_edge=min_edge)
    return jsonify(result)

@app.route("/api/real-odds/leagues", methods=["GET"])
def real_odds_leagues():
    return jsonify({"leagues": list(SUPPORTED_LEAGUES.keys())})

from notifications.telegram import send_value_bets, send_test as telegram_test

@app.route("/api/telegram/test", methods=["POST"])
def telegram_test_endpoint():
    result = telegram_test()
    return jsonify(result)

@app.route("/api/telegram/send", methods=["POST"])
def telegram_send():
    data = request.get_json(silent=True) or {}
    min_edge = float(data.get("min_edge", 10.0))
    alerts = _state.get("alerts") or []
    result = send_value_bets(alerts, min_edge=min_edge)
    return jsonify(result)

@app.route("/api/backtest/walk-forward", methods=["GET"])
def backtest_walk_forward():
    league_name     = request.args.get("league", "Premier League")
    window_months   = int(request.args.get("window_months", 3))
    step_months     = int(request.args.get("step_months", 1))
    min_edge        = float(request.args.get("min_edge", 0.05))
    initial_bankroll = float(request.args.get("bankroll", 1000.0))
    result = walk_forward_validation(
        league_name=league_name,
        window_months=window_months,
        step_months=step_months,
        min_edge=min_edge,
        initial_bankroll=initial_bankroll,
    )
    return jsonify(result)


# ENDPOINTS DE BASE DE DATOS

@app.route('/api/bets', methods=['GET'])
def list_bets():
    if not _db_available:
        return jsonify({'error': 'DB no disponible'}), 503
    result_filter = request.args.get('result')
    limit = int(request.args.get('limit', 50))
    bets = get_bets(limit=limit, result_filter=result_filter)
    for b in bets:
        for k, v in b.items():
            if hasattr(v, 'isoformat'):
                b[k] = v.isoformat()
    return jsonify({'bets': bets})

@app.route('/api/bets', methods=['POST'])
def create_bet():
    if not _db_available:
        return jsonify({'error': 'DB no disponible'}), 503
    data = request.get_json(silent=True) or {}
    bet_id = save_bet(
        home_team=data.get('home_team', ''),
        away_team=data.get('away_team', ''),
        league=data.get('league', ''),
        bet_type=data.get('bet_type', 'home'),
        odds=float(data.get('odds', 0)),
        edge=float(data.get('edge', 0)),
        kelly_stake=float(data.get('kelly_stake', 0)),
        amount_bet=float(data.get('amount_bet', 0)),
        match_date=data.get('match_date'),
    )
    return jsonify({'bet_id': bet_id, 'status': 'saved'})

@app.route('/api/bets/<int:bet_id>/resolve', methods=['POST'])
def resolve_bet_endpoint(bet_id):
    if not _db_available:
        return jsonify({'error': 'DB no disponible'}), 503
    data = request.get_json(silent=True) or {}
    result = data.get('result')
    if result not in ('win', 'loss'):
        return jsonify({'error': 'result debe ser win o loss'}), 400
    profit = resolve_bet(bet_id, result)
    new_bankroll = get_bankroll()
    _state['bankroll'] = new_bankroll
    return jsonify({'profit': profit, 'new_bankroll': new_bankroll})

@app.route('/api/stats', methods=['GET'])
def bet_stats():
    if not _db_available:
        return jsonify({'error': 'DB no disponible'}), 503
    stats = get_bet_stats()
    bankroll = get_bankroll()
    for k, v in stats.items():
        if hasattr(v, '__float__'):
            stats[k] = float(v)
    return jsonify({**stats, 'current_bankroll': bankroll})

@app.route('/api/alerts/history', methods=['GET'])
def alerts_history():
    if not _db_available:
        return jsonify({'error': 'DB no disponible'}), 503
    limit = int(request.args.get('limit', 100))
    history = get_alerts_history(limit=limit)
    for h in history:
        for k, v in h.items():
            if hasattr(v, 'isoformat'):
                h[k] = v.isoformat()
    return jsonify({'alerts': history})

    # SETTINGS

@app.route('/api/settings', methods=['GET'])
def get_settings_endpoint():
    try:
        data = get_settings()
        return jsonify(data)
    except Exception as e:
        return jsonify({}), 200

@app.route('/api/settings', methods=['POST'])
def save_settings_endpoint():
    try:
        data = request.get_json(silent=True) or {}
        save_settings(data)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
