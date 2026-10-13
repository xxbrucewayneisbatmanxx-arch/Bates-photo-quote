# Bates Plumbing – Photo Quote (demo)
Customer uploads a plumbing photo + name/phone/description -> likely problem, estimated price range (Nevada, MO rates), urgency, next step, lead summary (JSON). Built by Never Miss a Job as a demo for Bates Plumbing.

## Run locally
```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export GEMINI_API_KEY=...        # live mode; without a key it falls back to a canned demo answer
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8765
```
Open http://localhost:8765. API: `POST /api/triage` (multipart: name, phone, description, photo). `GET /health` shows mode.

Env vars (all optional except the key): `GEMINI_API_KEY` (secret), `MAKE_WEBHOOK_URL` (lead JSON POSTed here), `GEMINI_MODEL` (default gemini-flash-latest), `BRAND_NAME` / `BRAND_TRADE` / `BRAND_TAGLINE` / `BRAND_DEMO_LABEL` (default to Bates Plumbing), `RATE_LIMIT_PER_HOUR` (10/IP), `MAX_UPLOAD_BYTES` (8MB, 4MB on Vercel), `LEADS_DIR`.

## Deploy on Vercel (free Hobby plan, no card)
Zero-config: Vercel detects the FastAPI `app` in `app.py`; `vercel.json` sets a 60s timeout. Import the GitHub repo at vercel.com/new, add `GEMINI_API_KEY` under Environment Variables, Deploy.
Notes: Vercel caps request bodies at 4.5MB, so the page shrinks photos in the browser (max 1600px JPEG) before upload. Lead files go to `/tmp` and are temporary — use `MAKE_WEBHOOK_URL` to keep leads.

## Deploy on Render (needs card verification)
`render.yaml` + `Procfile` are kept: start command `uvicorn app:app --host 0.0.0.0 --port $PORT`.
