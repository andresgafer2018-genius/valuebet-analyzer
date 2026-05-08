"""
API REST – Producción (Railway)
================================
- CORS configurado para aceptar el dominio de Vercel
- Variables de entorno para API keys
- Entrenamiento al startup (con cache en disco)
- Compatible con Gunicorn
"""

import os, sys, logging
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data.fetcher import DataFetcher
from models.engine import PoissonModel, LogisticModel, ValueBetDetector, ArbitrageDetector, ProbabilityCalibrator

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

_state = {
    "alerts": None, "predictions": None, "arb": [],
    "bankroll": float(os.getenv("INITIAL_BANKROLL", "1000")),
}

def _train_and_analyze():
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

        # Mezcla Poisson + LogReg (60/40)
        pred_lr = lm.predict_proba(match["home_team"], match["away_team"], pred["lambda_home"], pred["lambda_away"])
        if pred_lr:
            ph = pred["p_home"]*0.6 + pred_lr["lr_p_home"]*0.4
            pd = pred["p_draw"]*0.6 + pred_lr["lr_p_draw"]*0.4
            pa = pred["p_away"]*0.6 + pred_lr["lr_p_away"]*0.4
            t  = ph+pd+pa
            pred.update({"p_home": round(ph/t,4), "p_draw": round(pd/t,4), "p_away": round(pa/t,4)})

        # Calibración final
        pred = cal.calibrate(pred)

        odds_list = [fetcher.get_simulated_odds(match) for _ in range(3)]
        for odds in odds_list:
            all_alerts.extend(det.detect(pred, odds, match))
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

if __name__ == "__main__":
    import threading, webbrowser
    port = int(os.getenv("PORT", 5050))
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{port}")
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=port, debug=False)

from analysis.backtesting import run_backtest

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
