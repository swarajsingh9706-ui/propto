# PROPTO on cPanel — Subdomain setup (recommended)

Clean separation, no folder/.htaccess conflicts:
- **Frontend** → `https://manage.propto.app`  (React build + SPA .htaccess)
- **Backend**  → `https://api.propto.app`      (FastAPI Python app, its own folder)
- **Database** → MongoDB Atlas

---

## Step 0 — Remove the old broken app
cPanel → **Setup Python App** → open `manage.propto.app/backend` → **CANCEL** (don't Save) → **DESTROY**.
This clears the conflicting app that shared the website's docroot.

## Step 1 — Create the backend subdomain
cPanel → **Domains** (or **Subdomains**) → **Create a New Domain**:
- Domain: `api.propto.app`
- Uncheck "share document root"; note the document root it creates, e.g.
  `/home/proptoap/api.propto.app`
Wait for DNS/SSL (AutoSSL usually issues a cert within a few minutes).

## Step 2 — Upload backend files
Upload the contents of your project's `/backend` folder INTO the subdomain docroot:
`/home/proptoap/api.propto.app/`
So you should see there: `server.py`, `passenger_wsgi.py`, `seed.py`,
`requirements-cpanel.txt`, `routers/`, `ai_engine.py`, `pipeline.py`, etc.
(Only backend files live here — no React, so nothing can conflict.)

## Step 3 — Create the Python App
cPanel → **Setup Python App** → **Create Application**:
- **Python version:** 3.11
- **Application root:** `api.propto.app`
- **Application URL:** select `api.propto.app` and leave the sub-path box **EMPTY** (root)
- **Application startup file:** `passenger_wsgi.py`
- **Application Entry point:** `application`
- Click **Create**.

## Step 4 — Backend environment variables
On the Python App screen, add these (or create `/home/proptoap/api.propto.app/.env`):
```
MONGO_URL=mongodb+srv://USER:PASS@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
DB_NAME=propto
GEMINI_API_KEY=your_google_gemini_key
CORS_ORIGINS=https://manage.propto.app
JWT_SECRET=long_random_string_change_me
ADMIN_EMAIL=superadmin@propto.com
ADMIN_PASSWORD=ChangeMe@123
WHAPI_TOKEN=your_whapi_token
# Meta (only if used)
WHATSAPP_TOKEN=
WHATSAPP_PHONE_ID=
WHATSAPP_WABA_ID=
WHATSAPP_APP_SECRET=
WHATSAPP_VERIFY_TOKEN=
```

## Step 5 — Install deps + seed + restart
Copy the "enter virtualenv" command shown on the app screen, run it in cPanel **Terminal**, then:
```bash
cd ~/api.propto.app
pip install -r requirements-cpanel.txt
python seed.py
```
Back on the app screen click **Restart**.

## Step 6 — Verify the backend (no /backend prefix now!)
```bash
curl https://api.propto.app/api/health
# -> {"status":"healthy"}
```
Open in a browser: `https://api.propto.app/api/whapi/webhook`
# -> {"status":"ok","detail":"PROPTO Whapi webhook is live. Whapi will POST here."}

## Step 7 — Rebuild & upload the frontend
On your machine, in `/frontend`:
```bash
echo "REACT_APP_BACKEND_URL=https://api.propto.app" > .env
yarn install
yarn build
```
Upload everything **inside** `build/` into the `manage.propto.app` document root.
Ensure the SPA `.htaccess` is there too (from `frontend/public/.htaccess` it's already
inside `build/`). Its content:
```apache
Options -MultiViews
RewriteEngine On
RewriteBase /
RewriteCond %{REQUEST_FILENAME} -f [OR]
RewriteCond %{REQUEST_FILENAME} -d
RewriteRule ^ - [L]
RewriteRule ^ index.html [L]
```
(No `/backend` exclusion needed anymore — the backend is on its own subdomain.)

## Step 8 — Point Whapi to the new URL
In Whapi settings, set the webhook to:
```
https://api.propto.app/api/whapi/webhook
```
Subscribe to `messages` (post/put/patch). Meta webhook (if used):
`https://api.propto.app/api/webhook`

## Step 9 — Go live
- Frontend: https://manage.propto.app
- Backend:  https://api.propto.app
- Login: your `ADMIN_EMAIL` / `ADMIN_PASSWORD`, or demo `admin@greenvalley.com` / `Admin@123`.

## Troubleshooting
- **Restart shows red "no such application":** the Application root folder is empty or
  wrong — confirm `passenger_wsgi.py` is directly inside `~/api.propto.app`.
- **/api/health 404 (HTML):** the Python app isn't mounted at the subdomain root — recheck
  Application URL = `api.propto.app` with an EMPTY sub-path.
- **CORS error in browser:** set `CORS_ORIGINS=https://manage.propto.app` (exact origin) and Restart.
- **AI not classifying free-form messages:** set a valid `GEMINI_API_KEY` and Restart.
- After ANY file change or env change: **Restart the app** (Passenger does not hot-reload).
