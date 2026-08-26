# Deploying PROPTO on cPanel

PROPTO = **React (build) frontend** + **FastAPI (Python) backend** + **MongoDB**.
cPanel can host the React build and (if the "Setup Python App" feature is present)
the FastAPI backend via Phusion Passenger. cPanel **cannot** host MongoDB — use
**MongoDB Atlas** (free tier is fine).

> Prerequisite: your cPanel shows **Setup Python App** under "Software"
> (same CloudLinux/Passenger stack as "Setup Node.js App"). If it's missing,
> ask your host to enable it, or use a VPS instead.

---

## 0) Get MongoDB (Atlas)
1. Create a free cluster at https://www.mongodb.com/atlas
2. Create a DB user + password.
3. Network Access → allow your server IP (or `0.0.0.0/0` to start).
4. Copy the connection string, e.g.
   `mongodb+srv://USER:PASS@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`

## 1) Get your own Gemini API key
The Emergent LLM key does **not** work off-platform. Get a free key at
https://aistudio.google.com/app/apikey . You'll set it as `GEMINI_API_KEY`
(the code already supports it — see `backend/ai_engine.py`).

---

## 2) Upload the code
Upload the repo to your account, e.g.:
- Backend  → `/home/USER/propto-backend/`   (contents of `/backend`)
- Frontend → build later, upload to `public_html/` (or a subfolder)

---

## 3) Create the Python App (FastAPI backend)
cPanel → **Setup Python App** → **Create Application**:
- **Python version:** 3.10 or 3.11
- **Application root:** `propto-backend`
- **Application URL:** a subdomain, e.g. `api.yourdomain.com` (recommended)
- **Application startup file:** `passenger_wsgi.py`
- **Application Entry point:** `application`

Click **Create**. cPanel makes a virtualenv and shows the "enter virtualenv"
command (looks like `source /home/USER/virtualenv/propto-backend/3.11/bin/activate`).

### Install dependencies
Open cPanel **Terminal** (or SSH), enter the virtualenv command shown above, then:
```bash
cd ~/propto-backend
pip install -r requirements-cpanel.txt
```
> Use `requirements-cpanel.txt` (NOT `requirements.txt`). The default file contains
> Emergent-only packages (`emergentintegrations`, custom `litellm` wheel) that cannot
> install off-platform. `requirements-cpanel.txt` drops those and adds `a2wsgi`.

### Backend environment variables
In the Python App screen, add these under **Environment variables**
(or create `~/propto-backend/.env`):
```
MONGO_URL=mongodb+srv://USER:PASS@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
DB_NAME=propto
GEMINI_API_KEY=your_google_gemini_key
CORS_ORIGINS=https://yourdomain.com
JWT_SECRET=change_this_to_a_long_random_string
ADMIN_EMAIL=superadmin@propto.com
ADMIN_PASSWORD=ChangeMe@123
# WhatsApp (optional — only if you use them)
WHAPI_TOKEN=your_whapi_token
WHATSAPP_TOKEN=...
WHATSAPP_PHONE_ID=...
WHATSAPP_WABA_ID=...
WHATSAPP_APP_SECRET=...
WHATSAPP_VERIFY_TOKEN=...
```

### Seed the database (one time)
Still inside the virtualenv:
```bash
cd ~/propto-backend
python seed.py
```
This creates indexes + the super admin + demo society.

### Restart & test
Click **Restart** on the Python App. Then:
```bash
curl https://api.yourdomain.com/api/health      # -> {"status":"healthy"}
```

---

## 4) Build & upload the frontend (React)
On your **local machine** (or cPanel Node app), inside `/frontend`:
```bash
# point the app at your backend URL BEFORE building
echo "REACT_APP_BACKEND_URL=https://api.yourdomain.com" > .env
yarn install
yarn build      # outputs the ./build folder
```
Upload everything inside `build/` into `public_html/` (or your chosen docroot).

### SPA routing (.htaccess)
Create `public_html/.htaccess` so React Router deep links work:
```apache
<IfModule mod_rewrite.c>
  RewriteEngine On
  RewriteBase /
  RewriteRule ^index\.html$ - [L]
  RewriteCond %{REQUEST_FILENAME} !-f
  RewriteCond %{REQUEST_FILENAME} !-d
  RewriteRule . /index.html [L]
</IfModule>
```

---

## 5) Point WhatsApp webhooks (optional)
If you use Whapi / Meta, update their webhook URLs to your new server:
- Whapi:  `https://api.yourdomain.com/api/whapi/webhook`
- Meta:   `https://api.yourdomain.com/api/webhook`  (verify token = `WHATSAPP_VERIFY_TOKEN`)

---

## 6) Go live
- Frontend: `https://yourdomain.com`
- Backend:  `https://api.yourdomain.com`
- Log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD` (super admin) or the demo
  society admin `admin@greenvalley.com` / `Admin@123`.

## Troubleshooting
- **502 / app won't start:** check the Python App "log" link; usually a missing
  env var or a package that failed to install.
- **CORS errors in browser:** set `CORS_ORIGINS` to your exact frontend origin.
- **"Setup Python App" not available:** your host is PHP-only — use a VPS
  (DigitalOcean/AWS) with nginx + uvicorn + systemd instead.
- **AI not working:** confirm `GEMINI_API_KEY` is set and valid.
