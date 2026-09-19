MediRescue - Live Server + Flask setup

1. Put patient.html in your frontend folder and open it with VS Code Live Server.
2. Install dependencies:
   python -m pip install -r requirements_live_server.txt
3. Run backend:
   python app_live_server.py
4. Open the patient page with Live Server, normally:
   http://127.0.0.1:5500/patient.html

Backend API runs on:
   http://127.0.0.1:5000

The patient page automatically sends API requests to port 5000 when served from Live Server port 5500. CORS and credentials are enabled in the Flask backend.

Important: do NOT use `mode: no-cors`.
