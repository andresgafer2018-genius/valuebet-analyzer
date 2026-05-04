import os
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def send_message(text, parse_mode="HTML"):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return {"error": "Telegram no configurado"}
    r = requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
    }, timeout=10)
    return r.json()

def format_alert(alert):
    conf = "🔥 ALTA" if alert.get("confidence") == "ALTA" else "⚡ MEDIA"
    edge = alert.get("edge_pct", 0)
    odd = alert.get("odd", 0)
    kelly = alert.get("kelly_frac", 0)
    market = alert.get("market", "")
    match = alert.get("match", "")
    league = alert.get("league", "")
    return (
        f"{conf} | +{edge}% edge\n"
        f"⚽ <b>{match}</b>\n"
        f"🏆 {league}\n"
        f"📊 {market}\n"
        f"💰 Cuota: <b>{odd}</b> | Kelly: {kelly*100:.1f}%\n"
    )

def send_value_bets(alerts, min_edge=10.0):
    """Envia las mejores value bets por Telegram."""
    top = [a for a in alerts if a.get("edge_pct", 0) >= min_edge]
    if not top:
        return {"sent": 0, "message": "Sin alertas con edge suficiente"}

    now = datetime.now().strftime("%H:%M")
    header = f"🎯 <b>ValueBet Analyzer</b> — {now}\n{len(top)} oportunidades detectadas\n\n"
    body = "\n".join(format_alert(a) for a in top[:5])
    footer = f"\n<i>Edge minimo: {min_edge}% | Solo las top 5</i>"

    result = send_message(header + body + footer)
    return {"sent": len(top[:5]), "result": result}

def send_test():
    """Mensaje de prueba."""
    return send_message(
        "✅ <b>ValueBet Analyzer</b> conectado!\n"
        "Las notificaciones de value bets están activas.\n\n"
        "Recibirás alertas cuando se detecten oportunidades con edge alto."
    )
