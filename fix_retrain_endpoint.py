"""fix_retrain_endpoint.py"""

with open('dashboard/api.py', 'r', encoding='utf-8') as f:
    api = f.read()

# Reemplazar el endpoint trigger_retrain completo
old = (
    '@app.route("/api/retrain", methods=["POST"])\n'
    'def trigger_retrain():\n'
    '    status = get_retrain_status()\n'
    '    if status["is_running"]:\n'
    '        return jsonify({"message": "Ya en curso", "status": status}), 409\n'
    '    run_retrain_async(pm, lm, cal, fetcher)\n'
    '    return jsonify({"message": "Iniciado", "status": status})\n'
)

new = (
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

if old in api:
    api = api.replace(old, new)
    print('OK - endpoint reemplazado')
else:
    # Buscar variante sin el status check
    old2 = (
        '@app.route("/api/retrain", methods=["POST"])\n'
        'def trigger_retrain():\n'
    )
    idx = api.find(old2)
    if idx >= 0:
        print(f'Endpoint encontrado en posicion {idx}')
        # Mostrar contexto
        print(repr(api[idx:idx+300]))
    else:
        print('ERROR: endpoint no encontrado')
    print('Sin cambios')
    exit(1)

with open('dashboard/api.py', 'w', encoding='utf-8') as f:
    f.write(api)

print('api.py guardado OK')
