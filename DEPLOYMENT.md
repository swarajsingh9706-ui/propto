# PROPTO — cPanel single-domain deployment (`manage.propto.app`)

Everything on **one domain**:
- **Frontend (React build)** → served at `https://manage.propto.app`
- **Backend (FastAPI)** → Python App mounted at the sub-path `https://manage.propto.app/api`
- **Database** → your existing MongoDB Atlas (unchanged)

The FastAPI routes already start with `/api`, and `passenger_wsgi.py` folds the
sub-path back in, so `https://manage.propto.app/api/...` and the Whapi webhook at
`https://manage.propto.app/api/whapi/webhook` both work.

---

## Step 0 — Clean the old setup (keep Atlas!)
In cPanel:
1. **Setup Python App** → open any old PROPTO app → **CANCEL** (don't Save) → **DESTROY**.
2. **File Manager** → empty the `manage.propto.app` document root (delete old React files,
   old backend files, and any old `.htaccess`).
3. Do **NOT** touch MongoDB Atlas — the database stays as-is.

---

## Step 1 — Create the Python App (backend)
cPanel → **Setup Python App** → **Create Application**:
- **Python version:** 3.11
- **Application root:** `propto_api`  (a folder OUTSIDE the web docroot, e.g. `/home/<user>/propto_api`)
- **Application URL:** select `manage.propto.app`, and in the sub-path box type **`api`**
- **Application startup file:** `passenger_wsgi.py`
- **Application Entry point:** `application`
- Click **Create**.

## Step 2 — Upload backend files
Upload the **contents of the project `/backend` folder** into the Application root
(`/home/<user>/propto_api/`). You should see there:
`server.py`, `passenger_wsgi.py`, `seed.py`, `requirements-cpanel.txt`,
`routers/`, `ai_engine.py`, `pipeline.py`, `db.py`, `models.py`, etc.

## Step 3 — Backend environment variables
Rename the uploaded **`.env.cpanel` → `.env`** (in `/home/<user>/propto_api/`) and fill the
3 placeholders. It already contains a generated `JWT_SECRET`, CORS, admin login,
your Whapi token, and `WHAPI_BASE`:
```
MONGO_URL=PASTE_YOUR_MONGODB_ATLAS_CONNECTION_STRING_HERE   <-- paste your Atlas string
DB_NAME=propto
CORS_ORIGINS=https://manage.propto.app
JWT_SECRET=<already generated for you>
ADMIN_EMAIL=superadmin@propto.com
ADMIN_PASSWORD=Propto@Admin2026                              <-- change if you like
GEMINI_API_KEY=PASTE_YOUR_GOOGLE_GEMINI_API_KEY_HERE         <-- paste your Gemini key
WHAPI_TOKEN=<your Whapi token, pre-filled>
WHAPI_BASE=https://gate.whapi.cloud
AI_CONFIDENCE_THRESHOLD=0.7
```
(You can also add these under the Python App's "Environment variables" panel instead of a file.)

## Step 4 — Install deps + seed + restart
Copy the **"Enter to the virtual environment"** command shown on the Python App
screen, run it in cPanel **Terminal**, then:
```bash
cd ~/propto_api
pip install -r requirements-cpanel.txt
python seed.py          # creates super admin + demo society (Green Valley)
```
Back on the Python App screen click **Restart**.

## Step 5 — Verify the backend
```bash
curl https://manage.propto.app/api/health
# -> {"status":"healthy"}
```
Open in a browser: `https://manage.propto.app/api/whapi/webhook`
```
{"status":"ok","detail":"PROPTO Whapi webhook is live. Whapi will POST here."}
```
If `/api/health` returns HTML/404, the sub-path is wrong — recheck Application URL =
`manage.propto.app` with sub-path **`api`**, and that the entry point is `application`.

## Step 6 — Build & upload the frontend
On your machine, in the project `/frontend` folder:
```bash
yarn install
yarn build
```
`yarn build` reads `frontend/.env.production` (already set to
`REACT_APP_BACKEND_URL=https://manage.propto.app`).

Upload **everything inside `frontend/build/`** into the `manage.propto.app`
document root. The SPA `.htaccess` is already inside the build (it excludes `/api`
so Passenger keeps handling the backend):
```apache
Options -MultiViews
RewriteEngine On
RewriteBase /
RewriteRule ^api(/.*)?$ - [L]
RewriteCond %{REQUEST_FILENAME} -f [OR]
RewriteCond %{REQUEST_FILENAME} -d
RewriteRule ^ - [L]
RewriteRule ^ index.html [L]
```

## Step 7 — Point Whapi to the webhook
In Whapi settings set the webhook URL to:
```
https://manage.propto.app/api/whapi/webhook
```
Subscribe to `messages` (POST/PUT/PATCH) and poll updates. Then send a real group
message that matches the taxonomy and watch a ticket appear on the dashboard.

## Step 8 — Go live
- App: `https://manage.propto.app`
- Login: `superadmin@propto.com` / `Propto@Admin2026` (or the values you set),
  or the demo Society Admin `admin@greenvalley.com` / `Admin@123`.

---

## Troubleshooting
- **`/api/health` returns HTML or 404:** sub-path isn't `api`, or entry point isn't
  `application`. Recheck Step 1 and Restart.
- **`a2wsgi not installed`:** you didn't run `pip install -r requirements-cpanel.txt`
  inside the app's virtualenv. Enter the venv (Step 4) and install, then Restart.
- **Atlas TLS/handshake error in logs:** add the cPanel server's outbound IP to Atlas
  Network Access. (`db.py` already pins the certifi CA bundle.)
- **Frontend loads but API calls fail / CORS:** confirm `frontend/.env.production` had
  the right URL at build time, and `CORS_ORIGINS=https://manage.propto.app` in backend `.env`.
- **Deep-link refresh 404 (e.g. `/tickets`):** the SPA `.htaccess` didn't upload — copy it
  into the docroot.
- **AI ignores free-form (non-taxonomy) messages:** set a valid `GEMINI_API_KEY` and Restart.
- **After ANY file or env change: Restart the Python App** (Passenger does not hot-reload).
