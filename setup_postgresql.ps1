# ============================================================
# ValueBet Analyzer - Setup PostgreSQL
# Ejecutar desde: F:\Proyecto Apuestas
# ============================================================

$ROOT = "F:\Proyecto Apuestas"
Set-Location $ROOT
Write-Host ""
Write-Host "Iniciando setup PostgreSQL para ValueBet Analyzer..." -ForegroundColor Cyan

# ─── PASO 1: Crear database/__init__.py ─────────────────────

Write-Host ""
Write-Host "Paso 1: Creando archivos database/..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path "$ROOT\database" -Force | Out-Null
[System.IO.File]::WriteAllText("$ROOT\database\__init__.py", "", [System.Text.Encoding]::UTF8)
Write-Host "  OK database/__init__.py" -ForegroundColor Green

# ─── PASO 2: Crear database/db.py ───────────────────────────

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("import os")
$lines.Add("import psycopg2")
$lines.Add("from psycopg2.extras import RealDictCursor")
$lines.Add("import logging")
$lines.Add("")
$lines.Add("log = logging.getLogger(__name__)")
$lines.Add("")
$lines.Add("def get_connection():")
$lines.Add("    database_url = os.getenv('DATABASE_URL')")
$lines.Add("    if not database_url:")
$lines.Add("        raise RuntimeError('DATABASE_URL no esta configurada')")
$lines.Add("    if database_url.startswith('postgres://'):")
$lines.Add("        database_url = database_url.replace('postgres://', 'postgresql://', 1)")
$lines.Add("    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)")
$lines.Add("")
$lines.Add("def init_db():")
$lines.Add("    conn = get_connection()")
$lines.Add("    try:")
$lines.Add("        with conn.cursor() as cur:")
$lines.Add("            cur.execute('''")
$lines.Add("                CREATE TABLE IF NOT EXISTS bankroll (")
$lines.Add("                    id         SERIAL PRIMARY KEY,")
$lines.Add("                    amount     FLOAT NOT NULL DEFAULT 1000.0,")
$lines.Add("                    updated_at TIMESTAMP DEFAULT NOW()")
$lines.Add("                );")
$lines.Add("                CREATE TABLE IF NOT EXISTS bets (")
$lines.Add("                    id          SERIAL PRIMARY KEY,")
$lines.Add("                    home_team   VARCHAR(100),")
$lines.Add("                    away_team   VARCHAR(100),")
$lines.Add("                    league      VARCHAR(100),")
$lines.Add("                    bet_type    VARCHAR(20),")
$lines.Add("                    odds        FLOAT,")
$lines.Add("                    edge        FLOAT,")
$lines.Add("                    kelly_stake FLOAT,")
$lines.Add("                    amount_bet  FLOAT,")
$lines.Add("                    result      VARCHAR(10) DEFAULT 'pending',")
$lines.Add("                    profit      FLOAT DEFAULT 0,")
$lines.Add("                    created_at  TIMESTAMP DEFAULT NOW(),")
$lines.Add("                    match_date  TIMESTAMP")
$lines.Add("                );")
$lines.Add("                CREATE TABLE IF NOT EXISTS alerts_history (")
$lines.Add("                    id         SERIAL PRIMARY KEY,")
$lines.Add("                    home_team  VARCHAR(100),")
$lines.Add("                    away_team  VARCHAR(100),")
$lines.Add("                    league     VARCHAR(100),")
$lines.Add("                    alert_data JSONB,")
$lines.Add("                    created_at TIMESTAMP DEFAULT NOW()")
$lines.Add("                );")
$lines.Add("                INSERT INTO bankroll (amount)")
$lines.Add("                SELECT 1000.0")
$lines.Add("                WHERE NOT EXISTS (SELECT 1 FROM bankroll);")
$lines.Add("            ''')")
$lines.Add("        conn.commit()")
$lines.Add("        log.info('Base de datos inicializada correctamente')")
$lines.Add("    except Exception as e:")
$lines.Add("        conn.rollback()")
$lines.Add("        log.error(f'Error inicializando DB: {e}')")
$lines.Add("        raise")
$lines.Add("    finally:")
$lines.Add("        conn.close()")

[System.IO.File]::WriteAllLines("$ROOT\database\db.py", $lines, [System.Text.Encoding]::UTF8)
Write-Host "  OK database/db.py" -ForegroundColor Green

# ─── PASO 3: Crear database/models.py ───────────────────────

$lines2 = New-Object System.Collections.Generic.List[string]
$lines2.Add("import json")
$lines2.Add("import logging")
$lines2.Add("from database.db import get_connection")
$lines2.Add("")
$lines2.Add("log = logging.getLogger(__name__)")
$lines2.Add("")
$lines2.Add("# BANKROLL")
$lines2.Add("")
$lines2.Add("def get_bankroll():")
$lines2.Add("    conn = get_connection()")
$lines2.Add("    try:")
$lines2.Add("        with conn.cursor() as cur:")
$lines2.Add("            cur.execute('SELECT amount FROM bankroll ORDER BY id DESC LIMIT 1')")
$lines2.Add("            row = cur.fetchone()")
$lines2.Add("            return float(row['amount']) if row else 1000.0")
$lines2.Add("    finally:")
$lines2.Add("        conn.close()")
$lines2.Add("")
$lines2.Add("def update_bankroll(amount):")
$lines2.Add("    conn = get_connection()")
$lines2.Add("    try:")
$lines2.Add("        with conn.cursor() as cur:")
$lines2.Add("            cur.execute(")
$lines2.Add("                'UPDATE bankroll SET amount = %s, updated_at = NOW() WHERE id = (SELECT id FROM bankroll ORDER BY id DESC LIMIT 1)',")
$lines2.Add("                (amount,)")
$lines2.Add("            )")
$lines2.Add("        conn.commit()")
$lines2.Add("    finally:")
$lines2.Add("        conn.close()")
$lines2.Add("")
$lines2.Add("# APUESTAS")
$lines2.Add("")
$lines2.Add("def save_bet(home_team, away_team, league, bet_type, odds, edge, kelly_stake, amount_bet, match_date=None):")
$lines2.Add("    conn = get_connection()")
$lines2.Add("    try:")
$lines2.Add("        with conn.cursor() as cur:")
$lines2.Add("            cur.execute('''")
$lines2.Add("                INSERT INTO bets (home_team, away_team, league, bet_type, odds, edge, kelly_stake, amount_bet, result, match_date)")
$lines2.Add("                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)")
$lines2.Add("                RETURNING id")
$lines2.Add("            ''', (home_team, away_team, league, bet_type, odds, edge, kelly_stake, amount_bet, match_date))")
$lines2.Add("            bet_id = cur.fetchone()['id']")
$lines2.Add("        conn.commit()")
$lines2.Add("        return bet_id")
$lines2.Add("    finally:")
$lines2.Add("        conn.close()")
$lines2.Add("")
$lines2.Add("def resolve_bet(bet_id, result):")
$lines2.Add("    conn = get_connection()")
$lines2.Add("    try:")
$lines2.Add("        with conn.cursor() as cur:")
$lines2.Add("            cur.execute('SELECT odds, amount_bet FROM bets WHERE id = %s', (bet_id,))")
$lines2.Add("            bet = cur.fetchone()")
$lines2.Add("            if not bet:")
$lines2.Add("                return None")
$lines2.Add("            profit = (bet['odds'] - 1) * bet['amount_bet'] if result == 'win' else -bet['amount_bet']")
$lines2.Add("            cur.execute('UPDATE bets SET result = %s, profit = %s WHERE id = %s', (result, profit, bet_id))")
$lines2.Add("            cur.execute(")
$lines2.Add("                'UPDATE bankroll SET amount = amount + %s, updated_at = NOW() WHERE id = (SELECT id FROM bankroll ORDER BY id DESC LIMIT 1)',")
$lines2.Add("                (profit,)")
$lines2.Add("            )")
$lines2.Add("        conn.commit()")
$lines2.Add("        return profit")
$lines2.Add("    finally:")
$lines2.Add("        conn.close()")
$lines2.Add("")
$lines2.Add("def get_bets(limit=50, result_filter=None):")
$lines2.Add("    conn = get_connection()")
$lines2.Add("    try:")
$lines2.Add("        with conn.cursor() as cur:")
$lines2.Add("            if result_filter:")
$lines2.Add("                cur.execute('SELECT * FROM bets WHERE result = %s ORDER BY created_at DESC LIMIT %s', (result_filter, limit))")
$lines2.Add("            else:")
$lines2.Add("                cur.execute('SELECT * FROM bets ORDER BY created_at DESC LIMIT %s', (limit,))")
$lines2.Add("            return [dict(r) for r in cur.fetchall()]")
$lines2.Add("    finally:")
$lines2.Add("        conn.close()")
$lines2.Add("")
$lines2.Add("def get_bet_stats():")
$lines2.Add("    conn = get_connection()")
$lines2.Add("    try:")
$lines2.Add("        with conn.cursor() as cur:")
$lines2.Add("            cur.execute('''")
$lines2.Add("                SELECT")
$lines2.Add("                    COUNT(*) FILTER (WHERE result != 'pending') AS total,")
$lines2.Add("                    COUNT(*) FILTER (WHERE result = 'win')      AS wins,")
$lines2.Add("                    COUNT(*) FILTER (WHERE result = 'loss')     AS losses,")
$lines2.Add("                    COUNT(*) FILTER (WHERE result = 'pending')  AS pending,")
$lines2.Add("                    COALESCE(SUM(profit), 0)                    AS total_profit,")
$lines2.Add("                    COALESCE(AVG(edge), 0)                      AS avg_edge")
$lines2.Add("                FROM bets")
$lines2.Add("            ''')")
$lines2.Add("            return dict(cur.fetchone())")
$lines2.Add("    finally:")
$lines2.Add("        conn.close()")
$lines2.Add("")
$lines2.Add("# ALERTAS")
$lines2.Add("")
$lines2.Add("def save_alerts(alerts):")
$lines2.Add("    if not alerts:")
$lines2.Add("        return")
$lines2.Add("    conn = get_connection()")
$lines2.Add("    try:")
$lines2.Add("        with conn.cursor() as cur:")
$lines2.Add("            for alert in alerts:")
$lines2.Add("                cur.execute('''")
$lines2.Add("                    INSERT INTO alerts_history (home_team, away_team, league, alert_data)")
$lines2.Add("                    VALUES (%s, %s, %s, %s)")
$lines2.Add("                ''', (")
$lines2.Add("                    alert.get('home_team', ''),")
$lines2.Add("                    alert.get('away_team', ''),")
$lines2.Add("                    alert.get('league', ''),")
$lines2.Add("                    json.dumps(alert)")
$lines2.Add("                ))")
$lines2.Add("        conn.commit()")
$lines2.Add("    finally:")
$lines2.Add("        conn.close()")
$lines2.Add("")
$lines2.Add("def get_alerts_history(limit=100):")
$lines2.Add("    conn = get_connection()")
$lines2.Add("    try:")
$lines2.Add("        with conn.cursor() as cur:")
$lines2.Add("            cur.execute('SELECT * FROM alerts_history ORDER BY created_at DESC LIMIT %s', (limit,))")
$lines2.Add("            return [dict(r) for r in cur.fetchall()]")
$lines2.Add("    finally:")
$lines2.Add("        conn.close()")

[System.IO.File]::WriteAllLines("$ROOT\database\models.py", $lines2, [System.Text.Encoding]::UTF8)
Write-Host "  OK database/models.py" -ForegroundColor Green

# ─── PASO 4: Modificar api.py ───────────────────────────────

Write-Host ""
Write-Host "Paso 2: Modificando dashboard/api.py..." -ForegroundColor Yellow

$apiPath = "$ROOT\dashboard\api.py"
Copy-Item $apiPath "$apiPath.bak" -Force
Write-Host "  Backup creado: api.py.bak" -ForegroundColor Gray

$apiContent = [System.IO.File]::ReadAllText($apiPath, [System.Text.Encoding]::UTF8)

# 4a) Agregar imports DB
$oldImport = "from models.engine import PoissonModel, LogisticModel, ValueBetDetector, ArbitrageDetector, ProbabilityCalibrator"
$newImport = "from models.engine import PoissonModel, LogisticModel, ValueBetDetector, ArbitrageDetector, ProbabilityCalibrator`nfrom database.db import init_db`nfrom database.models import get_bankroll, update_bankroll, save_alerts, get_alerts_history, get_bets, get_bet_stats, save_bet, resolve_bet"
$apiContent = $apiContent.Replace($oldImport, $newImport)
Write-Host "  OK imports de DB agregados" -ForegroundColor Green

# 4b) Reemplazar _state
$oldState = "_state = {`n    `"alerts`": None, `"predictions`": None, `"arb`": [],`n    `"bankroll`": float(os.getenv(`"INITIAL_BANKROLL`", `"1000`")),`n}"
$newState = "# Inicializar PostgreSQL`n_db_available = False`ntry:`n    init_db()`n    _db_available = True`n    log.info('PostgreSQL conectado correctamente')`nexcept Exception as _e:`n    log.warning(f'Sin PostgreSQL, usando memoria: {_e}')`n`n_state = {`n    `"alerts`": None, `"predictions`": None, `"arb`": [],`n    `"bankroll`": get_bankroll() if _db_available else float(os.getenv(`"INITIAL_BANKROLL`", `"1000`")),`n}"
$apiContent = $apiContent.Replace($oldState, $newState)
Write-Host "  OK _state actualizado" -ForegroundColor Green

# 4c) Agregar save_alerts al final de _train_and_analyze
$oldEnd = "    _state[`"arb`"] = arbs"
$newEnd = "    _state[`"arb`"] = arbs`n`n    # Persistir alertas en PostgreSQL`n    if _db_available and all_alerts:`n        try:`n            save_alerts(all_alerts)`n            log.info(f'Guardadas {len(all_alerts)} alertas en DB')`n        except Exception as e:`n            log.warning(f'No se pudieron guardar alertas: {e}')"
$apiContent = $apiContent.Replace($oldEnd, $newEnd)
Write-Host "  OK save_alerts agregado en _train_and_analyze" -ForegroundColor Green

# 4d) Agregar nuevos endpoints al final
$endpoints = New-Object System.Collections.Generic.List[string]
$endpoints.Add("")
$endpoints.Add("")
$endpoints.Add("# ENDPOINTS DE BASE DE DATOS")
$endpoints.Add("")
$endpoints.Add("@app.route('/api/bets', methods=['GET'])")
$endpoints.Add("def list_bets():")
$endpoints.Add("    if not _db_available:")
$endpoints.Add("        return jsonify({'error': 'DB no disponible'}), 503")
$endpoints.Add("    result_filter = request.args.get('result')")
$endpoints.Add("    limit = int(request.args.get('limit', 50))")
$endpoints.Add("    bets = get_bets(limit=limit, result_filter=result_filter)")
$endpoints.Add("    for b in bets:")
$endpoints.Add("        for k, v in b.items():")
$endpoints.Add("            if hasattr(v, 'isoformat'):")
$endpoints.Add("                b[k] = v.isoformat()")
$endpoints.Add("    return jsonify({'bets': bets})")
$endpoints.Add("")
$endpoints.Add("@app.route('/api/bets', methods=['POST'])")
$endpoints.Add("def create_bet():")
$endpoints.Add("    if not _db_available:")
$endpoints.Add("        return jsonify({'error': 'DB no disponible'}), 503")
$endpoints.Add("    data = request.get_json(silent=True) or {}")
$endpoints.Add("    bet_id = save_bet(")
$endpoints.Add("        home_team=data.get('home_team', ''),")
$endpoints.Add("        away_team=data.get('away_team', ''),")
$endpoints.Add("        league=data.get('league', ''),")
$endpoints.Add("        bet_type=data.get('bet_type', 'home'),")
$endpoints.Add("        odds=float(data.get('odds', 0)),")
$endpoints.Add("        edge=float(data.get('edge', 0)),")
$endpoints.Add("        kelly_stake=float(data.get('kelly_stake', 0)),")
$endpoints.Add("        amount_bet=float(data.get('amount_bet', 0)),")
$endpoints.Add("        match_date=data.get('match_date'),")
$endpoints.Add("    )")
$endpoints.Add("    return jsonify({'bet_id': bet_id, 'status': 'saved'})")
$endpoints.Add("")
$endpoints.Add("@app.route('/api/bets/<int:bet_id>/resolve', methods=['POST'])")
$endpoints.Add("def resolve_bet_endpoint(bet_id):")
$endpoints.Add("    if not _db_available:")
$endpoints.Add("        return jsonify({'error': 'DB no disponible'}), 503")
$endpoints.Add("    data = request.get_json(silent=True) or {}")
$endpoints.Add("    result = data.get('result')")
$endpoints.Add("    if result not in ('win', 'loss'):")
$endpoints.Add("        return jsonify({'error': 'result debe ser win o loss'}), 400")
$endpoints.Add("    profit = resolve_bet(bet_id, result)")
$endpoints.Add("    new_bankroll = get_bankroll()")
$endpoints.Add("    _state['bankroll'] = new_bankroll")
$endpoints.Add("    return jsonify({'profit': profit, 'new_bankroll': new_bankroll})")
$endpoints.Add("")
$endpoints.Add("@app.route('/api/stats', methods=['GET'])")
$endpoints.Add("def bet_stats():")
$endpoints.Add("    if not _db_available:")
$endpoints.Add("        return jsonify({'error': 'DB no disponible'}), 503")
$endpoints.Add("    stats = get_bet_stats()")
$endpoints.Add("    bankroll = get_bankroll()")
$endpoints.Add("    for k, v in stats.items():")
$endpoints.Add("        if hasattr(v, '__float__'):")
$endpoints.Add("            stats[k] = float(v)")
$endpoints.Add("    return jsonify({**stats, 'current_bankroll': bankroll})")
$endpoints.Add("")
$endpoints.Add("@app.route('/api/alerts/history', methods=['GET'])")
$endpoints.Add("def alerts_history():")
$endpoints.Add("    if not _db_available:")
$endpoints.Add("        return jsonify({'error': 'DB no disponible'}), 503")
$endpoints.Add("    limit = int(request.args.get('limit', 100))")
$endpoints.Add("    history = get_alerts_history(limit=limit)")
$endpoints.Add("    for h in history:")
$endpoints.Add("        for k, v in h.items():")
$endpoints.Add("            if hasattr(v, 'isoformat'):")
$endpoints.Add("                h[k] = v.isoformat()")
$endpoints.Add("    return jsonify({'alerts': history})")

$endpointsText = $endpoints -join "`n"
$apiContent = $apiContent + $endpointsText
[System.IO.File]::WriteAllText($apiPath, $apiContent, [System.Text.Encoding]::UTF8)
Write-Host "  OK nuevos endpoints agregados" -ForegroundColor Green
Write-Host "  OK api.py guardado" -ForegroundColor Green

# ─── PASO 5: requirements.txt ───────────────────────────────

Write-Host ""
Write-Host "Paso 3: Actualizando requirements.txt..." -ForegroundColor Yellow
$reqPath = "$ROOT\requirements.txt"
$reqContent = [System.IO.File]::ReadAllText($reqPath, [System.Text.Encoding]::UTF8)
if ($reqContent -notmatch "psycopg2-binary") {
    [System.IO.File]::AppendAllText($reqPath, "`npsycopg2-binary==2.9.9", [System.Text.Encoding]::UTF8)
    Write-Host "  OK psycopg2-binary==2.9.9 agregado" -ForegroundColor Green
} else {
    Write-Host "  psycopg2-binary ya existe, saltando" -ForegroundColor Gray
}

# ─── PASO 6: Crear deploy_postgres.ps1 ──────────────────────

Write-Host ""
Write-Host "Paso 4: Creando deploy_postgres.ps1..." -ForegroundColor Yellow

$deployLines = New-Object System.Collections.Generic.List[string]
$deployLines.Add("# deploy_postgres.ps1 - Ejecutar UNA SOLA VEZ")
$deployLines.Add("Set-Location 'F:\Proyecto Apuestas'")
$deployLines.Add("Write-Host 'Creando PostgreSQL en Fly.io...' -ForegroundColor Cyan")
$deployLines.Add("flyctl postgres create --name valuebet-db --region iad --initial-cluster-size 1 --vm-size shared-cpu-1x --volume-size 1")
$deployLines.Add("flyctl postgres attach valuebet-db --app valuebet-analyzer")
$deployLines.Add("Write-Host 'Secrets actuales:' -ForegroundColor Yellow")
$deployLines.Add("flyctl secrets list --app valuebet-analyzer")
$deployLines.Add("git add -A")
$deployLines.Add("git commit -m 'feat: integrar PostgreSQL persistente'")
$deployLines.Add("git push origin master")
$deployLines.Add("Write-Host 'Listo! Deploy en curso via GitHub Actions.' -ForegroundColor Green")
$deployLines.Add("Write-Host 'Endpoints nuevos:'")
$deployLines.Add("Write-Host '  GET  /api/stats'")
$deployLines.Add("Write-Host '  GET  /api/bets'")
$deployLines.Add("Write-Host '  POST /api/bets'")
$deployLines.Add("Write-Host '  POST /api/bets/{id}/resolve'")
$deployLines.Add("Write-Host '  GET  /api/alerts/history'")

[System.IO.File]::WriteAllLines("$ROOT\deploy_postgres.ps1", $deployLines, [System.Text.Encoding]::UTF8)
Write-Host "  OK deploy_postgres.ps1 creado" -ForegroundColor Green

# ─── RESUMEN ────────────────────────────────────────────────

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Setup completado!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Archivos creados/modificados:" -ForegroundColor White
Write-Host "  + database/__init__.py" -ForegroundColor Green
Write-Host "  + database/db.py" -ForegroundColor Green
Write-Host "  + database/models.py" -ForegroundColor Green
Write-Host "  ~ dashboard/api.py  (backup: api.py.bak)" -ForegroundColor Yellow
Write-Host "  ~ requirements.txt" -ForegroundColor Yellow
Write-Host "  + deploy_postgres.ps1" -ForegroundColor Green
Write-Host ""
Write-Host "PROXIMO PASO - ejecuta:" -ForegroundColor Cyan
Write-Host "  Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force" -ForegroundColor White
Write-Host "  .\deploy_postgres.ps1" -ForegroundColor White
Write-Host ""
Write-Host "NOTA: deploy_postgres.ps1 se ejecuta UNA SOLA VEZ." -ForegroundColor Yellow
