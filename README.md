# Photo Triage demo (Summit Home Services / Never Miss a Job)
Customer uploads a plumbing/HVAC photo + name/phone/description -> likely problem, estimated price range (small-town MO), urgency, next step, lead summary (JSON).

## Run
```
cd /workspace/ai_agency/demos/photo_triage
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export GEMINI_API_KEY=...        # live mode (or GOOGLE_API_KEY); without a key it falls back to mock
export PHOTO_TRIAGE_MOCK=1       # force canned demo result
export MAKE_WEBHOOK_URL=https://hook.make.com/...   # optional; lead JSON POSTed here
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8765
```
Open http://localhost:8765. API: `POST /api/triage` (multipart: name, phone, description, photo). `GET /health` shows mode.
Leads are saved to `leads/<id>.json`. Optional `GEMINI_MODEL` (default gemini-flash-latest).

## Deploy on Render
Uses `render.yaml` (free Python web service). Start: `uvicorn app:app --host 0.0.0.0 --port $PORT`.
Set `GEMINI_API_KEY` (secret) in the Render dashboard; optional `MAKE_WEBHOOK_URL`. Limits: 10 triage requests/hour per IP (`RATE_LIMIT_PER_HOUR`), 8MB uploads (`MAX_UPLOAD_BYTES`).
Note: free-tier disk is ephemeral, so `leads/` files reset on redeploy — use the Make webhook for persistence.
