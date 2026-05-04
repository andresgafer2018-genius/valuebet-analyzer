import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from dashboard.api import app

if __name__ == "__main__":
    import threading
    import webbrowser
    import time

    port = int(os.getenv("PORT", 5050))

    def open_browser():
        time.sleep(2)
        webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=port, debug=False)
