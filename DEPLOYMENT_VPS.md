# PROPTO — VPS deployment (Redis queue + async worker)

Architecture (Redis/BullMQ-style, in Python):

```
WhatsApp → Whapi → Webhook (FastAPI) → save+LPUSH to Redis → 200 OK
                                                   │
                                        PROPTO worker (worker.py)
                                                   │
                              pre-filter → OpenAI (complaint?) → 10k taxonomy
                                                   │ (no match)
                                          OpenAI generates ticket content
                                                   │
                                            Ticket created (Atlas)
```

- **API** (FastAPI/uvicorn) at `https://api.propto.app`
- **Worker** (`worker.py`) — persistent systemd service consuming the Redis queue
- **Redis** — local on the VPS (`127.0.0.1:6379`)
- **DB** — your existing MongoDB Atlas
- **Frontend** stays on `manage.propto.app` (React build, points at `api.propto.app`)

Assumes Ubuntu 22.04/24.04 VPS with root/sudo. Replace `<user>` and paths as needed.
Backend files live in `/opt/propto/backend`.

---

## 1) Base packages
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip git nginx redis-server ufw
```

## 2) Redis — enable, secure, verify
```bash
# run under systemd
sudo sed -i 's/^# *supervised .*/supervised systemd/' /etc/redis/redis.conf
# bind to localhost only (default) — do NOT expose Redis publicly
sudo sed -i 's/^bind .*/bind 127.0.0.1 -::1/' /etc/redis/redis.conf

sudo systemctl enable redis-server
sudo systemctl restart redis-server
redis-cli ping        # -> PONG
```
(Optional password: set `requirepass YOUR_STRONG_PASS` in redis.conf, then use
`REDIS_URL=redis://:YOUR_STRONG_PASS@127.0.0.1:6379/0` in `.env`.)

## 3) Get the backend code + virtualenv
```bash
sudo mkdir -p /opt/propto && sudo chown -R $USER:$USER /opt/propto
cd /opt/propto
# upload/clone your project so that the backend is at /opt/propto/backend
cd /opt/propto/backend

python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn            # production ASGI server manager
```
Make sure `backend/data/taxonomy.json` (the 10,000-issue cache) is present.

## 4) Environment file
```bash
cp /opt/propto/backend/.env.vps /opt/propto/backend/.env
nano /opt/propto/backend/.env
```
Fill/confirm:
```
MONGO_URL=...your Atlas string...
DB_NAME=propto
CORS_ORIGINS=https://manage.propto.app
JWT_SECRET=... (pre-filled)
ADMIN_EMAIL=superadmin@propto.com
ADMIN_PASSWORD=Propto@Admin2026
OPENAI_API_KEY=... (your OpenAI key)
OPENAI_MODEL=gpt-5.6-luna
WHAPI_TOKEN=... (pre-filled)
WHAPI_BASE=https://gate.whapi.cloud
AI_CONFIDENCE_THRESHOLD=0.7
REDIS_URL=redis://127.0.0.1:6379/0
```

## 5) Seed once
```bash
cd /opt/propto/backend && source venv/bin/activate
python seed.py        # -> "Seeding complete."
```

## 6) systemd service — API
```bash
sudo nano /etc/systemd/system/propto-api.service
```
```ini
[Unit]
Description=PROPTO API (FastAPI)
After=network.target redis-server.service

[Service]
User=<user>
WorkingDirectory=/opt/propto/backend
ExecStart=/opt/propto/backend/venv/bin/gunicorn server:app \
  -k uvicorn.workers.UvicornWorker -w 3 -b 127.0.0.1:8001 --timeout 60
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

## 7) systemd service — Worker
```bash
sudo nano /etc/systemd/system/propto-worker.service
```
```ini
[Unit]
Description=PROPTO background worker (Redis queue)
After=network.target redis-server.service

[Service]
User=<user>
WorkingDirectory=/opt/propto/backend
ExecStart=/opt/propto/backend/venv/bin/python worker.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Start both:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now propto-api propto-worker
sudo systemctl status propto-api --no-pager
sudo systemctl status propto-worker --no-pager     # -> "PROPTO worker started; waiting for jobs"
```
Logs:
```bash
journalctl -u propto-api -f
journalctl -u propto-worker -f
```

## 8) Nginx + HTTPS for api.propto.app
Point DNS `api.propto.app` → your VPS IP first.
```bash
sudo nano /etc/nginx/sites-available/api.propto.app
```
```nginx
server {
    server_name api.propto.app;
    client_max_body_size 25M;
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/api.propto.app /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.propto.app
```

## 9) Firewall
```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```
(Redis stays on 127.0.0.1 only — never `ufw allow 6379`.)

## 10) Verify the backend
```bash
curl https://api.propto.app/api/health                 # {"status":"healthy"}
curl https://api.propto.app/api/whapi/webhook          # {"status":"ok",...}
```

## 11) Frontend (on manage.propto.app)
`frontend/.env.production` already = `REACT_APP_BACKEND_URL=https://api.propto.app`.
```bash
cd frontend && yarn install && yarn build
```
Upload `frontend/build/` to the `manage.propto.app` docroot (keep the `.htaccess`
on cPanel, or serve via nginx if the frontend is also on the VPS).

## 12) Whapi webhook
Set the webhook to `https://api.propto.app/api/whapi/webhook`, enable modes
**`messages` (POST)** and **`messages` (PATCH)**.

## 13) End-to-end test
- In PROPTO → WhatsApp Integration → **Load groups** → pick your group → Save.
- Send a complaint (e.g. *"Lift in Tower B is stuck"*). Watch:
  ```bash
  journalctl -u propto-worker -f
  ```
  You should see it dequeued, OpenAI classify it, taxonomy match, ticket created.
- Send *"good morning"* → worker logs it as ignored (no OpenAI call).

---

## How the new flow works (code)
- `routers/whatsapp_router.py`: webhook → if `REDIS_URL` set, `task_queue.enqueue(...)` and return 200; else process inline.
- `task_queue.py`: `LPUSH propto:webhooks`.
- `worker.py`: reliable `BRPOPLPUSH propto:webhooks propto:webhooks:processing`, runs the pipeline, `LREM` on completion.
- `ai_engine.prefilter()`: drops ONLY greetings BEFORE any OpenAI call.
- `ai_engine.analyze_message()`: OpenAI decides complaint + extracts fields → 10k taxonomy enriches category/severity/routing → if no match, OpenAI's content builds the ticket. Deterministic safety net (taxonomy/keyword) still creates a ticket if OpenAI fails or misclassifies.

## Ops cheatsheet
```bash
sudo systemctl restart propto-api propto-worker     # after code/env changes
redis-cli LLEN propto:webhooks                      # pending jobs (should stay near 0)
redis-cli LLEN propto:webhooks:processing           # in-flight jobs
journalctl -u propto-worker -n 100 --no-pager       # recent worker activity
```
