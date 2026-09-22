# MediRescue 🚑

> **AWS-powered emergency response platform connecting patients, hospitals, and ambulance drivers through a real-time SOS workflow.**

MediRescue is a hackathon-ready emergency response platform built with Flask and AWS. It connects patients, verified hospitals, and ambulance drivers through an end-to-end emergency workflow including SOS activation, safety confirmation, hospital matching, ambulance dispatch, routing, ETA calculation, notifications, and emergency completion.

The application is deployed on **AWS EC2** using **Gunicorn, Nginx, and Cloudflare Tunnel**.

---

## 🌐 Live Demo

MediRescue is exposed through a public Cloudflare Tunnel.

Replace `YOUR-CLOUDFLARE-URL` with the current public URL before submission.

### Patient Portal
```text
https://YOUR-CLOUDFLARE-URL/
```

### Hospital Portal
```text
https://YOUR-CLOUDFLARE-URL/hospital
```

### Ambulance Driver Portal
```text
https://YOUR-CLOUDFLARE-URL/driver
```

### Admin Portal
```text
https://YOUR-CLOUDFLARE-URL/admin
```

> **Important:** `http://127.0.0.1:5000` is only the local Flask development address. It is **not** the public demo URL.

---

# 🚨 What MediRescue Does

MediRescue provides an end-to-end emergency response workflow:

1. Patient starts an SOS.
2. A short safety countdown allows accidental cancellation.
3. The emergency is created and hospitals are ranked using location/distance data.
4. Verified hospitals can accept the emergency.
5. A suitable ambulance driver can be dispatched.
6. The driver confirms dispatch and pickup.
7. Amazon Location Routes V2 provides road distance and ETA.
8. Amazon SNS sends critical emergency notifications.
9. The emergency is completed through the hospital/driver workflow.
10. Admins manage hospital and ambulance-driver verification.

---

# ✨ Main Features

## 🧑 Patient
- One-tap SOS workflow
- Safety countdown before emergency broadcast
- Emergency status tracking
- Hospital matching
- Ambulance/driver assignment visibility
- Road distance and ETA
- Emergency completion flow

## 🏥 Hospital
- Hospital authentication and verification
- Incoming emergency requests
- Accept emergency requests
- Emergency status management
- Hospital-side emergency workflow

## 🚑 Ambulance Driver
- Driver authentication and verification
- Assigned emergency view
- Dispatch confirmation
- Pickup confirmation
- Emergency completion
- Driver-side status updates

## 🧑‍💼 Admin
- Admin authentication
- Hospital verification/rejection
- Ambulance driver verification/rejection
- Pending registration management
- Emergency overview
- Creation of verified hospital/driver records

> The admin portal is primarily a verification and operational-management layer. Emergency dispatch follows the application's emergency workflow.

---

# 🏗️ Architecture

```text
                         Internet
                            │
                            ▼
                  ┌──────────────────┐
                  │ Cloudflare Tunnel│
                  └────────┬─────────┘
                           │
                           ▼
                     ┌─────────────┐
                     │    Nginx    │
                     └──────┬──────┘
                            │
                            ▼
                     ┌─────────────┐
                     │   Gunicorn  │
                     └──────┬──────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │ Flask MediRescue │
                  │      app.py      │
                  └────────┬─────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
         ┌─────────┐   ┌─────────┐  ┌─────────────────┐
         │DynamoDB │   │   SNS   │  │ Amazon Location │
         │         │   │         │  │   Routes V2     │
         └─────────┘   └─────────┘  └─────────────────┘
```

---

# ☁️ AWS Services

| AWS Service | Purpose |
|---|---|
| **Amazon EC2** | Application hosting |
| **Amazon DynamoDB** | Emergency/application data |
| **Amazon SNS** | Critical emergency notifications |
| **Amazon Location Routes V2** | Road distance and ETA |
| **AWS IAM** | AWS resource permissions |

---

# 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python / Flask |
| Application Server | Gunicorn |
| Reverse Proxy | Nginx |
| Public Access | Cloudflare Tunnel |
| Compute | AWS EC2 |
| Database | Amazon DynamoDB |
| Notifications | Amazon SNS |
| Routing | Amazon Location Routes V2 |
| Authentication | Flask/application authentication |
| Service Manager | systemd |
| Testing | Python unittest |

---

# 📁 Project Structure

```text
MediRescue/
├── app.py
├── app_live_server.py
├── aws_services.py
├── requirements.txt
├── README.md
├── templates/
│   ├── patient.html
│   ├── hospital.html
│   ├── driver.html
│   └── admin.html
├── static/
│   ├── style.css
│   ├── patient.js
│   └── ...
├── tests/
│   ├── test_*.py
│   └── ...
└── .gitignore
```

Generated/cache files, credentials, databases, private keys, and virtual environments should not be committed.

---

# 🚀 Local Development

## 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd MediRescue
```

Or, on the existing EC2 deployment:

```bash
cd /home/ubuntu/MediRescue/MediRescue
```

## 2. Create and activate the virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

## 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Run locally

```bash
python app.py
```

Local development address:

```text
http://127.0.0.1:5000
```

> This is a **local development address only**. The hackathon demo uses the public Cloudflare URL.

---

# 🔐 Production Security

Production secrets are stored outside the repository, for example:

```text
/etc/medirescue.env
```

Example:

```env
AWS_ENABLED=true
AWS_REGION=ap-south-1
MEDIRESCUE_ADMIN_PASSWORD=YOUR_STRONG_ADMIN_PASSWORD
MEDIRESCUE_SECRET=YOUR_LONG_RANDOM_SECRET
```

Protect the file:

```bash
sudo chmod 600 /etc/medirescue.env
```

Never commit:

```text
.env
*.pem
*.ppk
*.db
AWS access keys
AWS secret keys
Cloudflare tunnel credentials
production passwords
private SSH keys
```

The production application uses the EC2 IAM role for AWS access where applicable rather than hardcoding AWS credentials.

---

# 🦄 Production Deployment

MediRescue runs on AWS EC2 with:

```text
Cloudflare Tunnel
        ↓
Nginx :80
        ↓
Gunicorn :8000
        ↓
Flask
        ↓
AWS Services
```

Typical Gunicorn binding:

```text
127.0.0.1:8000
```

Typical Nginx-to-Gunicorn proxy:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Check the actual production service before changing it:

```bash
sudo systemctl cat medirescue
```

---

# 📍 Amazon Location Routes V2

MediRescue integrates with **Amazon Location Routes V2** for road-based routing.

The route helper returns:

```text
distance_km
eta_minutes
source
```

Example:

```json
{
  "distance_km": 7.39,
  "eta_minutes": 13,
  "source": "amazon_location_routes_v2"
}
```

---

# 📢 Amazon SNS

MediRescue uses **Amazon SNS** for critical emergency notifications.

The emergency workflow can publish structured emergency information to the configured SNS topic, allowing configured subscribers to receive notifications.

---

# 🔄 Emergency Lifecycle

```text
PATIENT STARTS SOS
        │
        ▼
PENDING_CONFIRMATION
        │
        ▼
Safety Countdown
        │
        ▼
HOSPITAL_BROADCAST
        │
        ▼
Hospital Accepts
        │
        ▼
Ambulance Assigned
        │
        ▼
Driver Dispatch
        │
        ▼
Driver Pickup
        │
        ▼
Hospital Reached
        │
        ▼
COMPLETED
```

---

# 🔌 Important API Routes

Core application routes include:

```text
/api/sos/start
/api/emergency/<id>/eta
/api/admin/login
/api/admin/overview
/api/admin/pending
/api/admin/verify
```

Additional hospital and driver endpoints are implemented in:

```text
app.py
```

---

# 🧪 Testing

Run the complete test suite:

```bash
cd /home/ubuntu/MediRescue/MediRescue
source venv/bin/activate
python -m unittest discover -s tests -p "test_*.py" -v
```

Current verified result:

```text
Ran 8 tests
OK
```

The tests cover important behavior including:

- SOS safety window
- SOS cancellation
- GPS validation
- Hospital acceptance
- Duplicate acceptance protection
- Driver dispatch lifecycle
- Driver pickup/completion
- Emergency timeline events

Syntax check:

```bash
python -m py_compile app.py
```

---

# 🔍 Production Health Checks

Check services:

```bash
sudo systemctl status medirescue
sudo systemctl status nginx
sudo systemctl status cloudflared-mediservice
```

Check Gunicorn:

```bash
curl -I http://127.0.0.1:8000
```

Check Nginx:

```bash
curl -I http://127.0.0.1
```

> These `127.0.0.1` addresses are **internal server health checks**, not browser/demo addresses.

View application logs:

```bash
sudo journalctl -u medirescue -n 100 --no-pager
```

View Cloudflare logs:

```bash
sudo journalctl -u cloudflared-mediservice -n 100 --no-pager
```

---

# 🧑‍💼 Admin Portal

```text
/admin
```

Admin functionality:

- Admin authentication
- Hospital verification
- Ambulance driver verification
- Pending registration review
- Emergency overview
- Operational management

---

# 🏥 Hospital Portal

```text
/hospital
```

Hospitals can:

- Authenticate
- View incoming emergencies
- Accept emergency requests
- Update emergency status
- Complete the hospital-side workflow

---

# 🚑 Driver Portal

```text
/driver
```

Drivers can:

- Authenticate
- View assigned emergencies
- Dispatch
- Confirm pickup
- Update trip status
- Complete the emergency workflow

---

# 🧑 Patient Portal

```text
/
```

Patient flow:

1. Start SOS
2. Safety countdown
3. Confirm emergency
4. Broadcast emergency
5. Hospital matching
6. Ambulance/driver workflow
7. ETA/routing
8. Completion

---

# 🏆 Demo Flow

### 1. Patient

Open:

```text
https://YOUR-CLOUDFLARE-URL/
```

Start an SOS.

### 2. Safety Confirmation

Show the safety countdown and confirm the emergency.

### 3. Emergency Broadcast

Demonstrate hospital matching and emergency status.

### 4. Hospital

Open:

```text
https://YOUR-CLOUDFLARE-URL/hospital
```

Accept the emergency.

### 5. Driver

Open:

```text
https://YOUR-CLOUDFLARE-URL/driver
```

Dispatch the ambulance and confirm pickup.

### 6. Routing

Show road distance and ETA powered by Amazon Location Routes V2.

### 7. Notification

Demonstrate the SNS notification generated by the emergency workflow.

### 8. Completion

Complete the emergency workflow.

### 9. Admin

Open:

```text
https://YOUR-CLOUDFLARE-URL/admin
```

Demonstrate verification and operational management.

---

# 🏥 Production Disclaimer

MediRescue is a **hackathon/prototype emergency-response system**.

A real healthcare deployment would require additional controls including:

- Stronger authentication and authorization
- Detailed audit logging
- Encryption and key management
- Privacy and compliance controls
- Rate limiting
- Monitoring and alerting
- Disaster recovery
- Secure patient-data handling
- Formal security review

The project should not be treated as a production medical system without these additional controls.

---

# 📊 Current Project Verification

The current project has been verified for:

- Flask application syntax
- Automated test suite
- Production Gunicorn service
- Nginx service
- Cloudflare Tunnel service
- Amazon SNS notification integration
- Amazon Location Routes V2 integration
- Production debug mode disabled
- Production admin password stored outside the repository
- Sensitive/private deployment files excluded from the submission ZIP

Current automated test result:

```text
8 tests
8 passed
```

---

# 🛠️ Quick Command Cheat Sheet

```bash
# Project
cd /home/ubuntu/MediRescue/MediRescue
source venv/bin/activate

# Test
python -m unittest discover -s tests -p "test_*.py" -v

# Syntax
python -m py_compile app.py

# App service
sudo systemctl restart medirescue
sudo systemctl status medirescue
sudo journalctl -u medirescue -n 100 --no-pager

# Nginx
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl status nginx

# Cloudflare
sudo systemctl restart cloudflared-mediservice
sudo systemctl status cloudflared-mediservice
sudo journalctl -u cloudflared-mediservice -n 100 --no-pager

# Internal health checks
curl -I http://127.0.0.1:8000
curl -I http://127.0.0.1

# Resources
df -h
free -h
sudo ss -lntp
```

---

# 👨‍💻 MediRescue

**MediRescue — AWS Emergency Response Platform**

Built with:

**Flask · AWS EC2 · DynamoDB · SNS · Amazon Location Routes V2 · Gunicorn · Nginx · Cloudflare Tunnel**

> Built as a hackathon project demonstrating an end-to-end emergency response workflow using AWS.
