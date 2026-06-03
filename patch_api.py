import sys

filepath = sys.argv[1]

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: agregar create_user_settings_table al import
old1 = 'from database.db import init_db'
new1 = 'from database.db import init_db, create_user_settings_table'

# Fix 2: llamar create_user_settings_table despues de init_db
old2 = '    init_db()\n    _db_available = True'
new2 = '    init_db()\n    create_user_settings_table()\n    _db_available = True'

if old1 in content:
    content = content.replace(old1, new1)
    print("✅ Fix 1 aplicado: import")
else:
    print("⚠️  Fix 1 no encontrado")

if old2 in content:
    content = content.replace(old2, new2)
    print("✅ Fix 2 aplicado: create_user_settings_table()")
else:
    print("⚠️  Fix 2 no encontrado - intentando con CRLF")
    old2_crlf = '    init_db()\r\n    _db_available = True'
    new2_crlf = '    init_db()\r\n    create_user_settings_table()\r\n    _db_available = True'
    if old2_crlf in content:
        content = content.replace(old2_crlf, new2_crlf)
        print("✅ Fix 2 aplicado con CRLF")
    else:
        print("❌ Fix 2 falló también con CRLF")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Listo.")
