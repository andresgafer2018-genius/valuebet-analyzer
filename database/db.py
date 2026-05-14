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
                INSERT INTO bankroll (amount)
                SELECT 1000.0
                WHERE NOT EXISTS (SELECT 1 FROM bankroll);
            ''')
        conn.commit()
        log.info('Base de datos inicializada correctamente')
    except Exception as e:
        conn.rollback()
        log.error(f'Error inicializando DB: {e}')
        raise
    finally:
        conn.close()
