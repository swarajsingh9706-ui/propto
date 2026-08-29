# PROPTO — cPanel deployment (backend on its own subdomain)

Two apps, two hosts (cleanest, fully isolated):
- **Frontend (React build)** → `https://manage.propto.app`
- **Backend (FastAPI)** → `https://api.propto.app`  ← its own Python App + its own worker pool
- **Database** → your existing MongoDB Atlas (unchanged)

The backend keeps the `/api` prefix, so:
- API base = `https://api.propto.app/api`
- Health = `https://api.propto.app/api/health`
- Whapi webhook = `https://api.propto.app/api/whapi/webhook`

---

## Step 0 — Clean the old setup (keep Atlas!)
In cPanel:
1. **Setup Python App** → open any old PROPTO app → **Destroy**.
2. **File Manager** → empty the `manage.propto.app` docroot (old React files + any old `.htaccess`).
3. Do **NOT** touch MongoDB Atlas.

---

## Step 1 — Create the `api.propto.app` subdomain
cPanel → **Domains** (or **Subdomains**) → **Create A New Domain**:
- Domain: `api.propto.app`
- Uncheck "share document root"; let it create a folder, e.g. `/home/<user>/api.propto.app`.
- After creating, go to **SSL/TLS Status** → run **AutoSSL** so `https://api.propto.app` gets a certificate.

## Step 2 — Create the backend Python App
cPanel → **Setup Python App** → **Create Application**:
- **Python version:** 3.11
- **Application root:** `propto_api`  (e.g. `/home/<user>/propto_api`)
- **Application URL:** select **`api.propto.app`**, leave the sub-path box **EMPTY**
- **Application startup file:** `passenger_wsgi.py`
- **Application Entry point:** `application`
- Click **Create**.

## Step 3 — Upload backend files
Upload the **contents of the project `/backend` folder** into the Application root
(`/home/<user>/propto_api/`): `server.py`, `passenger_wsgi.py`, `seed.py`,
`requirements-cpanel.txt`, `routers/`, `ai_engine.py`, `pipeline.py`, `db.py`, `models.py`, etc.

## Step 4 — Backend environment variables
Rename the uploaded **`.env.cpanel` → `.env`** in `/home/<user>/propto_api/` and fill the
2 placeholders (JWT/CORS/admin/Whapi are pre-filled):
```
MONGO_URL=PASTE_YOUR_MONGODB_ATLAS_CONNECTION_STRING_HERE   <-- paste your Atlas string
DB_NAME=propto
CORS_ORIGINS=https://manage.propto.app                      <-- MUST be the frontend origin (cross-origin)
JWT_SECRET=<already generated for you>
ADMIN_EMAIL=superadmin@propto.com
ADMIN_PASSWORD=Propto@Admin2026                             <-- change if you like
GEMINI_API_KEY=PASTE_YOUR_GOOGLE_GEMINI_API_KEY_HERE        <-- paste your Gemini key
WHAPI_TOKEN=<your Whapi token, pre-filled>
WHAPI_BASE=https://gate.whapi.cloud
AI_CONFIDENCE_THRESHOLD=0.7
```

## Step 5 — More workers (IMPORTANT — this was the real bottleneck)
The default 6 LSAPI workers saturate under WhatsApp bursts. Give the backend headroom:
- In the **Setup Python App** screen, add an environment variable **`LSAPI_CHILDREN` = `20`**,
  **or** create a file `/home/<user>/propto_api/.htaccess` (Passenger reads it) containing:
  ```
  PassengerMaxPoolSize 20
  ```
- (The code already replies to Whapi in ~0.3s and processes in the background, so workers
  are freed immediately — but more workers = more concurrency headroom.)

## Step 6 — Install deps, seed, restart
Copy the **"Enter to the virtual environment"** command from the Python App screen, run it in
cPanel **Terminal**, then:
```bash
cd ~/propto_api
pip install -r requirements-cpanel.txt
python seed.py          # creates super admin + demo society (Green Valley)
```
Back on the Python App screen click **Restart**.

## Step 7 — Verify the backend
```bash
curl https://api.propto.app/api/health
# -> {"status":"healthy"}
```
Browser: `https://api.propto.app/api/whapi/webhook`
```
{"status":"ok","detail":"PROPTO Whapi webhook is live. Whapi will POST here."}
```
Both must respond **instantly**. If `/api/health` returns HTML/404, the entry point isn't
`application` or the startup file isn't `passenger_wsgi.py` — recheck Step 2 and Restart.

## Step 8 — Build & upload the frontend (on `manage.propto.app`)
On your machine, in the project `/frontend` folder:
```bash
yarn install
yarn build
```
`yarn build` reads `frontend/.env.production` (already set to
`REACT_APP_BACKEND_URL=https://api.propto.app`).

Upload **everything inside `frontend/build/`** into the `manage.propto.app` document root.
The SPA `.htaccess` is already inside the build (handles deep-link refresh):
```apache
Options -MultiViews
RewriteEngine On
RewriteBase /
RewriteCond %{REQUEST_FILENAME} -f [OR]
RewriteCond %{REQUEST_FILENAME} -d
RewriteRule ^ - [L]
RewriteRule ^ index.html [L]
```

## Step 9 — Point Whapi to the backend webhook
Whapi → Channel → Settings → **Webhooks**:
```
https://api.propto.app/api/whapi/webhook
```
Enable modes: **`messages` (POST)** and **`messages` (PATCH)** (PATCH is needed for live poll vote counts).

## Step 10 — Go live & connect the group
- App: `https://manage.propto.app`  (login: `superadmin@propto.com` / `Propto@Admin2026`)
- WhatsApp Integration → **Load groups** → pick **"Propto - Ticket Management"** → **Save**
  (this stores the exact Chat ID `120363...@g.us`).
- Send a complaint in the group (e.g. *"Water leaking in flat B302, send a plumber"*) → it appears
  on **AI Activity** + **Tickets**. Cast a Yes/No vote on a suggestion → tally updates.

---

## Troubleshooting
- **Frontend loads but every API call fails / CORS error in console:**
  - Confirm `frontend/.env.production` = `https://api.propto.app` at build time.
  - Confirm backend `.env` has `CORS_ORIGINS=https://manage.propto.app` (exact, no trailing slash, no `*`).
  - Confirm `https://api.propto.app` has a valid SSL cert (AutoSSL, Step 1).
- **`/api/health` returns HTML or 404:** startup file / entry point wrong (Step 2), or app not restarted.
- **`a2wsgi not installed`:** run `pip install -r requirements-cpanel.txt` inside the app's venv, Restart.
- **Atlas TLS/handshake error:** add the cPanel server's outbound IP to Atlas Network Access.
- **Messages/votes still not processed:** check the app log for `Whapi: group ... matched society ...`
  (working) vs `NO society mapped to group chat_id=... Configured=[...]` (Chat ID mismatch — re-pick the group).
  If you see `Reached max children process limit`, raise `LSAPI_CHILDREN` (Step 5).
- **After ANY file/env change: Restart the Python App** (Passenger doesn't hot-reload).
