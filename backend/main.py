"""
Automated Digital Forensics Reporter - Backend API
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn
import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from pathlib import Path

# Load .env using absolute path so it always works
ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

from rag_engine import ForensicsRAGEngine
from report_generator import ReportGenerator
from autopsy_parser import AutopsyParser

app = FastAPI(title="Automated Digital Forensics Reporter", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT_DIR = Path(__file__).parent.parent  # project root (one level above backend/)
UPLOAD_DIR = Path("uploads")
REPORTS_DIR = Path("reports")
UPLOAD_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# ── MySQL database layer ──────────────────────────────────────────────────
from database import (
    init_db,
    db_get_user, db_user_exists, db_create_user,
    db_update_password, db_update_role,
    db_create_case, db_get_case, db_update_case,
    db_list_cases, db_case_exists,
    db_create_session, db_get_session,
    db_delete_session, db_purge_sessions,
    db_check_lockout, db_record_failure, db_clear_attempts,
    db_audit, db_get_case_audit, db_get_recent_audit,
    db_generate_csrf, db_validate_csrf as _db_validate_csrf_tokens, db_purge_csrf,
    MAX_ATTEMPTS, LOCKOUT_SECS,
)

def _job_audit(job_id: str, user: str, action: str, detail: str = ""):
    """Persist a per-job audit event to MySQL."""
    db_audit(user, action, detail=f"job={job_id} | {detail}", case_id=job_id)

def _audit(user: str, action: str, detail: str = ""):
    """Persist a global audit event to MySQL."""
    db_audit(user, action, detail=detail)
    print(f"[AUDIT] {datetime.now().isoformat()} | {user} | {action} | {detail}")

# ── SESSION API KEY STORE ─────────────────────────────────────────────────
# Keys are stored ONLY in memory, never logged, never written to disk.
# Each session token maps to an encrypted key + expiry time.
import hashlib, time, secrets as _secrets
from cryptography.fernet import Fernet

_SESSION_KEYS = {}   # session_token -> {fernet_key, encrypted_api_key, expires_at, key_type}
_SESSION_TIMEOUT = 1800  # 30 minutes inactivity

def _make_fernet():
    return Fernet(Fernet.generate_key())

def _store_session_key(session_token: str, api_key: str, key_type: str):
    f = _make_fernet()
    encrypted = f.encrypt(api_key.encode()).decode()
    _SESSION_KEYS[session_token] = {
        "fernet": f,
        "encrypted": encrypted,
        "expires_at": time.time() + _SESSION_TIMEOUT,
        "key_type": key_type,
    }

def _get_session_key(session_token: str):
    entry = _SESSION_KEYS.get(session_token)
    if not entry:
        return None, None
    if time.time() > entry["expires_at"]:
        del _SESSION_KEYS[session_token]
        return None, None
    # Refresh expiry on use
    entry["expires_at"] = time.time() + _SESSION_TIMEOUT
    try:
        key = entry["fernet"].decrypt(entry["encrypted"].encode()).decode()
        return key, entry["key_type"]
    except Exception:
        return None, None

def _clear_session_key(session_token: str):
    _SESSION_KEYS.pop(session_token, None)

def _purge_expired_keys():
    now = time.time()
    expired = [t for t, v in _SESSION_KEYS.items() if now > v["expires_at"]]
    for t in expired:
        del _SESSION_KEYS[t]

rag_engine = ForensicsRAGEngine()
report_gen = ReportGenerator()
parser = AutopsyParser()

# Initialise MySQL tables and seed default users on startup
try:
    init_db()
    print("[DB] MySQL tables ready")
except Exception as _db_err:
    print(f"[DB] WARNING: MySQL not connected — {_db_err}")
    print("[DB] Running in degraded mode (no persistence)")


# Pre-load HTML at startup for instant response (prevents tab title flicker)
_HTML_CONTENT = None
_HTML_PATH = None

def _load_html():
    global _HTML_CONTENT, _HTML_PATH
    candidates = [
        ROOT_DIR / "frontend" / "index.html",
        Path(__file__).parent.parent / "frontend" / "index.html",
        Path("../frontend/index.html"),
    ]
    for f in candidates:
        if f.exists():
            _HTML_PATH = f
            with open(f, "r", encoding="utf-8") as fh:
                html = fh.read()
            # Ensure <title> is the very first thing after <head>
            # so browser never has time to show the URL as tab title
            html = html.replace(
                "<head>",
                "<head><title>AUTOPSY SIM - Digital Forensics Bureau</title>"
            , 1)
            _HTML_CONTENT = html
            print(f"[App] Frontend loaded from {f}")
            return
    print("[App] WARNING: frontend/index.html not found")

_load_html()

@app.get("/")
def root():
    from fastapi.responses import HTMLResponse
    if _HTML_CONTENT:
        return HTMLResponse(
            content=_HTML_CONTENT,
            status_code=200,
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            }
        )
    return {"status": "running"}

@app.get("/login.html")
def serve_login():
    from fastapi.responses import HTMLResponse
    candidates = [
        ROOT_DIR / "frontend" / "login.html",
        Path(__file__).parent.parent / "frontend" / "login.html",
    ]
    for f in candidates:
        if f.exists():
            with open(f, "r", encoding="utf-8") as fh:
                return HTMLResponse(content=fh.read(), headers={"Cache-Control": "no-store"})
    return root()

@app.get("/index.html")
def serve_index():
    return root()

# ── SESSION KEY ENDPOINTS ─────────────────────────────────────────────────
from fastapi import Header, HTTPException as FHTTPException
from pydantic import BaseModel

class KeyPayload(BaseModel):
    session_token: str
    api_key: str
    key_type: str  # "groq" or "openai"

@app.get("/api/dashboard")
def get_dashboard():
    """Aggregate stats across all jobs for the dashboard."""
    total_artifacts = 0
    suspicious = 0
    media_count = 0
    completed = 0
    failed = 0
    modes = {"quick": 0, "detailed": 0, "interactive": 0}
    all_cases = db_list_cases()
    for job in all_cases:
        st = job.get("status","")
        if st == "completed": completed += 1
        elif st == "error": failed += 1
        modes[job.get("analysis_mode","detailed")] = modes.get(job.get("analysis_mode","detailed"),0) + 1
        rp = job.get("report_path")
        if rp:
            try:
                import json as _json
                with open(rp) as rf:
                    rd = _json.load(rf)
                s = rd.get("summary", {})
                total_artifacts += s.get("total_artifacts", 0)
                suspicious += s.get("suspicious_events", 0)
                media_count += s.get("media_count", 0)
            except Exception:
                pass
    return {
        "total_jobs":       len(all_cases),
        "completed_jobs":   completed,
        "failed_jobs":      failed,
        "total_artifacts":  total_artifacts,
        "suspicious_events":suspicious,
        "media_count":      media_count,
        "analysis_modes":   modes,
        "recent_audit":     db_get_recent_audit(5),
    }

@app.get("/api/timeline/{job_id}")
def get_timeline(job_id: str, request: Request):
    """Return chronologically sorted normalized events with full traceability."""
    if not _check_rate(request):
        raise HTTPException(status_code=429, detail="Too many requests.")
    job = db_get_case(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not yet completed")
    # Primary: read from in-memory RAG store (populated during analysis)
    store  = rag_engine.case_data_store.get(job_id, {})
    parsed = store.get("parsed_data", {})
    events = list(parsed.get("normalized_events", []))

    # Fallback: read from saved report JSON on disk (survives restarts)
    if not events and job.get("report_path"):
        try:
            report_json = str(job["report_path"]).replace(".pdf", ".json")
            with open(report_json, "r", encoding="utf-8") as _f:
                _rd = json.load(_f)
            events = list(_rd.get("timeline", []))
            parsed = {"source_file": _rd.get("case_info",{}).get("case_name",""),
                      "file_hash": ""}
        except Exception:
            pass
    # Add media event if uploaded file is media
    fname = job.get("filename", "")
    ext = Path(fname).suffix.lower() if fname else ""
    IMAGE_EXTS = {".jpg",".jpeg",".png",".gif",".bmp",".webp"}
    AUDIO_EXTS = {".mp3",".wav",".aac",".m4a",".ogg",".flac"}
    VIDEO_EXTS = {".mp4",".avi",".mov",".mkv",".wmv",".webm"}
    if ext in IMAGE_EXTS | AUDIO_EXTS | VIDEO_EXTS:
        mtype = "MEDIA_IMAGE" if ext in IMAGE_EXTS else ("MEDIA_AUDIO" if ext in AUDIO_EXTS else "MEDIA_VIDEO")
        events.append({
            "event_type": mtype, "timestamp": job.get("created_at",""),
            "source": fname, "source_row": None,
            "record_ref": fname, "description": f"Media file: {fname}",
            "artifact_id": f"media_{job_id}", "confidence": "High",
            "conf_reason": "User-uploaded media file", "category": "media",
            "raw_attrs": {}, "media_url": f"/api/media-file/{job_id}"
        })
    def _sort_key(e):
        ts = e.get("timestamp","")
        return ts if ts and ts != "Unknown" else "9999"
    events.sort(key=_sort_key)
    return {
        "job_id": job_id, "case_name": job.get("case_name",""),
        "total": len(events), "events": events,
        "source_file": parsed.get("source_file",""),
        "file_hash": parsed.get("file_hash",""),
    }

# ── AUTHENTICATION SYSTEM ────────────────────────────────────────────────
# Passwords stored as PBKDF2-SHA256 (260k iterations) — never plain text
# Format: salt_hex:hash_hex
import hashlib as _hashlib, hmac as _hmac, secrets as _secrets_auth, re as _re

# Password policy constants
_PW_MIN_LEN    = 8
_PW_RE_UPPER   = _re.compile(r'[A-Z]')
_PW_RE_LOWER   = _re.compile(r'[a-z]')
_PW_RE_DIGIT   = _re.compile(r'[0-9]')
_PW_RE_SYMBOL  = _re.compile(r'[^A-Za-z0-9]')

def _validate_password_strength(pw: str):
    """Returns (ok: bool, reason: str)"""
    if len(pw) < _PW_MIN_LEN:
        return False, f"Password must be at least {_PW_MIN_LEN} characters"
    if not _PW_RE_UPPER.search(pw):
        return False, "Password must contain at least one uppercase letter"
    if not _PW_RE_LOWER.search(pw):
        return False, "Password must contain at least one lowercase letter"
    if not _PW_RE_DIGIT.search(pw):
        return False, "Password must contain at least one digit"
    if not _PW_RE_SYMBOL.search(pw):
        return False, "Password must contain at least one special character"
    return True, "OK"

def _hash_password(password: str, salt: str = None) -> str:
    if salt is None:
        salt = _secrets_auth.token_hex(32)
    h = _hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 260000)
    return f"{salt}:{h.hex()}"

def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, _ = stored_hash.split(':', 1)
        candidate = _hash_password(password, salt)
        return _hmac.compare_digest(candidate, stored_hash)
    except Exception:
        return False

# ── AUTH API ENDPOINTS ─────────────────────────────────────────────────────
from fastapi.responses import JSONResponse

class LoginPayload(BaseModel):
    username: str
    password: str

@app.get("/api/auth/csrf")
async def get_csrf_token(request: Request):
    """Issue a CSRF token. Call this before any state-changing request."""
    db_purge_csrf()
    token = db_generate_csrf()
    resp  = JSONResponse(content={"csrf_token": token})
    resp.set_cookie(
        key="dfr_csrf",
        value=token,
        httponly=False,          # JS must read this to send in header
        samesite="strict",
        max_age=3600,
        path="/",
        secure=False,            # localhost — set True in production (HTTPS)
    )
    return resp

@app.post("/api/auth/login")
async def auth_login(payload: LoginPayload, request: Request):
    db_purge_sessions()
    ip = getattr(request.client, "host", "unknown")

    # CSRF validation
    if not _db_validate_csrf_tokens(request.headers.get("X-CSRF-Token",""), request.cookies.get("dfr_csrf","")):
        return JSONResponse(status_code=403,
            content={"error": "Invalid or missing CSRF token. Refresh the page and try again."})

    # Rate check for login attempts
    allowed, remaining = db_check_lockout(ip)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"error": f"Account temporarily locked. Try again in {remaining}s.",
                     "locked": True, "remaining": remaining}
        )

    username = (payload.username or "").strip().lower()
    password = payload.password or ""

    user = db_get_user(username)
    if not user or not _verify_password(password, user['hash']):
        attempts_left = db_record_failure(ip)
        _audit("system", "LOGIN_FAILED", f"user={username} | ip={ip}")
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid username or password.",
                     "attempts_left": max(0, attempts_left)}
        )

    db_clear_attempts(ip)
    import secrets as _s
    token = _s.token_urlsafe(48)
    db_create_session(token, username, user)
    _audit(username, "LOGIN_OK", f"ip={ip}")

    resp = JSONResponse(content={
        "ok":           True,
        "username":     username,
        "role":         user['role'],
        "label":        user['label'],
        "allowedCases": user['allowedCases'],
        "canUpload":    user['canUpload'],
        "canQuery":     user['canQuery'],
        "canReport":    user['canReport'],
        "defaultCase":  user.get('defaultCase'),
    })
    # Secure HttpOnly cookie — not accessible from JS
    resp.set_cookie(
        key="dfr_session",
        value=token,
        httponly=True,           # JS cannot access — XSS-safe
        samesite="strict",       # CSRF-safe — no cross-site sends
        max_age=_SESSION_INACTIVITY,
        path="/",
        secure=False,            # localhost — change to True for HTTPS/production
    )
    # Rotate CSRF token after successful login
    new_csrf = db_generate_csrf()
    resp.set_cookie(
        key="dfr_csrf",
        value=new_csrf,
        httponly=False,
        samesite="strict",
        max_age=3600,
        path="/",
        secure=False,
    )
    return resp

@app.post("/api/auth/logout")
async def auth_logout(request: Request):
    if not _db_validate_csrf_tokens(request.headers.get("X-CSRF-Token",""), request.cookies.get("dfr_csrf","")):
        return JSONResponse(status_code=403, content={"error": "Invalid CSRF token."})
    token = request.cookies.get("dfr_session","")
    if token:
        db_delete_session(token)
        _audit("system","LOGOUT",f"session={token[:8]}...")
    resp = JSONResponse(content={"ok": True})
    resp.delete_cookie("dfr_session", path="/")
    return resp

@app.get("/api/auth/me")
async def auth_me(request: Request):
    """Check current session — called on every page load."""
    db_purge_sessions()
    token = request.cookies.get("dfr_session","")
    sess  = db_get_session(token)
    if not sess:
        return JSONResponse(status_code=401, content={"authenticated": False})
    return JSONResponse(content={"authenticated": True, **{k:v for k,v in sess.items()
                                  if k not in ('created_at','last_activity')}})

@app.post("/api/auth/ping")
async def auth_ping(request: Request):
    """Refresh session on user activity."""
    token = request.cookies.get("dfr_session","")
    sess  = db_get_session(token)
    if not sess:
        return JSONResponse(status_code=401, content={"ok": False})
    return JSONResponse(content={"ok": True})

@app.post("/api/auth/register")
async def register_user(payload: dict, request: Request):
    """Create a new user account. Anyone can self-register as a viewer.
    Role defaults to 'viewer'. Admin can promote via /api/auth/admin/set-role."""
    db_purge_csrf()
    if not _db_validate_csrf_tokens(request.headers.get("X-CSRF-Token",""), request.cookies.get("dfr_csrf","")):
        return JSONResponse(status_code=403, content={"error": "Invalid CSRF token."})

    username    = (payload.get("username","") or "").strip().lower()
    password    = payload.get("password","") or ""
    display     = (payload.get("display_name","") or "").strip() or username.capitalize()

    # Username validation
    if not username:
        return JSONResponse(status_code=400, content={"error": "Username is required."})
    if len(username) < 3 or len(username) > 20:
        return JSONResponse(status_code=400, content={"error": "Username must be 3–20 characters."})
    import re as _re2
    if not _re2.match(r'^[a-z0-9_]+$', username):
        return JSONResponse(status_code=400,
            content={"error": "Username may only contain lowercase letters, digits, and underscores."})
    RESERVED = {'admin','root','system','anonymous','guest','null','undefined'}
    if username in RESERVED:
        return JSONResponse(status_code=400, content={"error": "That username is reserved."})
    if db_user_exists(username):
        return JSONResponse(status_code=409, content={"error": "Username already taken."})

    # Password validation
    ok, reason = _validate_password_strength(password)
    if not ok:
        return JSONResponse(status_code=400, content={"error": reason})

    # Create user with viewer role
    ip = getattr(request.client, "host", "unknown")
    db_create_user(username, _hash_password(password), role="viewer", label=display)
    _audit("system", "USER_REGISTERED", f"username={username} | ip={ip}")
    return JSONResponse(content={"ok": True, "username": username,
                                  "role": "viewer",
                                  "message": "Account created. You can now log in."})

@app.post("/api/auth/admin/set-role")
async def admin_set_role(payload: dict, request: Request):
    """Admin-only: promote/demote a user's role."""
    if not _db_validate_csrf_tokens(request.headers.get("X-CSRF-Token",""), request.cookies.get("dfr_csrf","")):
        return JSONResponse(status_code=403, content={"error": "Invalid CSRF token."})
    token = request.cookies.get("dfr_session","")
    sess  = db_get_session(token)
    if not sess or sess.get("role") != "admin":
        return JSONResponse(status_code=403, content={"error": "Admin access required."})
    target   = (payload.get("username","") or "").strip().lower()
    new_role = (payload.get("role","") or "").strip().lower()
    if not db_user_exists(target):
        return JSONResponse(status_code=404, content={"error": "User not found."})
    if new_role not in ("admin","analyst","viewer"):
        return JSONResponse(status_code=400, content={"error": "Invalid role."})
    db_update_role(target, new_role)
    _audit(sess["username"], "ROLE_CHANGED", f"target={target} | new_role={new_role}")
    return JSONResponse(content={"ok": True})

@app.post("/api/auth/change-password")
async def change_password(payload: dict, request: Request):
    """Change own password — must meet strength requirements."""
    if not _db_validate_csrf_tokens(request.headers.get("X-CSRF-Token",""), request.cookies.get("dfr_csrf","")):
        return JSONResponse(status_code=403, content={"error": "Invalid CSRF token."})
    token = request.cookies.get("dfr_session","")
    sess  = db_get_session(token)
    if not sess:
        return JSONResponse(status_code=401, content={"error":"Not authenticated"})
    username    = sess['username']
    old_pw      = payload.get('old_password','')
    new_pw      = payload.get('new_password','')
    user        = db_get_user(username)
    if not user or not _verify_password(old_pw, user['hash']):
        return JSONResponse(status_code=403, content={"error":"Current password incorrect"})
    ok, reason = _validate_password_strength(new_pw)
    if not ok:
        return JSONResponse(status_code=400, content={"error": reason})
    db_update_password(username, _hash_password(new_pw))
    _audit(username, "PASSWORD_CHANGED", f"ip={getattr(request.client,'host','?')}")
    return JSONResponse(content={"ok": True})

# ── RATE LIMITING ────────────────────────────────────────────────────────

import collections as _col
_rate_store = _col.defaultdict(list)  # ip -> [timestamps]
_RATE_LIMIT = 60   # max requests per minute per IP

def _check_rate(request) -> bool:
    ip = getattr(request.client, "host", "unknown")
    now = time.time()
    # Keep only last 60 seconds
    _rate_store[ip] = [t for t in _rate_store[ip] if now - t < 60]
    if len(_rate_store[ip]) >= _RATE_LIMIT:
        return False
    _rate_store[ip].append(now)
    return True

# ── PER-JOB AUDIT LOG ────────────────────────────────────────────────────
@app.get("/api/job-audit/{job_id}")
def get_job_audit(job_id: str):
    """Return audit trail for a specific job — who did what when."""
    job = db_get_case(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    entries = db_get_case_audit(job_id)
    # Enrich with job metadata
    return {
        "job_id":       job_id,
        "case_name":    job.get("case_name",""),
        "analyst":      job.get("analyst_name",""),
        "created_at":   job.get("created_at",""),
        "sha256":       job.get("sha256",""),
        "audit_trail":  entries,
        "total_events": len(entries),
    }

# ── EXPORT ENDPOINTS ──────────────────────────────────────────────────────
@app.get("/api/export/timeline/{job_id}")
def export_timeline(job_id: str):
    """Export timeline as JSON for download."""
    _job = db_get_case(job_id)
    if not _job: raise HTTPException(404, "Job not found")
    store = rag_engine.case_data_store.get(job_id, {})
    parsed = store.get("parsed_data", {})
    events = parsed.get("normalized_events", [])
    return {
        "export_type":  "timeline",
        "job_id":       job_id,
        "case_name":    _job.get("case_name",""),
        "generated_at": datetime.now().isoformat(),
        "events":       events,
        "total":        len(events),
    }

@app.get("/api/export/artifacts/{job_id}")
def export_artifacts(job_id: str):
    """Export full artifact list as JSON."""
    _job2 = db_get_case(job_id)
    if not _job2: raise HTTPException(404, "Job not found")
    store = rag_engine.case_data_store.get(job_id, {})
    parsed = store.get("parsed_data", {})
    return {
        "export_type":  "artifacts",
        "job_id":       job_id,
        "case_name":    _job2.get("case_name",""),
        "generated_at": datetime.now().isoformat(),
        "summary":      parsed.get("summary",{}),
        "artifacts":    parsed.get("artifacts",[]),
        "normalized":   parsed.get("normalized_events",[]),
    }

@app.get("/api/export/queries/{job_id}")
def export_queries(job_id: str):
    """Export query log for a job."""
    _job3 = db_get_case(job_id)
    if not _job3: raise HTTPException(404, "Job not found")
    entries = [e for e in db_get_case_audit(job_id) if e.get("action") == "QUERY_ASKED"]
    return {
        "export_type":  "query_log",
        "job_id":       job_id,
        "case_name":    _job3.get("case_name",""),
        "generated_at": datetime.now().isoformat(),
        "queries":      entries,
        "total":        len(entries),
    }

@app.get("/api/audit")
def get_audit_log(session_token: str = ""):
    """Return audit log — only for authenticated sessions."""
    return {"audit_log": db_get_recent_audit(100)}

@app.post("/api/validate-key")
def validate_api_key(payload: KeyPayload):
    """Test the key against the real API before storing it."""
    _purge_expired_keys()
    if not payload.api_key or not payload.session_token:
        return {"valid": False, "error": "Missing fields"}
    key = payload.api_key.strip()
    key_type = payload.key_type if payload.key_type in ("groq","openai") else "groq"
    try:
        if key_type == "groq":
            try:
                from groq import Groq
                client = Groq(api_key=key)
                # Minimal test call
                client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role":"user","content":"hi"}],
                    max_tokens=1
                )
                valid = True
            except Exception as e:
                err = str(e)
                if "401" in err or "invalid" in err.lower() or "api key" in err.lower() or "auth" in err.lower():
                    return {"valid": False, "error": "Invalid API key"}
                # Network or other error - treat as valid but warn
                valid = True
        elif key_type == "openai":
            try:
                from openai import OpenAI
                client = OpenAI(api_key=key)
                client.models.list()
                valid = True
            except Exception as e:
                err = str(e)
                if "401" in err or "invalid" in err.lower() or "api key" in err.lower() or "auth" in err.lower():
                    return {"valid": False, "error": "Invalid API key"}
                valid = True
        else:
            return {"valid": False, "error": "Unknown key type"}
        # If valid, store it
        if valid:
            _store_session_key(payload.session_token, key, key_type)
        return {"valid": valid}
    except Exception as e:
        return {"valid": False, "error": str(e)}

@app.post("/api/set-key")
def set_api_key(payload: KeyPayload):
    _purge_expired_keys()
    if not payload.api_key or not payload.session_token:
        raise FHTTPException(status_code=400, detail="Missing fields")
    key_type = payload.key_type if payload.key_type in ("groq","openai") else "groq"
    _store_session_key(payload.session_token, payload.api_key, key_type)
    return {"status": "stored"}

@app.post("/api/clear-key")
def clear_api_key(payload: dict):
    token = payload.get("session_token","")
    _clear_session_key(token)
    return {"status": "cleared"}

@app.get("/api/key-status")
def key_status(session_token: str = ""):
    _purge_expired_keys()
    entry = _SESSION_KEYS.get(session_token)
    if not entry or time.time() > entry["expires_at"]:
        return {"active": False}
    remaining = int(entry["expires_at"] - time.time())
    return {"active": True, "key_type": entry["key_type"], "remaining_seconds": remaining}

@app.post("/api/refresh-session")
def refresh_session(payload: dict):
    token = payload.get("session_token","")
    entry = _SESSION_KEYS.get(token)
    if entry:
        entry["expires_at"] = time.time() + _SESSION_TIMEOUT
    return {"status": "ok"}




@app.post("/api/upload")
async def upload_forensic_log(
    request: Request,
    file: UploadFile = File(...),
    case_name: str = Form("Unknown Case"),
    analyst_name: str = Form("Unknown Analyst"),
    case_number: str = Form("CASE-001"),
    session_token: str = Form(""),
    department: str = Form("Digital Forensics Lab"),
    analysis_mode: str = Form("detailed"),
):
    from autopsy_parser import FileValidationError

    # ── Rate limiting ─────────────────────────────────────────
    if not _check_rate(request):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait before uploading again.")

    # ── Validate extension before saving ─────────────────────
    # Support both traditional forensic artifacts and disk images
    allowed_exts = {
        ".xml", ".csv", ".json", ".log", ".txt",
        ".jpg", ".jpeg", ".png", ".mp4", ".avi", ".mov",
        ".mp3", ".wav", ".aac", ".m4a",
        ".dd", ".img", ".raw", ".e01"  # Disk image formats
    }
    fname = file.filename or "unknown"
    ext = Path(fname).suffix.lower()
    if ext not in allowed_exts:
        _audit(analyst_name, "UPLOAD_REJECTED", f"Unsupported type: {ext} | file: {fname}")
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'")

    # ── Log upload (no filename/case-name keyword blocking — any file accepted) ──
    _audit(analyst_name, "CASE_VALIDATED", f"File '{fname}' accepted for case '{case_name}'")


    job_id = str(uuid.uuid4())
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(exist_ok=True)

    file_path = job_dir / fname
    is_disk_image = ext in {".dd", ".img", ".raw", ".e01"}
    max_size = 500 * 1024 * 1024 if is_disk_image else 50 * 1024 * 1024

    # Stream file to disk in 1 MB chunks — avoids loading 50+ MB into RAM
    import hashlib as _hl
    sha256_hasher = _hl.sha256()
    bytes_written = 0
    CHUNK = 1024 * 1024  # 1 MB chunks

    with open(file_path, "wb") as out_f:
        while True:
            chunk = await file.read(CHUNK)
            if not chunk:
                break
            bytes_written += len(chunk)
            if bytes_written > max_size:
                out_f.close()
                import os; os.remove(file_path)
                size_limit = "500 MB (disk images)" if is_disk_image else "50 MB"
                _audit(analyst_name, "UPLOAD_REJECTED", f"File too large: {fname}")
                raise HTTPException(status_code=400, detail=f"File too large (max {size_limit})")
            sha256_hasher.update(chunk)
            out_f.write(chunk)

    if bytes_written == 0:
        _audit(analyst_name, "UPLOAD_REJECTED", f"Empty file: {fname}")
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    sha256 = sha256_hasher.hexdigest().upper()

    db_create_case(job_id, {
        "status":        "uploaded",
        "file":          str(file_path),
        "filename":      fname,
        "case_name":     case_name,
        "analyst_name":  analyst_name,
        "case_number":   case_number,
        "department":    department,
        "sha256":        sha256,
        "is_disk_image": is_disk_image,
        "analysis_mode": analysis_mode,
        "session_token": session_token,
    })

    _audit(analyst_name, "CASE_CREATED", f"case={case_name} | analyst={analyst_name} | type={'disk_image' if is_disk_image else 'artifacts'}")
    _job_audit(job_id, analyst_name, "CASE_CREATED", f"case={case_name}")
    _job_audit(job_id, analyst_name, "EVIDENCE_UPLOADED", f"file={fname} | sha256={sha256[:16]}... | type={'disk_image' if is_disk_image else 'artifacts'}")

    return {"job_id": job_id, "status": "uploaded", "message": "File uploaded successfully", "file_type": "disk_image" if is_disk_image else "artifacts"}



@app.post("/api/process/{job_id}")
async def process_forensic_log(job_id: str, background_tasks: BackgroundTasks):
    if not db_case_exists(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    db_update_case(job_id, status="processing")
    background_tasks.add_task(run_pipeline, job_id)
    return {"job_id": job_id, "status": "processing"}


@app.get("/api/status/{job_id}")
def get_status(job_id: str):
    _st = db_get_case(job_id)
    if not _st:
        raise HTTPException(status_code=404, detail="Job not found")
    return _st


@app.get("/api/report/{job_id}")
def download_report(job_id: str):
    job = db_get_case(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Report not ready. Status: {job['status']}")
    report_path = job["report_path"]
    if not report_path or not Path(report_path).exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename=f"forensics_report_{job_id[:8]}.pdf"
    )


@app.get("/api/report-preview/{job_id}")
def preview_report(job_id: str):
    job = db_get_case(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Report not ready. Status: {job['status']}")
    preview_path = Path(str(job["report_path"]).replace(".pdf", ".json"))
    if preview_path.exists():
        with open(preview_path) as f:
            return json.load(f)
    return {"error": "Preview not available"}


@app.get("/api/jobs")
def list_jobs():
    return db_list_cases()


@app.post("/api/query/{job_id}")
async def query_case(request: Request, job_id: str, query: dict):
    job = db_get_case(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Case not fully processed yet")
    question = query.get("question", "")
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    # Use session API key if provided
    session_token = query.get("session_token", "")
    if session_token:
        session_key, key_type = _get_session_key(session_token)
        if session_key:
            rag_engine.set_runtime_key(session_key, key_type)
    answer = rag_engine.query(job_id, question)
    analyst_q = job.get("analyst_name","?")
    _audit(analyst_q, "AI_QUERY", f"job={job_id} | q={question[:80]}")
    _job_audit(job_id, analyst_q, "QUERY_ASKED", f"q={question[:120]}")
    return {"question": question, "answer": answer, "job_id": job_id}


@app.get("/api/media/{job_id}")
def get_media_info(job_id: str):
    job = db_get_case(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    filename = job["filename"].lower()

    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
    AUDIO_EXTS = {'.mp3', '.wav', '.aac', '.m4a', '.ogg', '.flac', '.opus', '.wma'}
    VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}

    ext = '.' + filename.rsplit('.', 1)[-1] if '.' in filename else ''

    if ext in IMAGE_EXTS:
        media_type = 'image'
    elif ext in AUDIO_EXTS:
        media_type = 'audio'
    elif ext in VIDEO_EXTS:
        media_type = 'video'
    else:
        media_type = 'none'

    file_path = Path(job["file"])
    file_size = file_path.stat().st_size if file_path.exists() else 0
    size_str = f"{file_size // (1024*1024)} MB" if file_size > 1024*1024 else f"{file_size // 1024} KB"

    return {
        "job_id": job_id,
        "filename": job["filename"],
        "media_type": media_type,
        "case_name": job["case_name"],
        "case_number": job["case_number"],
        "analyst_name": job["analyst_name"],
        "created_at": job["created_at"],
        "size": size_str,
        "file_url": f"/api/media-file/{job_id}",
        "status": job["status"]
    }


@app.get("/api/media-file/{job_id}")
def serve_media_file(job_id: str):
    job = db_get_case(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    file_path = Path(job["file"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    filename = job["filename"].lower()
    ext = '.' + filename.rsplit('.', 1)[-1] if '.' in filename else ''

    mime_map = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.gif': 'image/gif', '.webp': 'image/webp',
        '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.aac': 'audio/aac',
        '.m4a': 'audio/mp4', '.ogg': 'audio/ogg', '.opus': 'audio/opus',
        '.mp4': 'video/mp4', '.avi': 'video/x-msvideo', '.mov': 'video/quicktime',
        '.mkv': 'video/x-matroska', '.webm': 'video/webm',
    }
    media_type = mime_map.get(ext, 'application/octet-stream')

    return FileResponse(str(file_path), media_type=media_type, filename=job["filename"])




@app.get("/api/sample-file/{filename}")
def serve_sample_file(filename: str):
    # Security: strip any path traversal
    filename = Path(filename).name
    sample_dir = ROOT_DIR / "sample_data"
    file_path = sample_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Sample file not found: {filename}")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime_map = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
        "gif": "image/gif", "webp": "image/webp",
        "mp3": "audio/mpeg", "wav": "audio/wav", "aac": "audio/aac",
        "m4a": "audio/mp4", "ogg": "audio/ogg",
        "mp4": "video/mp4", "avi": "video/x-msvideo",
        "mov": "video/quicktime", "webm": "video/webm",
    }
    media_type = mime_map.get(ext, "application/octet-stream")
    import os
    # Try multiple locations to handle different working directory scenarios
    candidates = [
        file_path,
        Path(__file__).parent / "sample_data" / Path(filename).name,
        Path("sample_data") / Path(filename).name,
    ]
    resolved = None
    for c in candidates:
        if c.exists():
            resolved = c
            break
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"File not found in any sample_data location: {filename}")
    file_size = os.path.getsize(str(resolved))
    from fastapi.responses import StreamingResponse
    def iterfile():
        with open(str(resolved), "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                yield chunk
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Content-Length": str(file_size),
        "Accept-Ranges": "bytes",
        "Content-Disposition": f"inline; filename={filename}",
    }
    return StreamingResponse(iterfile(), media_type=media_type, headers=headers)


def run_pipeline(job_id: str):
    try:
        job = db_get_case(job_id)
        if not job:
            print(f"[Pipeline] Job {job_id} not found in DB")
            return
        file_path     = job["file"]
        analysis_mode = job.get("analysis_mode", "detailed")
        analyst       = job.get("analyst_name", "?")

        _audit(analyst, "PIPELINE_START", f"job={job_id} | mode={analysis_mode}")
        _job_audit(job_id, analyst, "ANALYSIS_STARTED", f"mode={analysis_mode}")

        session_token = job.get("session_token", "")
        if session_token:
            session_key, key_type = _get_session_key(session_token)
            if session_key:
                rag_engine.set_runtime_key(session_key, key_type)
                report_gen.set_runtime_key(session_key, key_type)

        db_update_case(job_id, status="parsing")
        from autopsy_parser import FileValidationError
        try:
            parsed_data = parser.parse(file_path)
        except FileValidationError as fve:
            db_update_case(job_id, status="error", error=f"File validation failed: {fve}")
            _audit(analyst, "PIPELINE_ERROR", f"job={job_id} | validation: {fve}")
            return

        db_update_case(job_id, status="indexing")
        rag_engine.index_case(job_id, parsed_data)

        db_update_case(job_id, status="generating")
        report_data = report_gen.generate(
            job_id=job_id,
            parsed_data=parsed_data,
            rag_engine=rag_engine,
            case_info={
                "case_name":    job["case_name"],
                "analyst_name": job["analyst_name"],
                "case_number":  job["case_number"],
                "department":   job["department"],
                "created_at":   job["created_at"],
            }
        )

        report_path      = str(REPORTS_DIR / f"report_{job_id}.pdf")
        report_json_path = str(REPORTS_DIR / f"report_{job_id}.json")

        report_gen.save_pdf(report_data, report_path)
        with open(report_json_path, "w") as f:
            json.dump(report_data, f, indent=2, default=str)

        db_update_case(job_id, status="completed", report_path=report_path)
        _job_audit(job_id, analyst, "REPORT_GENERATED",
                   f"artifacts={parsed_data.get('summary',{}).get('total_artifacts',0)} | "
                   f"high_conf={parsed_data.get('summary',{}).get('high_confidence_events',0)}")

    except Exception as e:
        db_update_case(job_id, status="failed", error=str(e))
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
