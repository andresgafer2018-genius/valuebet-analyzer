"""fix_indent.py — corrige IndentationError en api.py linea 57"""

with open('dashboard/api.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Mostrar contexto alrededor de linea 57
print("=== Contexto lineas 50-65 ===")
for i, line in enumerate(lines[49:64], start=50):
    print(f"{i}: {repr(line)}")

# Buscar y corregir el problema
fixed = []
for i, line in enumerate(lines):
    # Si hay una linea con _models = {} mal indentada, corregirla
    stripped = line.lstrip()
    if '_models = {}' in stripped and line.startswith(' ') and not lines[i-1].rstrip().endswith(':'):
        # Esta linea no deberia estar indentada
        fixed.append(stripped)
        print(f"Linea {i+1} corregida: {repr(line)} -> {repr(stripped)}")
    else:
        fixed.append(line)

with open('dashboard/api.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed)

print("\n=== Contexto despues del fix ===")
with open('dashboard/api.py', 'r', encoding='utf-8') as f:
    lines2 = f.readlines()
for i, line in enumerate(lines2[49:64], start=50):
    print(f"{i}: {repr(line)}")

print("\nOK")
