"""fix_retrain_final.py — usa variable global _models para pasar modelos al endpoint"""

with open('dashboard/api.py', 'r', encoding='utf-8') as f:
    api = f.read()

changed = []

# 1. Agregar _models dict global justo despues de inicializar los modelos
# Buscamos la linea donde se inicializa fetcher
if '_models = {}' not in api:
    api = api.replace(
        'fetcher = DataFetcher()',
        'fetcher = DataFetcher()\n_models = {}  # Referencia global para endpoints'
    )
    changed.append('_models dict')

# 2. Poblar _models despues de entrenar (buscar linea de calibrator)
if '_models["pm"]' not in api:
    api = api.replace(
        'cal = ProbabilityCalibrator()',
        'cal = ProbabilityCalibrator()\n_models["pm"] = pm if "pm" in dir() else None\n_models["lm"] = lm if "lm" in dir() else None\n_models["cal"] = cal\n_models["fetcher"] = fetcher'
    )
    changed.append('_models poblado')

# 3. Reemplazar endpoint para usar _models
old_endpoint = (
    '@app.route("/api/retrain", methods=["POST"])\n'
    'def trigger_retrain():\n'
    '    import sys\n'
    '    _mod = sys.modules[__name__]\n'
    '    _pm = getattr(_mod, "pm", None)\n'
    '    _lm = getattr(_mod, "lm", None)\n'
    '    _cal = getattr(_mod, "cal", None)\n'
    '    _f = getattr(_mod, "fetcher", None)\n'
    '    if _pm is None:\n'
    '        return jsonify({"message": "Modelo no inicializado"}), 503\n'
    '    status = get_retrain_status()\n'
    '    if status["is_running"]:\n'
    '        return jsonify({"message": "Ya en curso", "status": status}), 409\n'
    '    run_retrain_async(_pm, _lm, _cal, _f)\n'
    '    return jsonify({"message": "Iniciado", "status": status})\n'
)

new_endpoint = (
    '@app.route("/api/retrain", methods=["POST"])\n'
    'def trigger_retrain():\n'
    '    _pm  = _models.get("pm")\n'
    '    _lm  = _models.get("lm")\n'
    '    _cal = _models.get("cal")\n'
    '    _f   = _models.get("fetcher")\n'
    '    if _pm is None:\n'
    '        return jsonify({"message": "Modelo no inicializado"}), 503\n'
    '    status = get_retrain_status()\n'
    '    if status["is_running"]:\n'
    '        return jsonify({"message": "Ya en curso", "status": status}), 409\n'
    '    run_retrain_async(_pm, _lm, _cal, _f)\n'
    '    return jsonify({"message": "Iniciado", "status": status})\n'
)

if old_endpoint in api:
    api = api.replace(old_endpoint, new_endpoint)
    changed.append('endpoint actualizado')
else:
    print('WARNING: endpoint no encontrado exacto, buscando alternativa...')
    # Buscar y mostrar el endpoint actual
    idx = api.find('@app.route("/api/retrain", methods=["POST"])')
    if idx >= 0:
        print('Endpoint actual:')
        print(repr(api[idx:idx+400]))

# 4. Tambien actualizar el scheduler para usar _models
old_sched = '_scheduled_retrain, trigger=IntervalTrigger(hours=24)'
if '_models.get' not in api and 'run_retrain_async(pm, lm, cal, fetcher)' in api:
    api = api.replace(
        'run_retrain_async(pm, lm, cal, fetcher)',
        'run_retrain_async(_models.get("pm"), _models.get("lm"), _models.get("cal"), _models.get("fetcher"))'
    )
    changed.append('scheduler actualizado')

with open('dashboard/api.py', 'w', encoding='utf-8') as f:
    f.write(api)

print('OK:', ', '.join(changed) if changed else 'sin cambios adicionales')
