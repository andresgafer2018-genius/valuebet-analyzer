"""fix_models_indent.py — mueve _models dentro de _train_and_analyze y lo declara global"""

with open('dashboard/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Agregar declaracion global _models al inicio del archivo (nivel modulo)
if '\n_models = {}  # Referencia global para endpoints\n' in content:
    # Sacar la linea suelta que esta fuera de la funcion
    content = content.replace('\n_models = {}  # Referencia global para endpoints\n', '\n')

# 2. Agregar _models = {} a nivel modulo antes de _train_and_analyze
if '_models: dict = {}' not in content and 'global _models' not in content:
    content = content.replace(
        'def _train_and_analyze():',
        '_models: dict = {}  # Referencia global para retrain endpoint\n\ndef _train_and_analyze():'
    )

# 3. Agregar "global _models" al inicio de _train_and_analyze
if 'global _models' not in content:
    content = content.replace(
        'def _train_and_analyze():\n    log.info("Entrenando modelos...")',
        'def _train_and_analyze():\n    global _models\n    log.info("Entrenando modelos...")'
    )

# 4. Mover las asignaciones _models["pm"] etc. DENTRO de la funcion (con indentacion)
# Primero sacarlas de donde estan (sin indentacion)
lines_to_fix = [
    '_models["pm"] = pm if "pm" in dir() else None\n',
    '_models["lm"] = lm if "lm" in dir() else None\n',
    '_models["cal"] = cal\n',
    '_models["fetcher"] = fetcher\n',
]
for line in lines_to_fix:
    content = content.replace(line, '')

# 5. Insertarlas correctamente despues de "cal = ProbabilityCalibrator()" con indentacion
content = content.replace(
    '    cal = ProbabilityCalibrator()\n',
    '    cal = ProbabilityCalibrator()\n'
    '    _models["pm"] = pm\n'
    '    _models["lm"] = lm\n'
    '    _models["cal"] = cal\n'
    '    _models["fetcher"] = fetcher\n'
)

with open('dashboard/api.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Verificar resultado
with open('dashboard/api.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== Contexto lineas 53-75 ===")
for i, line in enumerate(lines[52:75], start=53):
    print(f"{i}: {repr(line)}")

# Verificar sintaxis
import ast
try:
    ast.parse(open('dashboard/api.py', encoding='utf-8').read())
    print("\n✅ Sintaxis OK")
except SyntaxError as e:
    print(f"\n❌ SyntaxError: {e}")
