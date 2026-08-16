"""Development server entrypoint.

Adds the project root (for `agent`) and this directory (for `src`) to
sys.path, then runs the Flask app.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, Path(__file__).resolve().parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.app import app  # noqa: E402

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)