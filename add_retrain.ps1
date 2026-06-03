# ============================================================
# add_retrain.ps1
# Agrega re-entrenamiento automático al ValueBet Analyzer
# ============================================================

$ROOT    = "F:\Proyecto Apuestas"
$API     = "$ROOT\dashboard\api.py"
$MODELS  = "$ROOT\models"
$REQ     = "$ROOT\requirements.txt"

Set-Location $ROOT
Write-Host "`n🔄 Configurando re-entrenamiento automático..." -ForegroundColor Cyan

# ── PASO 1: Copiar retrain.py ────────────────────────────────
Write-Host "`n📄 Paso 1: Copiando retrain.py a models\..." -ForegroundColor Yellow
Copy-Item "$ROOT\retrain.py" "$MODELS\retrain.py" -Force
Write-Host "  ✅ models\retrain.py copiado" -ForegroundColor Green

# ── PASO 2: Agregar APScheduler a requirements.txt ──────────
Write-Host "`n📦 Paso 2: Actualizando requirements.txt..." -ForegroundColor Yellow
$req = Get-Content $REQ -Raw
if ($req -notmatch "APScheduler") {
    Add-Content $REQ "`nAPScheduler==3.10.4"
    Write-Host "  ✅ APScheduler==3.10.4 agregado" -ForegroundColor Green
} else {
    Write-Host "  ⏭️  APScheduler ya existe" -ForegroundColor Gray
}

# ── PASO 3: Parchear api.py ──────────────────────────────────
Write-Host "`n🔧 Paso 3: Parcheando api.py..." -ForegroundColor Yellow

$api = [System.IO.File]::ReadAllText($API, [System.Text.Encoding]::UTF8)

# 3a. Agregar imports si no existen
if ($api -notmatch "from models.retrain import") {
    $api = $api -replace "(from database\.models import[^\n]+)", `
        "`$1`nfrom models.retrain import run_retrain_async, get_retrain_status"
    Write-Host "  ✅ Import retrain agregado" -ForegroundColor Green
}

if ($api -notmatch "APScheduler|BackgroundScheduler") {
    $api = $api -replace "(import os, sys, logging)", `
        "`$1`nfrom apscheduler.schedulers.background import BackgroundScheduler`nfrom apscheduler.triggers.interval import IntervalTrigger"
    Write-Host "  ✅ Import APScheduler agregado" -ForegroundColor Green
}

# 3b. Agregar arranque del scheduler después de init_db
$schedulerBlock = @'

# ── Scheduler de re-entrenamiento automático ────────────────
_scheduler = BackgroundScheduler(timezone="UTC")

def _scheduled_retrain():
    """Función llamada por el scheduler cada 24hs."""
    log.info("[Scheduler] Iniciando re-entrenamiento programado...")
    run_retrain_async(poisson, logistic, calibrator, fetcher)

# Primer re-entrenamiento 5 minutos después del arranque,
# luego cada 24 horas
_scheduler.add_job(
    _scheduled_retrain,
    trigger=IntervalTrigger(hours=24),
    id="auto_retrain",
    replace_existing=True,
    misfire_grace_time=3600,
)
_scheduler.start()
log.info("[Scheduler] Re-entrenamiento automático activo (cada 24hs)")
# ────────────────────────────────────────────────────────────
'@

if ($api -notmatch "_scheduler = BackgroundScheduler") {
    # Insertar después del bloque de init de modelos (busca la línea del calibrator)
    $api = $api -replace "(calibrator\s*=\s*ProbabilityCalibrator[^\n]*\n)", "`$1$schedulerBlock`n"
    Write-Host "  ✅ Scheduler agregado" -ForegroundColor Green
}

# 3c. Agregar endpoints /api/retrain
$retrainEndpoints = @'

# ── Endpoints de re-entrenamiento ───────────────────────────

@app.route("/api/retrain", methods=["POST"])
def trigger_retrain():
    """Triggea re-entrenamiento manual en background."""
    status = get_retrain_status()
    if status["is_running"]:
        return jsonify({"message": "Re-entrenamiento ya en curso", "status": status}), 409
    run_retrain_async(poisson, logistic, calibrator, fetcher)
    return jsonify({"message": "Re-entrenamiento iniciado en background", "status": status})

@app.route("/api/retrain/status", methods=["GET"])
def retrain_status():
    """Devuelve el estado del último re-entrenamiento."""
    return jsonify(get_retrain_status())

'@

if ($api -notmatch '"/api/retrain"') {
    # Insertar antes del if __name__ == "__main__"
    $api = $api -replace '(if __name__ == .__main__.)', "$retrainEndpoints`n`$1"
    Write-Host "  ✅ Endpoints /api/retrain agregados" -ForegroundColor Green
}

[System.IO.File]::WriteAllText($API, $api, [System.Text.Encoding]::UTF8)
Write-Host "  ✅ api.py guardado" -ForegroundColor Green

# ── PASO 4: Commit y push ────────────────────────────────────
Write-Host "`n🚀 Paso 4: Commit y push..." -ForegroundColor Yellow

git add models\retrain.py dashboard\api.py requirements.txt
git commit -m "feat: re-entrenamiento automatico cada 24hs (APScheduler)"
git push origin master

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  ✅ Re-entrenamiento automático configurado!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Endpoints nuevos:" -ForegroundColor White
Write-Host "  POST /api/retrain         -> triggear manualmente" -ForegroundColor Gray
Write-Host "  GET  /api/retrain/status  -> ver estado" -ForegroundColor Gray
Write-Host ""
Write-Host "El modelo se re-entrena automáticamente cada 24hs." -ForegroundColor Yellow
