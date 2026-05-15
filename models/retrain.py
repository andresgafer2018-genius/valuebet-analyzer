"""
retrain.py
==========
Re-entrenamiento automatico del modelo Poisson/Dixon-Coles.
Usa get_historical_matches() igual que el arranque normal de la app.
El status se persiste en PostgreSQL para sobrevivir reinicios de Fly.io.
"""

import logging
import threading
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# ── Status in-memory (fallback si no hay DB) ───────────────────────────────
_retrain_status = {
    "last_retrain": None,
    "last_error":   None,
    "is_running":   False,
    "total_runs":   0,
    "last_metrics": {},
}
_retrain_lock = threading.Lock()

# ── Helpers DB (importación diferida para evitar circular imports) ──────────

def _db_get() -> dict:
    try:
        from database.db import get_retrain_status_db
        return get_retrain_status_db()
    except Exception:
        return {}

def _db_update(**kwargs):
    try:
        from database.db import update_retrain_status_db
        update_retrain_status_db(**kwargs)
    except Exception as e:
        log.warning(f"[Retrain] No se pudo persistir status en DB: {e}")


def get_retrain_status() -> dict:
    """
    Devuelve el status actual.
    Si hay DB disponible, combina DB (persistente) + memoria (is_running en vivo).
    """
    with _retrain_lock:
        mem = dict(_retrain_status)

    # Intentar enriquecer con datos persistidos en DB
    db_status = _db_get()
    if db_status:
        # is_running siempre lo tomamos de memoria (más fresco)
        db_status["is_running"] = mem["is_running"]
        # Si no tenemos historial en memoria pero sí en DB, usamos DB
        if not mem["last_retrain"] and db_status.get("last_retrain"):
            return db_status
        # Si tenemos en memoria, es más fresco
        if mem["last_retrain"]:
            return mem
        return db_status

    return mem


def run_retrain(poisson_model, logistic_model, calibrator, fetcher) -> dict:
    global _retrain_status

    with _retrain_lock:
        if _retrain_status["is_running"]:
            return {"success": False, "message": "Re-entrenamiento ya en curso", "metrics": {}}
        _retrain_status["is_running"] = True

    # Marcar como running también en DB
    _db_update(is_running=True, last_error=None)

    try:
        log.info("[Retrain] Iniciando re-entrenamiento...")
        start_time = datetime.now(timezone.utc)

        # Mismo método que el arranque normal
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

        # Persistir en DB
        _db_update(
            last_retrain=start_time,
            last_error=None,
            is_running=False,
            total_runs=_retrain_status["total_runs"],
            last_metrics=metrics,
        )

        log.info(f"[Retrain] Completado en {elapsed:.1f}s")
        return {"success": True, "message": "Re-entrenamiento exitoso", "metrics": metrics}

    except Exception as e:
        error_msg = str(e)
        log.error(f"[Retrain] Error: {error_msg}")
        with _retrain_lock:
            _retrain_status["last_error"] = error_msg
            _retrain_status["is_running"] = False

        # Persistir error en DB
        _db_update(is_running=False, last_error=error_msg)

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
