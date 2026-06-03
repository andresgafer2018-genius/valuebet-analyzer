import re

with open("dashboard/api.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('best_bk["bookmaker_key"]', 'best_bk["bk_key"]')
content = content.replace('best_bk["bookmaker_name"]', 'best_bk["bk_name"]')
content = content.replace('best_bk["bookmaker_url"]', 'best_bk["bk_url"]')

with open("dashboard/api.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Fix aplicado OK")
