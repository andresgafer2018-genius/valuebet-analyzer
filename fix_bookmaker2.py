with open("dashboard/api.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('best_bk["bk_key"]', 'best_bk.get("bookmaker_key") or best_bk.get("bk_key", "simulated")')
content = content.replace('best_bk["bk_name"]', 'best_bk.get("bookmaker_name") or best_bk.get("bk_name", "Bookmaker")')
content = content.replace('best_bk["bk_url"]', 'best_bk.get("bookmaker_url") or best_bk.get("bk_url", "")')

with open("dashboard/api.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Fix aplicado OK")
