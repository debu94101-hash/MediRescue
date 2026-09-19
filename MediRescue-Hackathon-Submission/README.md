# MediRescue 🚑

**MediRescue** is an AWS-powered emergency response platform that connects patients, hospitals, and ambulance drivers through a real-time SOS, hospital matching, ambulance dispatch, routing, and notification workflow.

Built as a hackathon-ready Flask application and deployed on **AWS EC2** with **Nginx + Gunicorn + Cloudflare Tunnel**.

---

## 🚨 What MediRescue Does

MediRescue provides an end-to-end emergency workflow:

1. A patient starts an SOS.
2. A short safety countdown allows cancellation before broadcasting.
3. The emergency is created and hospitals are ranked using location/distance data.
4. Verified hospitals can accept the emergency.
5. A suitable ambulance driver can be dispatched.
6. The driver updates the trip through dispatch and pickup.
7. Amazon Location Routes V2 can calculate route distance and ETA.
8. Amazon SNS sends critical emergency notifications.
9. The hospital marks the emergency as reached/completed.
10. Admins manage verification of hospitals and ambulance drivers.

The application is designed to demonstrate how AWS services can be combined with a Flask application to create a practical emergency-response workflow.

---

## ✨ Main Features

### Patient
- One-tap SOS workflow
- Safety countdown before broadcast
- Emergency creation and status tracking
- Hospital matching
- Ambulance/driver assignment visibility
- Emergency ETA information
- Emergency completion flow

### Hospital
- Hospital login/verification flow
- View incoming emergencies
- Accept emergency requests
- Manage emergency status
- Hospital-side emergency workflow

### Ambulance Driver
- Driver login/verification
- View assigned emergencies
- Dispatch confirmation
- Pickup confirmation
- Emergency completion
- Driver-side status updates

### Admin
- Admin authentication
- Verify/reject hospitals
- Verify/reject ambulance drivers
- View pending registrations
- View emergency overview
- Create verified hospital/driver records
- Operational verification/control layer

> The admin portal is primarily a verification and operational-management layer. Emergency dispatch itself follows the application workflow rather than requiring the admin to manually dispatch every emergency.

---

# 🏗️ Architecture

## Production Architecture

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
                  ┌─────────────────┐
                  │ Flask MediRescue│
                  │     app.py      │
                  └────────┬────────┘
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
     ┌─────────┐      ┌─────────┐     ┌──────────────┐
     │DynamoDB │      │   SNS   │     │Amazon Location│
     │         │      │         │     │ Routes V2     │
     └─────────┘      └─────────┘     └──────────────┘
```

### AWS services used

- **Amazon EC2** — application hosting
- **Amazon DynamoDB** — emergency/application data
- **Amazon SNS** — critical emergency notifications
- **Amazon Location Service / Routes V2** — distance and ETA calculation
- **AWS IAM** — permissions for the EC2 instance role

### Infrastructure used

- Ubuntu on EC2
- Python
- Flask
- Gunicorn
- Nginx
- Cloudflare Tunnel
- systemd

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

Generated/cache files such as virtual environments, Python bytecode, databases, backups, credentials, and private keys should not be committed.

---

# 🧰 Tech Stack

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

# 🚀 Local Development

## 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd MediRescue
```

If the project is already on the EC2 instance:

```bash
cd /home/ubuntu/MediRescue/MediRescue
```

---

## 2. Create a Python virtual environment

```bash
python3 -m venv venv
```

Activate it:

```bash
source venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Run locally

```bash
python app.py
```

The Flask development server normally runs on:

```text
http://127.0.0.1:5000
```

For local development, debug mode should only be enabled intentionally. Production must use `debug=False`.

---

# ☁️ AWS / EC2 Deployment

The following commands describe the production setup used by MediRescue.

## 1. Connect to EC2

From Windows PowerShell:

```powershell
ssh -i "C:\path\to\MediRescue-Key.pem" ubuntu@<EC2_PUBLIC_IP>
```

**Never commit or share the `.pem` private key.**

---

## 2. Go to the project

```bash
cd /home/ubuntu/MediRescue/MediRescue
```

Check the project:

```bash
ls -la
```

---

## 3. Create/activate the virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

Upgrade pip:

```bash
pip install --upgrade pip
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# 🔐 Production Environment Variables

Production secrets should not be stored in GitHub.

MediRescue can use a protected environment file such as:

```text
/etc/medirescue.env
```

Create/edit it:

```bash
sudo nano /etc/medirescue.env
```

Example:

```env
AWS_ENABLED=true
AWS_REGION=ap-south-1

MEDIRESCUE_ADMIN_PASSWORD=YOUR_STRONG_ADMIN_PASSWORD

# Recommended for production:
MEDIRESCUE_SECRET=YOUR_LONG_RANDOM_SECRET
```

Do not put real production passwords, API keys, AWS access keys, Cloudflare credentials, or other secrets in this README.

Protect the file:

```bash
sudo chmod 600 /etc/medirescue.env
```

---

# 🔑 systemd EnvironmentFile

Create the systemd drop-in directory:

```bash
sudo mkdir -p /etc/systemd/system/medirescue.service.d
```

Create:

```bash
sudo nano /etc/systemd/system/medirescue.service.d/security.conf
```

Add:

```ini
[Service]
EnvironmentFile=/etc/medirescue.env
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Restart MediRescue:

```bash
sudo systemctl restart medirescue
```

Check:

```bash
sudo systemctl status medirescue
```

---

# 🦄 Gunicorn Production Service

A typical production service looks like this:

```ini
[Unit]
Description=MediRescue Flask Application
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/MediRescue/MediRescue
Environment="PATH=/home/ubuntu/MediRescue/MediRescue/venv/bin"
EnvironmentFile=/etc/medirescue.env
ExecStart=/home/ubuntu/MediRescue/MediRescue/venv/bin/gunicorn \
    --workers 2 \
    --bind 127.0.0.1:8000 \
    app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Save it as:

```bash
sudo nano /etc/systemd/system/medirescue.service
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable medirescue
sudo systemctl restart medirescue
sudo systemctl status medirescue
```

Check Gunicorn locally:

```bash
curl -I http://127.0.0.1:8000
```

> If an existing production service file is already configured, inspect it before replacing it:
>
> ```bash
> sudo systemctl cat medirescue
> ```

---

# 🌐 Nginx

Nginx sits in front of Gunicorn.

Typical configuration:

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Example location:

```bash
sudo nano /etc/nginx/sites-available/medirescue
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/medirescue /etc/nginx/sites-enabled/medirescue
```

Test configuration:

```bash
sudo nginx -t
```

Restart:

```bash
sudo systemctl restart nginx
```

Enable on boot:

```bash
sudo systemctl enable nginx
```

Check:

```bash
sudo systemctl status nginx
```

Test from EC2:

```bash
curl -I http://127.0.0.1
```

---

# ☁️ Cloudflare Tunnel

MediRescue production is exposed through a **Cloudflare Tunnel** instead of requiring the Flask application to be directly exposed to the public internet.

The flow is:

```text
Browser
   ↓
Cloudflare
   ↓
Cloudflare Tunnel
   ↓
EC2
   ↓
Nginx :80
   ↓
Gunicorn :8000
   ↓
Flask
```

## Check the existing tunnel service

```bash
sudo systemctl status cloudflared-mediservice
```

Start:

```bash
sudo systemctl start cloudflared-mediservice
```

Restart:

```bash
sudo systemctl restart cloudflared-mediservice
```

Enable on boot:

```bash
sudo systemctl enable cloudflared-mediservice
```

View logs:

```bash
sudo journalctl -u cloudflared-mediservice -n 100 --no-pager
```

Follow logs live:

```bash
sudo journalctl -u cloudflared-mediservice -f
```

---

## Generic Cloudflare Tunnel setup

If creating a new tunnel from scratch, install `cloudflared` using the official Cloudflare instructions.

Authenticate:

```bash
cloudflared tunnel login
```

Create a tunnel:

```bash
cloudflared tunnel create medirescue
```

A tunnel-specific UUID/credential is generated by Cloudflare. Do not commit that credential to GitHub.

A typical tunnel configuration points the public hostname to Nginx:

```yaml
tunnel: <YOUR_TUNNEL_UUID>
credentials-file: /path/to/<YOUR_TUNNEL_UUID>.json

ingress:
  - hostname: <YOUR_DOMAIN>
    service: http://127.0.0.1:80
  - service: http_status:404
```

Route DNS:

```bash
cloudflared tunnel route dns medirescue <YOUR_DOMAIN>
```

The exact Cloudflare configuration is deployment-specific and should never contain credentials in the public repository.

---

# 🔄 Production Service Commands

## MediRescue

```bash
sudo systemctl start medirescue
sudo systemctl stop medirescue
sudo systemctl restart medirescue
sudo systemctl status medirescue
```

Enable at boot:

```bash
sudo systemctl enable medirescue
```

Logs:

```bash
sudo journalctl -u medirescue -n 100 --no-pager
```

Live logs:

```bash
sudo journalctl -u medirescue -f
```

---

## Nginx

```bash
sudo systemctl start nginx
sudo systemctl stop nginx
sudo systemctl restart nginx
sudo systemctl status nginx
```

Test configuration:

```bash
sudo nginx -t
```

Logs:

```bash
sudo journalctl -u nginx -n 100 --no-pager
```

---

## Cloudflare Tunnel

```bash
sudo systemctl start cloudflared-mediservice
sudo systemctl stop cloudflared-mediservice
sudo systemctl restart cloudflared-mediservice
sudo systemctl status cloudflared-mediservice
```

Logs:

```bash
sudo journalctl -u cloudflared-mediservice -n 100 --no-pager
```

---

# 🧪 Testing

Run the complete test suite:

```bash
cd /home/ubuntu/MediRescue/MediRescue
source venv/bin/activate
python -m unittest discover -s tests -p "test_*.py" -v
```

The current project test suite has been verified with:

```text
Ran 8 tests
OK
```

---

# 🧹 Syntax Check

Before restarting production:

```bash
python -m py_compile app.py
```

Optional compile check for the supporting server file:

```bash
python -m py_compile app_live_server.py
```

---

# 🔍 Production Health Checks

Check all services:

```bash
sudo systemctl status medirescue
sudo systemctl status nginx
sudo systemctl status cloudflared-mediservice
```

Check Gunicorn directly:

```bash
curl -I http://127.0.0.1:8000
```

Check Nginx:

```bash
curl -I http://127.0.0.1
```

Check recent MediRescue logs:

```bash
sudo journalctl -u medirescue -n 100 --no-pager
```

Quick error search:

```bash
sudo journalctl -u medirescue --since "30 minutes ago" --no-pager | grep -Ei "error|exception|traceback"
```

---

# 🐛 Troubleshooting

## App is not starting

```bash
sudo systemctl status medirescue
sudo journalctl -u medirescue -n 200 --no-pager
```

Check Python:

```bash
python3 --version
```

Check Gunicorn:

```bash
/home/ubuntu/MediRescue/MediRescue/venv/bin/gunicorn --version
```

Check syntax:

```bash
cd /home/ubuntu/MediRescue/MediRescue
source venv/bin/activate
python -m py_compile app.py
```

---

## Nginx gives 502

Check Gunicorn:

```bash
sudo systemctl status medirescue
curl -I http://127.0.0.1:8000
```

Check Nginx:

```bash
sudo nginx -t
sudo systemctl status nginx
```

Check logs:

```bash
sudo journalctl -u nginx -n 100 --no-pager
sudo journalctl -u medirescue -n 100 --no-pager
```

---

## Cloudflare Tunnel is not working

```bash
sudo systemctl status cloudflared-mediservice
sudo journalctl -u cloudflared-mediservice -n 200 --no-pager
```

Then verify Nginx locally:

```bash
curl -I http://127.0.0.1
```

If Nginx works locally but Cloudflare does not, inspect the tunnel configuration and Cloudflare DNS/hostname configuration.

---

# 🔐 Security Checklist

Never commit any of the following:

```text
*.pem
*.ppk
.env
*.db
AWS access keys
AWS secret keys
Cloudflare tunnel credentials
production passwords
private SSH keys
```

Recommended `.gitignore`:

```gitignore
venv/
__pycache__/
*/__pycache__/
*.pyc
*.db
.env
*.pem
*.ppk
*.backup*
*.before-*
```

Check the repository before pushing:

```bash
git status --short
```

Search for obvious secret files:

```bash
find . -maxdepth 3 -type f \( -name "*.pem" -o -name ".env" -o -name "*.db" \) -print
```

Search for common AWS key patterns:

```bash
grep -RInE "AKIA[0-9A-Z]{16}|aws_secret_access_key|aws_access_key_id" . \
  --exclude-dir=venv \
  --exclude-dir=.git \
  --exclude="*.pyc"
```

Do not paste private keys or production credentials into GitHub issues, README files, screenshots, or chat.

---

# 🐙 GitHub Upload

Initialize Git if necessary:

```bash
cd /home/ubuntu/MediRescue/MediRescue
git init
```

Set identity if required:

```bash
git config --global user.name "YOUR_NAME"
git config --global user.email "YOUR_EMAIL"
```

Review files:

```bash
git status --short
```

Add files:

```bash
git add .
```

Review staged files:

```bash
git status
```

Commit:

```bash
git commit -m "Initial MediRescue hackathon release"
```

Add your GitHub repository:

```bash
git remote add origin <YOUR_GITHUB_REPOSITORY_URL>
```

Push:

```bash
git branch -M main
git push -u origin main
```

### Important

Before `git push`, make sure these are **not** included:

```text
MediRescue-Key.pem
.env
*.db
venv/
Cloudflare credentials
AWS credentials
production password files
```

---

# 💻 Useful EC2 File Commands

Go to project:

```bash
cd /home/ubuntu/MediRescue/MediRescue
```

List files:

```bash
ls -lah
```

Show Python files:

```bash
find . -maxdepth 2 -name "*.py" -print
```

Show templates:

```bash
find templates -maxdepth 2 -type f -print
```

Show static files:

```bash
find static -maxdepth 2 -type f -print
```

Check disk:

```bash
df -h
```

Check memory:

```bash
free -h
```

Check running processes:

```bash
ps aux | grep -E "gunicorn|cloudflared|nginx"
```

Check listening ports:

```bash
sudo ss -lntp
```

---

# 📦 Create a Clean Submission ZIP

From the project directory:

```bash
cd /home/ubuntu/MediRescue/MediRescue
```

Create a clean ZIP:

```bash
zip -r /home/ubuntu/MediRescue-Hackathon-Submission.zip . \
  -x "venv/*" \
     "__pycache__/*" \
     "*/__pycache__/*" \
     "*.pyc" \
     "*.db" \
     ".env" \
     "*.pem" \
     "*.backup*" \
     "*.before-route*" \
     "*.before-debug-fix*" \
     "app.py.backup"
```

Check ZIP:

```bash
unzip -l /home/ubuntu/MediRescue-Hackathon-Submission.zip
```

Check for sensitive files:

```bash
unzip -l /home/ubuntu/MediRescue-Hackathon-Submission.zip \
  | grep -E "backup|before-|\.db|\.pem|\.env$"
```

---

# 📥 Download the ZIP to Windows

Run this from **Windows PowerShell**, not inside EC2:

```powershell
scp -i "C:\path\to\MediRescue-Key.pem" ubuntu@<EC2_PUBLIC_IP>:/home/ubuntu/MediRescue-Hackathon-Submission.zip "C:\Users\<YOUR_USERNAME>\Desktop\"
```

Keep the private key on your own machine.

---

# 🗄️ AWS Configuration

MediRescue is designed to use AWS services through the application's AWS integration layer.

The production environment uses:

```env
AWS_ENABLED=true
AWS_REGION=ap-south-1
```

The application can use the EC2 instance's IAM role rather than hardcoding AWS access keys.

### Important AWS security rule

Do **not** put this in the source code:

```python
AWS_ACCESS_KEY_ID = "..."
AWS_SECRET_ACCESS_KEY = "..."
```

Use an IAM role attached to EC2 where possible.

---

# 📢 Amazon SNS

MediRescue uses Amazon SNS for critical emergency notifications.

The emergency workflow can trigger SNS notifications when an emergency is broadcast/processed.

SNS should be configured in AWS rather than storing credentials in the application source code.

For production troubleshooting, inspect application logs:

```bash
sudo journalctl -u medirescue -n 200 --no-pager
```

---

# 📍 Amazon Location Routes V2

MediRescue integrates with Amazon Location Routes V2 for route information.

The application can return information such as:

```text
distance_km
eta_minutes
source
```

The application has been verified against the Amazon Location Routes V2 integration in the production environment.

---

# 🧑‍💼 Admin Portal

The admin portal is available through:

```text
/admin
```

Typical admin responsibilities include:

- Admin authentication
- Reviewing pending hospital registrations
- Reviewing pending ambulance driver registrations
- Approving/rejecting verification requests
- Viewing operational/emergency overview
- Creating verified hospital/driver records

Admin authentication should use a production password stored outside the Git repository.

---

# 🏥 Hospital Portal

Typical route:

```text
/hospital
```

Hospitals can:

- Authenticate
- View incoming emergency requests
- Accept emergency requests
- Update emergency workflow status
- Complete the hospital-side emergency process

---

# 🚑 Driver Portal

Typical route:

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

Typical route:

```text
/
```

The patient flow includes:

1. Start SOS
2. Safety countdown
3. Confirm emergency
4. Broadcast emergency
5. Hospital matching
6. Ambulance/driver workflow
7. ETA/routing
8. Completion

---

# 🔌 Important API Routes

The application contains APIs for the main emergency lifecycle, including routes for:

```text
/api/sos/start
/api/emergency/<id>/eta
/api/admin/login
/api/admin/overview
/api/admin/pending
/api/admin/verify
```

Additional hospital and driver endpoints are implemented in `app.py`.

For the exact current API implementation, see:

```text
app.py
```

---

# 🔁 Emergency Lifecycle

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

# 🧪 Recommended Deployment Checklist

After changing application code:

```bash
cd /home/ubuntu/MediRescue/MediRescue
source venv/bin/activate
```

Run tests:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Check syntax:

```bash
python -m py_compile app.py
```

Restart application:

```bash
sudo systemctl restart medirescue
```

Check:

```bash
sudo systemctl status medirescue
```

Check Nginx:

```bash
sudo nginx -t
sudo systemctl restart nginx
```

Check Cloudflare:

```bash
sudo systemctl status cloudflared-mediservice
```

Check local endpoint:

```bash
curl -I http://127.0.0.1
```

Check recent application errors:

```bash
sudo journalctl -u medirescue --since "10 minutes ago" --no-pager \
  | grep -Ei "error|exception|traceback"
```

---

# 🏆 Hackathon Demo Flow

A simple demonstration can follow this sequence:

### 1. Patient
Open:

```text
/
```

Start an SOS.

### 2. Safety confirmation
Show the countdown and confirm the emergency.

### 3. Emergency broadcast
Demonstrate hospital matching and emergency status.

### 4. Hospital
Open:

```text
/hospital
```

Accept the emergency.

### 5. Driver
Open:

```text
/driver
```

Dispatch and confirm pickup.

### 6. Routing
Show route distance and ETA powered by Amazon Location Routes V2.

### 7. Notification
Demonstrate the SNS notification generated by the emergency workflow.

### 8. Completion
Mark the hospital/emergency as reached and complete the workflow.

### 9. Admin
Open:

```text
/admin
```

Demonstrate verification and operational management.

---

# 🔒 Production Notes

For a real healthcare deployment, additional controls would be required, including stronger authentication/authorization, audit logging, encryption and key management, privacy/compliance controls, rate limiting, monitoring, disaster recovery, secure patient-data handling, and formal security review.

MediRescue is a hackathon/prototype system and should not be treated as a production medical system without those additional controls.

---

# 📊 Current Project Verification

The current project has been checked for:

- Flask application syntax
- Automated tests
- Production Gunicorn service
- Nginx service
- Cloudflare Tunnel service
- SNS notification integration
- Amazon Location Routes V2 integration
- Production debug mode disabled
- Production admin password moved to a protected environment file
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

# App logs
sudo journalctl -u medirescue -n 100 --no-pager

# Nginx
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl status nginx

# Cloudflare
sudo systemctl restart cloudflared-mediservice
sudo systemctl status cloudflared-mediservice
sudo journalctl -u cloudflared-mediservice -n 100 --no-pager

# Local checks
curl -I http://127.0.0.1:8000  these address can be change 
curl -I http://127.0.0.1

# Resources
df -h
free -h
sudo ss -lntp
```

---

# 📄 License

Add the project's chosen license here before publishing publicly.

---

# 👨‍💻 Project

**MediRescue — AWS Emergency Response Platform**

Built with Flask, AWS, Gunicorn, Nginx, and Cloudflare Tunnel for an emergency-response hackathon project.
