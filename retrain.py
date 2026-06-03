"""
retrain.py
==========
Lógica de re-entrenamiento automático del modelo Poisson/Dixon-Coles.
Se puede llamar manualmente via endpoint o automáticamente via scheduler.
"""

import os
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np

log = logging.getLogger(__name__)

# ── Estado global del re-entrenamiento ──────────────────────────────────────
_retrain_status = {
    "last_retrain": None,       # datetime del último re-entrenamiento exitoso
    "last_error":   None,       # mensaje del último error
    "is_running":   False,      # True si está corriendo ahora
    "total_runs":   0,
    "last_metrics": {},         # métricas del último entrenamiento
}
_retrain_lock = threading.Lock()


def get_retrain_status() -> dict:
    """Devuelve el estado actual del re-entrenamiento (thread-safe)."""
    with _retrain_lock:
        return dict(_retrain_status)


def _build_training_dataframe(fetcher) -> pd.DataFrame | None:
    """
    Construye el DataFrame de entrenamiento a partir de la API de APISports.
    Retorna None si no hay suficientes datos.
    """
    from data.fetcher import LEAGUE_IDS

    all_fixtures = []

    for league_name, league_id in LEAGUE_IDS.items():
        try:
            # Obtener partidos de la temporada actual y la anterior
            for season in [2024, 2023]:
                fixtures = fetcher.get_fixtures_league(league_id, season=season)
                for f in fixtures:
                    fixture  = f.get("fixture", {})
                    teams    = f.get("teams", {})
                    goals    = f.get("goals", {})
                    status   = fixture.get("status", {}).get("short", "")

                    # Solo partidos finalizados
                    if status not in ("FT", "AET", "PEN"):
                        continue

                    home_goals = goals.get("home")
                    away_goals = goals.get("away")

                    if home_goals is None or away_goals is None:
                        continue

                    all_fixtures.append({
                        "league":     league_name,
                        "home_team":  teams.get("home", {}).get("name", ""),
                        "away_team":  teams.get("away", {}).get("name", ""),
                        "home_goals": int(home_goals),
                        "away_goals": int(away_goals),
                        "date":       fixture.get("date", ""),
                    })
        except Exception as e:
            log.warning(f"[Retrain] Error fetching {league_name} season {season}: {e}")
            continue

    if not all_fixtures:
        return None

    df = pd.DataFrame(all_fixtures)
    df = df[df["home_team"].str.len() > 0]
    df = df[df["away_team"].str.len() > 0]
    df = df.drop_duplicates(subset=["league", "home_team", "away_team", "date"])

    log.info(f"[Retrain] DataFrame construido: {len(df)} partidos de {df['league'].nunique()} ligas")
    return df


def run_retrain(poisson_model, logistic_model, calibrator, fetcher) -> dict:
    """
    Ejecuta el re-entrenamiento completo.
    Retorna dict con resultado: {"success": bool, "message": str, "metrics": dict}
    """
    global _retrain_status

    with _retrain_lock:
        if _retrain_status["is_running"]:
            return {"success": False, "message": "Re-entrenamiento ya en curso", "metrics": {}}
        _retrain_status["is_running"] = True

    try:
        log.info("[Retrain] Iniciando re-entrenamiento...")
        start_time = datetime.now(timezone.utc)

        # 1. Obtener datos frescos
        df = _build_training_dataframe(fetcher)
        if df is None or len(df) < 100:
            raise ValueError(f"Datos insuficientes para re-entrenar ({len(df) if df is not None else 0} partidos)")

        # 2. Re-entrenar Poisson/Dixon-Coles
        poisson_model.fit(df)
        log.info(f"[Retrain] Poisson re-entrenado. ρ={poisson_model.rho:.4f}")

        # 3. Preparar features para regresión logística
        features, labels = _build_logistic_features(df, poisson_model)
        if len(features) >= 50:
            logistic_model.fit(features, labels)
            log.info(f"[Retrain] Logistic re-entrenado con {len(features)} muestras")

        # 4. Re-calibrar con Platt Scaling
        if len(features) >= 50:
            calibrator.calibrate(poisson_model, df)
            log.info("[Retrain] Calibrador re-entrenado")

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

        metrics = {
            "total_matches":  int(len(df)),
            "total_leagues":  int(df["league"].nunique()),
            "rho":            round(float(poisson_model.rho), 4),
            "elapsed_seconds": round(elapsed, 1),
            "timestamp":      start_time.isoformat(),
        }

        with _retrain_lock:
            _retrain_status["last_retrain"] = start_time.isoformat()
            _retrain_status["last_error"]   = None
            _retrain_status["total_runs"]  += 1
            _retrain_status["last_metrics"] = metrics
            _retrain_status["is_running"]   = False

        log.info(f"[Retrain] Completado en {elapsed:.1f}s — {len(df)} partidos, ρ={poisson_model.rho:.4f}")
        return {"success": True, "message": "Re-entrenamiento exitoso", "metrics": metrics}

    except Exception as e:
        error_msg = str(e)
        log.error(f"[Retrain] Error: {error_msg}")
        with _retrain_lock:
            _retrain_status["last_error"] = error_msg
            _retrain_status["is_running"] = False
        return {"success": False, "message": error_msg, "metrics": {}}


def run_retrain_async(poisson_model, logistic_model, calibrator, fetcher):
    """Lanza el re-entrenamiento en un thread background (no bloquea el request)."""
    t = threading.Thread(
        target=run_retrain,
        args=(poisson_model, logistic_model, calibrator, fetcher),
        daemon=True,
        name="retrain-worker"
    )
    t.start()
    return t


def _build_logistic_features(df: pd.DataFrame, poisson_model) -> tuple:
    """Construye features para el modelo logístico a partir del DataFrame."""
    features = []
    labels   = []

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
            # Label: 0=home, 1=draw, 2=away
            if row["home_goals"] > row["away_goals"]:
                labels.append(0)
            elif row["home_goals"] == row["away_goals"]:
                labels.append(1)
            else:
                labels.append(2)
        except Exception:
            continue

    return features, labels
