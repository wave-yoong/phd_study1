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

from backend.app import app

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
