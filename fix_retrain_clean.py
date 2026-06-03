"""fix_retrain_clean.py — fix definitivo del endpoint retrain"""
import ast

with open('dashboard/api.py', 'r', encoding='utf-8') as f:
    api = f.read()

# Verificar estado inicial
print("Buscando patrones...")
print(f"  'run_retrain_async(poisson': {'SI' if 'run_retrain_async(poisson' in api else 'NO'}")
print(f"  'run_retrain_async(pm':      {'SI' if 'run_retrain_async(pm' in api else 'NO'}")
print(f"  '_models':                   {'SI' if '_models' in api else 'NO'}")

# Fix 1: reemplazar variables incorrectas en el endpoint
api = api.replace(
    'run_retrain_async(poisson, logistic, calibrator, fetcher)',
    'run_retrain_async(pm, lm, cal, fetcher)'
)

# Fix 2: reemplazar en el scheduler si existe
api = api.replace(
    'run_retrain_async(poisson, logistic, calibrator, fetcher)',
    'run_retrain_async(pm, lm, cal, fetcher)'
)

# Fix 3: el endpoint usa variables locales de modulo - hacerlas globales
# Agregar global _pm, _lm, _cal, _fetcher NO es necesario porque
# pm, lm, cal, fetcher son variables de modulo (no locales de funcion)
# El problema es que estan DENTRO de _train_and_analyze()
# Solución: declararlas como global al inicio de _train_and_analyze

if 'global pm, lm, cal, fetcher' not in api:
    api = api.replace(
        'def _train_and_analyze():\n    log.info("Entrenando modelos...")',
        'def _train_and_analyze():\n    global pm, lm, cal, fetcher\n    log.info("Entrenando modelos...")'
    )
    print("  global pm,lm,cal,fetcher agregado en _train_and_analyze")

# Verificar sintaxis antes de guardar
try:
    ast.parse(api)
    print("\n✅ Sintaxis OK")
except SyntaxError as e:
    print(f"\n❌ SyntaxError linea {e.lineno}: {e.msg} — {repr(e.text)}")
    exit(1)

with open('dashboard/api.py', 'w', encoding='utf-8') as f:
    f.write(api)

print("✅ api.py guardado")

# Verificar resultado
with open('dashboard/api.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
print("\n=== Lineas 53-58 ===")
for i, line in enumerate(lines[52:58], start=53):
    print(f"{i}: {line}", end='')
