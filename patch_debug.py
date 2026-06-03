import re

with open('dashboard/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

debug_route = '''
@app.route("/api/debug-apisports", methods=["GET"])
def debug_apisports():
    import os, requests as req
    key = os.getenv("APISPORTS_KEY", "")
    if not key:
        return jsonify({"error": "KEY no configurada", "key_len": 0})
    try:
        r = req.get("https://v3.football.api-sports.io/fixtures",
            headers={"x-apisports-key": key},
            params={"team": 486, "season": 2025, "last": 3, "status": "FT"},
            timeout=15)
        return jsonify({"status": r.status_code, "key_prefix": key[:8], "response": r.json()})
    except Exception as e:
        return jsonify({"error": str(e)})

'''

# Insertar antes del ultimo if __name__
content = content.replace('if __name__ == "__main__":', debug_route + 'if __name__ == "__main__":')

with open('dashboard/api.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("OK")
