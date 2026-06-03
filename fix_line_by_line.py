"""fix_line_by_line.py — fix directo buscando lineas problematicas"""

with open('dashboard/api.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Mostrar lineas 53-75 para entender el estado actual
print("=== Estado actual 53-75 ===")
for i, line in enumerate(lines[52:75], start=53):
    print(f"{i}: {repr(line)}")

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Detectar lineas _models[...] = ... sin indentacion (fuera de funcion)
    # Solo las que estan sin indentar y no son la declaracion global
    stripped = line.strip()
    
    if (stripped.startswith('_models["pm"]') or 
        stripped.startswith('_models["lm"]') or
        stripped.startswith('_models["cal"]') or
        stripped.startswith('_models["fetcher"]')):
        
        # Verificar si esta sin indentacion (problema)
        if not line.startswith('    '):
            print(f"Linea {i+1} con problema: {repr(line)}")
            # Agregar con indentacion correcta
            new_lines.append('    ' + stripped + '\n')
            i += 1
            continue
    
    new_lines.append(line)
    i += 1

with open('dashboard/api.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

# Verificar sintaxis
import ast
try:
    ast.parse(open('dashboard/api.py', encoding='utf-8').read())
    print("\n✅ Sintaxis OK")
except SyntaxError as e:
    print(f"\n❌ SyntaxError en linea {e.lineno}: {e.msg}")
    print(f"   Texto: {repr(e.text)}")

print("\n=== Estado final 53-75 ===")
with open('dashboard/api.py', 'r', encoding='utf-8') as f:
    lines2 = f.readlines()
for i, line in enumerate(lines2[52:75], start=53):
    print(f"{i}: {repr(line)}")
