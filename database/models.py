import json
import logging
from database.db import get_connection

log = logging.getLogger(__name__)

# BANKROLL

def get_bankroll():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT amount FROM bankroll ORDER BY id DESC LIMIT 1')
            row = cur.fetchone()
            return float(row['amount']) if row else 1000.0
    finally:
        conn.close()

def update_bankroll(amount):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'UPDATE bankroll SET amount = %s, updated_at = NOW() WHERE id = (SELECT id FROM bankroll ORDER BY id DESC LIMIT 1)',
                (amount,)
            )
        conn.commit()
    finally:
        conn.close()

# APUESTAS

def save_bet(home_team, away_team, league, bet_type, odds, edge, kelly_stake, amount_bet, match_date=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO bets (home_team, away_team, league, bet_type, odds, edge, kelly_stake, amount_bet, result, match_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)
                RETURNING id
            ''', (home_team, away_team, league, bet_type, odds, edge, kelly_stake, amount_bet, match_date))
            bet_id = cur.fetchone()['id']
        conn.commit()
        return bet_id
    finally:
        conn.close()

def resolve_bet(bet_id, result):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT odds, amount_bet FROM bets WHERE id = %s', (bet_id,))
            bet = cur.fetchone()
            if not bet:
                return None
            profit = (bet['odds'] - 1) * bet['amount_bet'] if result == 'win' else -bet['amount_bet']
            cur.execute('UPDATE bets SET result = %s, profit = %s WHERE id = %s', (result, profit, bet_id))
            cur.execute(
                'UPDATE bankroll SET amount = amount + %s, updated_at = NOW() WHERE id = (SELECT id FROM bankroll ORDER BY id DESC LIMIT 1)',
                (profit,)
            )
        conn.commit()
        return profit
    finally:
        conn.close()

def get_bets(limit=50, result_filter=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if result_filter:
                cur.execute('SELECT * FROM bets WHERE result = %s ORDER BY created_at DESC LIMIT %s', (result_filter, limit))
            else:
                cur.execute('SELECT * FROM bets ORDER BY created_at DESC LIMIT %s', (limit,))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def get_bet_stats():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT
                    COUNT(*) FILTER (WHERE result != 'pending') AS total,
                    COUNT(*) FILTER (WHERE result = 'win')      AS wins,
                    COUNT(*) FILTER (WHERE result = 'loss')     AS losses,
                    COUNT(*) FILTER (WHERE result = 'pending')  AS pending,
                    COALESCE(SUM(profit), 0)                    AS total_profit,
                    COALESCE(AVG(edge), 0)                      AS avg_edge
                FROM bets
            ''')
            return dict(cur.fetchone())
    finally:
        conn.close()

# ALERTAS

def save_alerts(alerts):
    if not alerts:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for alert in alerts:
                cur.execute('''
                    INSERT INTO alerts_history (home_team, away_team, league, alert_data)
                    VALUES (%s, %s, %s, %s)
                ''', (
                    alert.get('home_team', ''),
                    alert.get('away_team', ''),
                    alert.get('league', ''),
                    json.dumps(alert)
                ))
        conn.commit()
    finally:
        conn.close()

def get_alerts_history(limit=100):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM alerts_history ORDER BY created_at DESC LIMIT %s', (limit,))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def update_bet_result(bet_id, result):
    """Actualiza resultado de una apuesta (win/loss/void) y calcula profit."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT odds, amount_bet FROM bets WHERE id = %s", (bet_id,))
            row = cur.fetchone()
            if not row:
                return {"error": "bet not found"}
            if result == 'win':
                profit = round(row['amount_bet'] * (row['odds'] - 1), 2)
            elif result == 'loss':
                profit = -round(row['amount_bet'], 2)
            else:
                profit = 0
            cur.execute("UPDATE bets SET result = %s, profit = %s WHERE id = %s", (result, profit, bet_id))
        conn.commit()
        return {"status": "updated", "profit": profit}
    finally:
        conn.close()

def delete_bet(bet_id):
    """Elimina una apuesta."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM bets WHERE id = %s", (bet_id,))
        conn.commit()
        return {"status": "deleted"}
    finally:
        conn.close()


def get_settings():
    """Obtiene la configuracion del usuario."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT key, value FROM user_settings')
            rows = cur.fetchall()
            return {r['key']: r['value'] for r in rows} if rows else {}
    finally:
        conn.close()


def save_settings(settings: dict):
    """Guarda la configuracion del usuario (upsert)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for key, value in settings.items():
                cur.execute("""
                    INSERT INTO user_settings (key, value)
                    VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """, (key, str(value)))
        conn.commit()
        return {"status": "ok"}
    finally:
        conn.close()
