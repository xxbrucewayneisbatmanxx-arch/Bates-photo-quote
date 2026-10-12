"""Photo Triage demo (Never Miss a Job). Brand via BRAND_* env vars."""
import json, os, uuid, datetime, logging, time, threading
from collections import defaultdict, deque
from pathlib import Path
import httpx
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse

BASE = Path(__file__).parent
LEADS = BASE / "leads"; LEADS.mkdir(exist_ok=True)
BRAND = os.getenv("BRAND_NAME", "Summit Home Services")
TRADE = os.getenv("BRAND_TRADE", "plumbing & HVAC")
TAGLINE = os.getenv("BRAND_TAGLINE", "Plumbing & HVAC · Nevada, MO")
DEMO_LABEL = os.getenv("BRAND_DEMO_LABEL", "")
MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
log = logging.getLogger("triage")
app = FastAPI(title="Photo Triage")
MAX_UPLOAD = int(os.getenv("MAX_UPLOAD_BYTES", str(8 * 1024 * 1024)))
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_HOUR", "10"))
_hits = defaultdict(deque); _lock = threading.Lock()

@app.on_event("startup")
def _startup(): LEADS.mkdir(parents=True, exist_ok=True)

def client_ip(req: Request):
    fwd = req.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else "unknown")

def check_rate(ip: str):
    now = time.time()
    with _lock:
        q = _hits[ip]
        while q and now - q[0] > 3600: q.popleft()
        if len(q) >= RATE_LIMIT: raise HTTPException(429, "Too many requests - please try again later or call us.")
        q.append(now)

PROMPT = """You are an intake assistant for {BRAND}, a {TRADE} company in Nevada, Missouri (small-town rates).
Look at the customer's photo and description. Respond ONLY with JSON:
{"likely_problem": str, "category": "plumbing"|"hvac"|"other", "confidence": "low"|"medium"|"high",
 "price_range_low": int, "price_range_high": int,
 "urgency": "emergency"|"soon"|"routine", "urgency_reason": str,
 "recommended_next_step": str, "safety_tips": [str]}
Price is a rough USD estimate for rural southwest Missouri labor+parts. Emergency = active flooding, gas smell, sewage, no heat in freezing weather, electrical hazard.
Customer description: """
PROMPT = PROMPT.replace("{BRAND}", BRAND).replace("{TRADE}", TRADE)

def mock_result(desc):
    return {"likely_problem": "Corroded compression fitting on the supply line under the sink, causing a slow drip",
            "category": "plumbing", "confidence": "medium", "price_range_low": 125, "price_range_high": 275,
            "urgency": "soon", "urgency_reason": "Active slow leak; risk of cabinet/subfloor water damage within days.",
            "recommended_next_step": "Close the shutoff valve under the sink, put a bucket down, and book a visit within 24-48 hours.",
            "safety_tips": ["Turn off the under-sink shutoff valve", "Keep the area dry to prevent mold"]}

def live_result(img: bytes, mime: str, desc: str):
    from google import genai
    from google.genai import types
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=key)
    r = client.models.generate_content(model=MODEL, contents=[types.Part.from_bytes(data=img, mime_type=mime), PROMPT + desc],
        config=types.GenerateContentConfig(response_mime_type="application/json"))
    return json.loads(r.text)

def mode():
    if os.getenv("PHOTO_TRIAGE_MOCK") == "1": return "mock"
    return "live" if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) else "mock"

@app.get("/")
def index():
    import html
    from fastapi.responses import HTMLResponse
    t = (BASE / "static" / "index.html").read_text()
    t = t.replace("Summit Home Services", html.escape(BRAND)).replace("Plumbing & HVAC · Nevada, MO", html.escape(TAGLINE))
    if DEMO_LABEL: t = t.replace("<body>", '<body><div style="background:#fff3cd;padding:6px;text-align:center;font-size:14px">' + html.escape(DEMO_LABEL) + '</div>', 1)
    return HTMLResponse(t)

@app.get("/health")
def health(): return {"ok": True, "mode": mode(), "webhook": bool(os.getenv("MAKE_WEBHOOK_URL"))}

@app.post("/api/triage")
async def triage(request: Request, name: str = Form(...), phone: str = Form(...), description: str = Form(""), photo: UploadFile = File(...)):
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_UPLOAD + 100_000: raise HTTPException(413, "Photo too large (8MB max)")
    img = await photo.read(MAX_UPLOAD + 1)
    if not img: raise HTTPException(400, "Empty photo")
    if len(img) > MAX_UPLOAD: raise HTTPException(413, "Photo too large (8MB max)")
    check_rate(client_ip(request))
    m = mode()
    try:
        res = mock_result(description) if m == "mock" else live_result(img, photo.content_type or "image/jpeg", description)
    except Exception as e:
        log.exception("model error"); raise HTTPException(502, f"Analysis failed: {type(e).__name__}")
    lo, hi = res.get("price_range_low"), res.get("price_range_high")
    res["price_estimate"] = f"${lo}-${hi} (estimate only; final price after on-site inspection)"
    lead = {"lead_id": str(uuid.uuid4()), "created_at": datetime.datetime.now().astimezone().isoformat(),
            "source": "photo_triage", "brand": BRAND, "mode": m,
            "customer": {"name": name, "phone": phone, "description": description},
            "triage": res,
            "lead_summary": f"{name} ({phone}): {res.get('likely_problem')}. Urgency: {res.get('urgency','').upper()}. Est. {res['price_estimate']}. Next: {res.get('recommended_next_step')}"}
    (LEADS / f"{lead['lead_id']}.json").write_text(json.dumps(lead, indent=2))
    hook = os.getenv("MAKE_WEBHOOK_URL"); lead["webhook_sent"] = False
    if hook:
        try:
            async with httpx.AsyncClient(timeout=10) as c: lead["webhook_sent"] = (await c.post(hook, json=lead)).is_success
        except Exception: log.exception("webhook failed")
    return lead
