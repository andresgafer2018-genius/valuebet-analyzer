import warnings, sys
warnings.filterwarnings('ignore')
sys.path.insert(0, '/home/claude/valuebets')

from data.fetcher import DataFetcher
from models.engine import PoissonModel, LogisticModel, ValueBetDetector, ArbitrageDetector

BANKROLL = 1500.0

f = DataFetcher()
df = f.get_historical_matches(400)
print(f"[OK] Datos: {len(df)} partidos historicos")

pm = PoissonModel()
pm.fit(df)
print(f"[OK] Poisson. Home advantage: {pm.home_advantage:.3f}")

lm = LogisticModel()
lm.fit(df)
print(f"[OK] Regresion Logistica")

det = ValueBetDetector()
arb_det = ArbitrageDetector()

upcoming = f.get_upcoming_matches()
print(f"[OK] {len(upcoming)} partidos proximos\n")

all_alerts = []
arb_count = 0

for match in upcoming:
    pred = pm.predict_proba(match['home_team'], match['away_team'], match['league'])
    pred_lr = lm.predict_proba(match['home_team'], match['away_team'],
                                pred['lambda_home'], pred['lambda_away'])
    if pred_lr:
        ph = pred['p_home']*0.6 + pred_lr['lr_p_home']*0.4
        pd = pred['p_draw']*0.6 + pred_lr['lr_p_draw']*0.4
        pa = pred['p_away']*0.6 + pred_lr['lr_p_away']*0.4
        t = ph+pd+pa
        pred['p_home'] = round(ph/t, 4)
        pred['p_draw'] = round(pd/t, 4)
        pred['p_away'] = round(pa/t, 4)

    odds_list = [f.get_simulated_odds(match) for _ in range(3)]
    for odds in odds_list:
        alerts = det.detect(pred, odds, match)
        all_alerts.extend(alerts)
    arb = arb_det.detect_arb(odds_list)
    if arb:
        arb_count += 1
        print(f"  ARBITRAJE: {match['home_team']} vs {match['away_team']} | Profit: {arb['profit_pct']}%")

seen = {}
for a in sorted(all_alerts, key=lambda x: x['edge_pct'], reverse=True):
    k = f"{a['match_id']}_{a['market']}"
    if k not in seen:
        seen[k] = a

top = sorted(seen.values(), key=lambda x: x['edge_pct'], reverse=True)[:12]

print(f"\n{'='*75}")
print(f"  VALUE BETS DEL DIA (bankroll: ${BANKROLL:.0f})")
print(f"{'='*75}")
print(f"{'CONF':<6} {'LIGA':<16} {'PARTIDO':<26} {'MERCADO':<19} {'CUOTA':>6} {'EDGE':>7} {'APUESTA':>12}")
print(f"{'-'*75}")
for a in top:
    stake = round(BANKROLL * a['kelly_frac'], 2)
    partido = f"{a['home_team'][:11]} vs {a['away_team'][:9]}"
    print(f"[{a['confidence']:4}] {a['league'][:14]:16} {partido:26} {a['market_label'][:18]:19} {a['odd']:>6.2f} {'+'+str(a['edge_pct'])+'%':>7} ${stake:>8.2f} ({a['kelly_frac']*100:.1f}%bk)")

print(f"{'-'*75}")
if top:
    avg_edge = sum(a['edge_pct'] for a in top) / len(top)
    high_conf = len([a for a in top if a['confidence'] == 'ALTA'])
    total_stake = sum(round(BANKROLL * a['kelly_frac'], 2) for a in top)
    print(f"  Total VBs: {len(top)} | Conf.Alta: {high_conf} | Edge avg: +{avg_edge:.2f}% | Arbitrajes: {arb_count}")
    print(f"  Exposicion total si apostas todo: ${total_stake:.2f} ({total_stake/BANKROLL*100:.1f}% bankroll)")
    print(f"  Recomendacion: maximo 20% bankroll/dia = ${BANKROLL*0.2:.2f}")
print(f"{'='*75}")
