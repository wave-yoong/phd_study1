"""
Deprecated entrypoint.

The canonical server now lives in backend/app.py (single Flask app that
auto-selects the real LLM or the mock agent and handles experimental
conditions). This shim re-exports that app so older commands keep working.

Run instead, from the repository root:
    ./run.sh          # real LLM
    ./run.sh demo     # mock agent, no API key
or:
    python -m backend.app
"""

import os
import sys

# Make the repository root importable so `backend` / `services` resolve even when
# this file is executed directly (python backend/run.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
