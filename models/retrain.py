"""
retrain.py
==========
Re-entrenamiento automatico del modelo Poisson/Dixon-Coles.
Usa get_historical_matches() igual que el arranque normal de la app.
"""

import logging
import threading
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_retrain_status = {
    "last_retrain":  None,
    "last_error":    None,
    "is_running":    False,
    "total_runs":    0,
    "last_metrics":  {},
}
_retrain_lock = threading.Lock()


def get_retrain_status() -> dict:
    with _retrain_lock:
        return dict(_retrain_status)


def run_retrain(poisson_model, logistic_model, calibrator, fetcher) -> dict:
    global _retrain_status

    with _retrain_lock:
        if _retrain_status["is_running"]:
            return {"success": False, "message": "Re-entrenamiento ya en curso", "metrics": {}}
        _retrain_status["is_running"] = True

    try:
        log.info("[Retrain] Iniciando re-entrenamiento...")
        start_time = datetime.now(timezone.utc)

        # Mismo metodo que el arranque normal
        df = fetcher.get_historical_matches(600)

        if df is None or len(df) < 100:
            raise ValueError(f"Datos insuficientes ({len(df) if df is not None else 0} partidos)")

        log.info(f"[Retrain] {len(df)} partidos, {df['league'].nunique()} ligas")

        # 1. Re-entrenar Poisson/Dixon-Coles
        poisson_model.fit(df)
        log.info(f"[Retrain] Poisson OK. rho={poisson_model.rho:.4f}")

        # 2. Re-entrenar LogisticModel (acepta df directamente)
        logistic_model.fit(df)
        log.info("[Retrain] Logistic OK")

        # 3. Re-calibrar (acepta proba_list y results)
        proba_list, results = _build_calibration_data(df, poisson_model)
        if len(proba_list) >= 50:
            calibrator.fit(proba_list, results)
            log.info("[Retrain] Calibrador OK")

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        metrics = {
            "total_matches":   int(len(df)),
            "total_leagues":   int(df["league"].nunique()),
            "rho":             round(float(poisson_model.rho), 4),
            "elapsed_seconds": round(elapsed, 1),
            "timestamp":       start_time.isoformat(),
        }

        with _retrain_lock:
            _retrain_status["last_retrain"] = start_time.isoformat()
            _retrain_status["last_error"]   = None
            _retrain_status["total_runs"]  += 1
            _retrain_status["last_metrics"] = metrics
            _retrain_status["is_running"]   = False

        log.info(f"[Retrain] Completado en {elapsed:.1f}s")
        return {"success": True, "message": "Re-entrenamiento exitoso", "metrics": metrics}

    except Exception as e:
        error_msg = str(e)
        log.error(f"[Retrain] Error: {error_msg}")
        with _retrain_lock:
            _retrain_status["last_error"] = error_msg
            _retrain_status["is_running"] = False
        return {"success": False, "message": error_msg, "metrics": {}}


def run_retrain_async(poisson_model, logistic_model, calibrator, fetcher):
    t = threading.Thread(
        target=run_retrain,
        args=(poisson_model, logistic_model, calibrator, fetcher),
        daemon=True,
        name="retrain-worker"
    )
    t.start()
    return t


def _build_calibration_data(df, poisson_model):
    proba_list, results = [], []
    for _, row in df.iterrows():
        try:
            p = poisson_model.predict_proba(
                row["home_team"], row["away_team"], row["league"]
            )
            proba_list.append(p)
            if row["home_goals"] > row["away_goals"]:
                results.append("H")
            elif row["home_goals"] == row["away_goals"]:
                results.append("D")
            else:
                results.append("A")
        except Exception:
            continue
    return proba_list, results
