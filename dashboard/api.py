"""
API REST – Producción (Railway)
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
from database.db import init_db
from models.retrain import run_retrain_async, get_retrain_status
from database.models import get_bankroll, update_bankroll, save_alerts, get_alerts_history, get_bets, get_bet_stats, save_bet, resolve_bet

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
    _db_available = True
    log.info('PostgreSQL conectado correctamente')
except Exception as _e:
    log.warning(f'Sin PostgreSQL, usando memoria: {_e}')

_state = {
    "alerts": None, "predictions": None, "arb": [],
    "bankroll": get_bankroll() if _db_available else float(os.getenv("INITIAL_BANKROLL", "1000")),
}

def _train_and_analyze():
    global pm, lm, cal, fetcher
    log.info("Entrenando modelos...")
    fetcher = DataFetcher()
    df      = fetcher.get_historical_matches(400)
    pm = PoissonModel(); pm.fit(df)
    lm = LogisticModel(); lm.fit(df)

    # Calibración de probabilidades (Platt Scaling)
    cal = ProbabilityCalibrator()
    proba_list = []
    results    = []
    for _, row in df.iterrows():
        if "result" in row and row["result"] in ("H", "D", "A"):
            p = pm.predict_proba(row["home_team"], row["away_team"], row["league"])
            proba_list.append(p)
            results.append(row["result"])
    cal.fit(proba_list, results)

    det     = ValueBetDetector()
    arb_det = ArbitrageDetector()
    upcoming = fetcher.get_upcoming_matches()
    all_alerts, all_preds, arbs = [], [], []
    for match in upcoming:
        pred = pm.predict_proba(match["home_team"], match["away_team"], match["league"])

        # Extraer forma y H2H ya calculados por el Poisson
        form_home = pred.get("form_home", {})
        form_away = pred.get("form_away", {})
        h2h       = pred.get("h2h", {})

        # Mezcla Poisson + LogReg (60/40) con variables adicionales
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

        # Calibración final
        pred = cal.calibrate(pred)

        odds_list = [fetcher.get_simulated_odds(match) for _ in range(3)]
        closing_odds = fetcher.get_closing_odds(match, odds_list[0], pred)
        # Enriquecer match con forma y H2H para que lleguen a las alertas
        match_enriched = {**match, "form_home": form_home, "form_away": form_away, "h2h": h2h}
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

@app.route("/api/refresh", methods=["POST"])
def refresh():
    _state["alerts"] = None
    _train_and_analyze()
    return jsonify({"status": "refreshed", "alerts": len(_state["alerts"] or [])})

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