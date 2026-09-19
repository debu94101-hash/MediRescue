"""Compatibility launcher for the MediRescue local server.

The project previously had two Flask applications (app.py and app_live_server.py),
which caused features to diverge. This launcher now starts the single canonical
application so Patient, Hospital, Driver, GPS and SOS routes stay in sync.
"""
from app import app, init_db

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
