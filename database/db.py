import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

log = logging.getLogger(__name__)

def get_connection():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise RuntimeError('DATABASE_URL no esta configurada')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

def init_db():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS bankroll (
                    id         SERIAL PRIMARY KEY,
                    amount     FLOAT NOT NULL DEFAULT 1000.0,
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS bets (
                    id          SERIAL PRIMARY KEY,
                    home_team   VARCHAR(100),
                    away_team   VARCHAR(100),
                    league      VARCHAR(100),
                    bet_type    VARCHAR(20),
                    odds        FLOAT,
                    edge        FLOAT,
                    kelly_stake FLOAT,
                    amount_bet  FLOAT,
                    result      VARCHAR(10) DEFAULT 'pending',
                    profit      FLOAT DEFAULT 0,
                    created_at  TIMESTAMP DEFAULT NOW(),
                    match_date  TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS alerts_history (
                    id         SERIAL PRIMARY KEY,
                    home_team  VARCHAR(100),
                    away_team  VARCHAR(100),
                    league     VARCHAR(100),
                    alert_data JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS retrain_status (
                    id           SERIAL PRIMARY KEY,
                    last_retrain TIMESTAMP,
                    last_error   TEXT,
                    is_running   BOOLEAN DEFAULT FALSE,
                    total_runs   INTEGER DEFAULT 0,
                    last_metrics JSONB DEFAULT '{}'::jsonb,
                    updated_at   TIMESTAMP DEFAULT NOW()
                );
                INSERT INTO bankroll (amount)
                SELECT 1000.0
                WHERE NOT EXISTS (SELECT 1 FROM bankroll);
                INSERT INTO retrain_status (is_running, total_runs, last_metrics)
                SELECT FALSE, 0, '{}'::jsonb
                WHERE NOT EXISTS (SELECT 1 FROM retrain_status);
            ''')
        conn.commit()
        log.info('Base de datos inicializada correctamente')
    except Exception as e:
        conn.rollback()
        log.error(f'Error inicializando DB: {e}')
        raise
    finally:
        conn.close()


# ── Funciones para retrain_status ──────────────────────────────────────────

def get_retrain_status_db() -> dict:
    """Lee el status del re-entrenamiento desde PostgreSQL."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM retrain_status ORDER BY id LIMIT 1')
            row = cur.fetchone()
        conn.close()
        if row:
            return {
                "last_retrain": row["last_retrain"].isoformat() if row["last_retrain"] else None,
                "last_error":   row["last_error"],
                "is_running":   row["is_running"],
                "total_runs":   row["total_runs"],
                "last_metrics": dict(row["last_metrics"]) if row["last_metrics"] else {},
            }
    except Exception as e:
        log.warning(f'[DB] No se pudo leer retrain_status: {e}')
    return {
        "last_retrain": None,
        "last_error":   None,
        "is_running":   False,
        "total_runs":   0,
        "last_metrics": {},
    }


def update_retrain_status_db(last_retrain=None, last_error=None,
                              is_running=None, total_runs=None,
                              last_metrics=None):
    """Actualiza el status del re-entrenamiento en PostgreSQL."""
    import json
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            fields, values = [], []
            if last_retrain is not None:
                fields.append("last_retrain = %s"); values.append(last_retrain)
            if last_error is not None:
                fields.append("last_error = %s"); values.append(last_error)
            if is_running is not None:
                fields.append("is_running = %s"); values.append(is_running)
            if total_runs is not None:
                fields.append("total_runs = %s"); values.append(total_runs)
            if last_metrics is not None:
                fields.append("last_metrics = %s"); values.append(json.dumps(last_metrics))
            fields.append("updated_at = NOW()")
            if fields:
                sql = f"UPDATE retrain_status SET {', '.join(fields)} WHERE id = (SELECT id FROM retrain_status LIMIT 1)"
                cur.execute(sql, values)
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning(f'[DB] No se pudo actualizar retrain_status: {e}')


# ── Funciones para bets ────────────────────────────────────────────────────

def save_bet(home_team, away_team, league, bet_type, odds, edge, kelly_stake, amount_bet, match_date=None):
    """Guarda una nueva apuesta en PostgreSQL."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO bets (home_team, away_team, league, bet_type, odds, edge, kelly_stake, amount_bet, match_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (home_team, away_team, league, bet_type, odds, edge, kelly_stake, amount_bet, match_date))
            row = cur.fetchone()
        conn.commit()
        conn.close()
        return row["id"] if row else None
    except Exception as e:
        log.error(f'[DB] Error guardando apuesta: {e}')
        return None


def get_bets(limit=100):
    """Obtiene las apuestas más recientes."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM bets ORDER BY created_at DESC LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f'[DB] Error obteniendo apuestas: {e}')
        return []


def update_bet_result(bet_id, result, profit):
    """Actualiza el resultado de una apuesta."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE bets SET result = %s, profit = %s WHERE id = %s
            """, (result, profit, bet_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log.error(f'[DB] Error actualizando resultado: {e}')
        return False


def delete_bet(bet_id):
    """Elimina una apuesta."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM bets WHERE id = %s", (bet_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log.error(f'[DB] Error eliminando apuesta: {e}')
        return False


def get_bet_stats():
    """Obtiene estadísticas generales de apuestas."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE result = 'won') as won,
                    COUNT(*) FILTER (WHERE result = 'lost') as lost,
                    COUNT(*) FILTER (WHERE result = 'pending') as pending,
                    COALESCE(SUM(profit), 0) as total_profit,
                    COALESCE(SUM(amount_bet), 0) as total_staked
                FROM bets
            """)
            row = cur.fetchone()
        conn.close()
        return dict(row) if row else {}
    except Exception as e:
        log.error(f'[DB] Error obteniendo stats: {e}')
        return {}


# ── Funciones para bankroll ────────────────────────────────────────────────

def get_bankroll():
    """Obtiene el bankroll actual."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT amount FROM bankroll ORDER BY id LIMIT 1")
            row = cur.fetchone()
        conn.close()
        return float(row["amount"]) if row else 1000.0
    except Exception as e:
        log.error(f'[DB] Error obteniendo bankroll: {e}')
        return 1000.0


def update_bankroll(amount):
    """Actualiza el bankroll."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE bankroll SET amount = %s, updated_at = NOW()
                WHERE id = (SELECT id FROM bankroll LIMIT 1)
            """, (amount,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log.error(f'[DB] Error actualizando bankroll: {e}')
        return False
