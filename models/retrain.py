"""
retrain.py
==========
Re-entrenamiento automático del modelo Poisson/Dixon-Coles.
Usa get_historical_matches() igual que el arranque normal de la app.
"""

import logging
import threading
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# ── Estado global ────────────────────────────────────────────
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

        # Usar el mismo metodo que usa el arranque normal
        df = fetcher.get_historical_matches(600)

        if df is None or len(df) < 100:
            raise ValueError(f"Datos insuficientes para re-entrenar ({len(df) if df is not None else 0} partidos)")

        log.info(f"[Retrain] {len(df)} partidos obtenidos de {df['league'].nunique()} ligas")

        # Re-entrenar Poisson/Dixon-Coles
        poisson_model.fit(df)
        log.info(f"[Retrain] Poisson re-entrenado. rho={poisson_model.rho:.4f}")

        # Re-entrenar modelo logistico
        features, labels = _build_logistic_features(df, poisson_model)
        if len(features) >= 50:
            logistic_model.fit(features, labels)
            log.info(f"[Retrain] Logistic re-entrenado con {len(features)} muestras")

        # Re-calibrar Platt Scaling
        if len(features) >= 50:
            calibrator.calibrate(poisson_model, df)
            log.info("[Retrain] Calibrador re-entrenado")

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

        log.info(f"[Retrain] Completado en {elapsed:.1f}s — {len(df)} partidos, rho={poisson_model.rho:.4f}")
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


def _build_logistic_features(df, poisson_model):
    features, labels = [], []
    for _, row in df.iterrows():
        try:
            probs = poisson_model.predict_proba(
                row["home_team"], row["away_team"], row["league"]
            )
            features.append([
                probs.get("home", 0.33),
                probs.get("draw", 0.33),
                probs.get("away", 0.33),
            ])
            if row["home_goals"] > row["away_goals"]:
                labels.append(0)
            elif row["home_goals"] == row["away_goals"]:
                labels.append(1)
            else:
                labels.append(2)
        except Exception:
            continue
    return features, labels
