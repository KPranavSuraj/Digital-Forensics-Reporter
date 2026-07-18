"""
database.py  —  MySQL persistence layer for AUTOPSY SIM
Replaces all in-memory dicts (jobs, _USER_DB, _AUTH_SESSIONS, etc.)
with proper SQL operations via SQLAlchemy + mysql-connector-python.

Connection URL is read from DATABASE_URL in backend/.env
Default: mysql+mysqlconnector://dfr_user:dfr_password@localhost:3306/dfr_db
"""
import json, os, secrets, time
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

load_dotenv(Path(__file__).parent / ".env")

DB_URL = os.getenv(
    "DATABASE_URL",
    "mysql+mysqlconnector://dfr_user:dfr_password@localhost:3306/dfr_db"
)

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            DB_URL,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
    return _engine

def conn():
    return get_engine().connect()

# ── JSON helpers ──────────────────────────────────────────────────────────────
def _j(v):  return json.dumps(v) if v is not None else None
def _uj(v): return json.loads(v) if v else None

# ── Datetime helpers ──────────────────────────────────────────────────────────
def _ts(v):
    """Convert datetime / string / None to ISO string for JSON responses."""
    if v is None:      return None
    if isinstance(v, datetime): return v.isoformat()
    return str(v)


# ════════════════════════════════════════════════════════════════════════════
# DATABASE INITIALISATION  (creates tables + seeds default users if needed)
# ════════════════════════════════════════════════════════════════════════════
def init_db():
    """
    Called once on server start.
    Creates all tables if they don't exist and seeds the four default users.
    """
    ddl = """
    CREATE TABLE IF NOT EXISTS users (
        username      VARCHAR(50)  PRIMARY KEY,
        password_hash VARCHAR(250) NOT NULL,
        role          VARCHAR(20)  NOT NULL DEFAULT 'viewer',
        label         VARCHAR(100),
        allowed_cases JSON,
        can_upload    TINYINT(1)   DEFAULT 0,
        can_query     TINYINT(1)   DEFAULT 0,
        can_report    TINYINT(1)   DEFAULT 1,
        default_case  JSON,
        created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS cases (
        id            VARCHAR(36)  PRIMARY KEY,
        status        VARCHAR(20)  DEFAULT 'uploaded',
        file_path     TEXT,
        filename      VARCHAR(255),
        case_name     VARCHAR(200),
        analyst_name  VARCHAR(100),
        case_number   VARCHAR(50),
        department    VARCHAR(100),
        sha256        VARCHAR(70),
        is_disk_image TINYINT(1)   DEFAULT 0,
        analysis_mode VARCHAR(20)  DEFAULT 'detailed',
        report_path   TEXT,
        error_message TEXT,
        pipeline_step VARCHAR(50),
        session_token VARCHAR(120),
        created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
        updated_at    DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS sessions (
        token         VARCHAR(120) PRIMARY KEY,
        username      VARCHAR(50)  NOT NULL,
        role          VARCHAR(20),
        label         VARCHAR(100),
        allowed_cases JSON,
        can_upload    TINYINT(1),
        can_query     TINYINT(1),
        can_report    TINYINT(1),
        default_case  JSON,
        created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
        last_activity DATETIME     DEFAULT CURRENT_TIMESTAMP,
        expires_at    DATETIME
    );

    CREATE TABLE IF NOT EXISTS login_attempts (
        ip_address    VARCHAR(45)  PRIMARY KEY,
        attempt_count INT          DEFAULT 0,
        locked_until  DATETIME     NULL,
        last_attempt  DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        id            BIGINT AUTO_INCREMENT PRIMARY KEY,
        case_id       VARCHAR(36)  NULL,
        username      VARCHAR(50),
        action        VARCHAR(100),
        detail        TEXT,
        ip_address    VARCHAR(45),
        created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS csrf_tokens (
        token         VARCHAR(120) PRIMARY KEY,
        expires_at    DATETIME     NOT NULL
    );
    """
    with conn() as c:
        for stmt in ddl.strip().split(";"):
            s = stmt.strip()
            if s:
                c.execute(text(s))
        c.commit()

    _seed_default_users()


def _seed_default_users():
    """Insert the four built-in accounts if they don't exist yet."""
    import hashlib as _hl, hmac as _hm
    def _hash(pw, salt=None):
        if not salt:
            salt = secrets.token_hex(32)
        h = _hl.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 260000)
        return f"{salt}:{h.hex()}"

    defaults = [
        {
            "username": "admin",
            "password_hash": _hash("Admin@Secure#2024!"),
            "role": "admin",
            "label": "Administrator",
            "allowed_cases": None,
            "can_upload": 1, "can_query": 1, "can_report": 1,
            "default_case": None,
        },
        {
            "username": "rodriguez",
            "password_hash": _hash("Rodriguez@Insider#2024!"),
            "role": "analyst",
            "label": "Agent M. Rodriguez",
            "allowed_cases": ["insider", "CY-2024-0089"],
            "can_upload": 1, "can_query": 1, "can_report": 1,
            "default_case": {
                "name": "Operation Insider Threat",
                "number": "CY-2024-0089",
                "analyst": "Agent M. Rodriguez",
                "dept": "Digital Forensics Lab",
            },
        },
        {
            "username": "patel",
            "password_hash": _hash("Patel@DarkWeb#2024!"),
            "role": "analyst",
            "label": "Agent K. Patel",
            "allowed_cases": ["darkweb", "CY-2024-0090"],
            "can_upload": 1, "can_query": 1, "can_report": 1,
            "default_case": {
                "name": "Operation Dark Web",
                "number": "CY-2024-0090",
                "analyst": "Agent K. Patel",
                "dept": "Digital Forensics Lab",
            },
        },
        {
            "username": "viewer",
            "password_hash": _hash("Viewer@Only#2024!"),
            "role": "viewer",
            "label": "Viewer",
            "allowed_cases": None,
            "can_upload": 0, "can_query": 0, "can_report": 1,
            "default_case": None,
        },
    ]
    with conn() as c:
        for u in defaults:
            exists = c.execute(
                text("SELECT 1 FROM users WHERE username=:un"),
                {"un": u["username"]}
            ).fetchone()
            if not exists:
                c.execute(text("""
                    INSERT INTO users
                        (username,password_hash,role,label,allowed_cases,
                         can_upload,can_query,can_report,default_case)
                    VALUES
                        (:username,:password_hash,:role,:label,:ac,
                         :can_upload,:can_query,:can_report,:dc)
                """), {
                    **u,
                    "ac": _j(u["allowed_cases"]),
                    "dc": _j(u["default_case"]),
                })
        c.commit()


# ════════════════════════════════════════════════════════════════════════════
# USERS
# ════════════════════════════════════════════════════════════════════════════
def db_get_user(username: str) -> dict | None:
    with conn() as c:
        row = c.execute(
            text("SELECT * FROM users WHERE username=:u"), {"u": username}
        ).mappings().fetchone()
    if not row:
        return None
    d = dict(row)
    return {
        "hash":         d["password_hash"],
        "role":         d["role"],
        "label":        d["label"],
        "allowedCases": _uj(d["allowed_cases"]),
        "canUpload":    bool(d["can_upload"]),
        "canQuery":     bool(d["can_query"]),
        "canReport":    bool(d["can_report"]),
        "defaultCase":  _uj(d["default_case"]),
    }

def db_user_exists(username: str) -> bool:
    with conn() as c:
        return bool(c.execute(
            text("SELECT 1 FROM users WHERE username=:u"), {"u": username}
        ).fetchone())

def db_create_user(username: str, password_hash: str, role: str = "viewer",
                   label: str = None, **kw):
    with conn() as c:
        c.execute(text("""
            INSERT INTO users
                (username,password_hash,role,label,allowed_cases,
                 can_upload,can_query,can_report,default_case)
            VALUES (:u,:h,:r,:l,:ac,:cu,:cq,:cr,:dc)
        """), {
            "u": username, "h": password_hash, "r": role,
            "l": label or username.capitalize(),
            "ac": _j(kw.get("allowedCases")),
            "cu": int(kw.get("canUpload", False)),
            "cq": int(kw.get("canQuery", False)),
            "cr": int(kw.get("canReport", True)),
            "dc": _j(kw.get("defaultCase")),
        })
        c.commit()

def db_update_password(username: str, new_hash: str):
    with conn() as c:
        c.execute(
            text("UPDATE users SET password_hash=:h WHERE username=:u"),
            {"h": new_hash, "u": username}
        )
        c.commit()

def db_update_role(username: str, role: str):
    can = role in ("admin", "analyst")
    with conn() as c:
        c.execute(text("""
            UPDATE users SET role=:r, can_upload=:cu, can_query=:cq
            WHERE username=:u
        """), {"r": role, "cu": int(can), "cq": int(can), "u": username})
        c.commit()


# ════════════════════════════════════════════════════════════════════════════
# CASES  (replaces  jobs = {})
# ════════════════════════════════════════════════════════════════════════════
def db_create_case(job_id: str, data: dict):
    with conn() as c:
        c.execute(text("""
            INSERT INTO cases
                (id,status,file_path,filename,case_name,analyst_name,
                 case_number,department,sha256,is_disk_image,
                 analysis_mode,session_token)
            VALUES
                (:id,:st,:fp,:fn,:cn,:an,:cnum,:dept,:sha,:di,:am,:tok)
        """), {
            "id":   job_id,
            "st":   data.get("status",   "uploaded"),
            "fp":   data.get("file",     ""),
            "fn":   data.get("filename", ""),
            "cn":   data.get("case_name",""),
            "an":   data.get("analyst_name",""),
            "cnum": data.get("case_number",""),
            "dept": data.get("department",""),
            "sha":  data.get("sha256",""),
            "di":   int(data.get("is_disk_image", False)),
            "am":   data.get("analysis_mode","detailed"),
            "tok":  data.get("session_token",""),
        })
        c.commit()

def db_get_case(job_id: str) -> dict | None:
    with conn() as c:
        row = c.execute(
            text("SELECT * FROM cases WHERE id=:id"), {"id": job_id}
        ).mappings().fetchone()
    if not row:
        return None
    d = dict(row)
    return {
        "id":            d["id"],
        "status":        d["status"],
        "file":          d["file_path"],
        "filename":      d["filename"],
        "case_name":     d["case_name"],
        "analyst_name":  d["analyst_name"],
        "case_number":   d["case_number"],
        "department":    d["department"],
        "sha256":        d["sha256"],
        "is_disk_image": bool(d["is_disk_image"]),
        "analysis_mode": d["analysis_mode"],
        "report_path":   d["report_path"],
        "error":         d["error_message"],
        "pipeline_step": d["pipeline_step"],
        "session_token": d["session_token"],
        "created_at":    _ts(d["created_at"]),
    }

def db_update_case(job_id: str, **kw):
    _col = {
        "status":        "status",
        "error":         "error_message",
        "report_path":   "report_path",
        "pipeline_step": "pipeline_step",
    }
    sets, params = [], {"id": job_id}
    for k, v in kw.items():
        col = _col.get(k, k)
        sets.append(f"{col}=:{k}")
        params[k] = v
    if not sets:
        return
    with conn() as c:
        c.execute(text(f"UPDATE cases SET {','.join(sets)} WHERE id=:id"), params)
        c.commit()

def db_list_cases() -> list:
    with conn() as c:
        rows = c.execute(
            text("SELECT * FROM cases ORDER BY created_at DESC")
        ).mappings().fetchall()
    result = []
    for row in rows:
        d = dict(row)
        result.append({
            "id":            d["id"],
            "status":        d["status"],
            "file":          d["file_path"],
            "filename":      d["filename"],
            "case_name":     d["case_name"],
            "analyst_name":  d["analyst_name"],
            "case_number":   d["case_number"],
            "department":    d["department"],
            "sha256":        d["sha256"],
            "is_disk_image": bool(d["is_disk_image"]),
            "analysis_mode": d["analysis_mode"],
            "report_path":   d["report_path"],
            "error":         d["error_message"],
            "pipeline_step": d["pipeline_step"],
            "session_token": d["session_token"],
            "created_at":    _ts(d["created_at"]),
        })
    return result

def db_case_exists(job_id: str) -> bool:
    with conn() as c:
        return bool(c.execute(
            text("SELECT 1 FROM cases WHERE id=:id"), {"id": job_id}
        ).fetchone())


# ════════════════════════════════════════════════════════════════════════════
# SESSIONS  (replaces  _AUTH_SESSIONS)
# ════════════════════════════════════════════════════════════════════════════
SESSION_TTL = 1800  # 30 minutes

def db_create_session(token: str, username: str, user_data: dict) -> str:
    expires = datetime.now() + timedelta(seconds=SESSION_TTL)
    with conn() as c:
        c.execute(text("""
            INSERT INTO sessions
                (token,username,role,label,allowed_cases,
                 can_upload,can_query,can_report,default_case,expires_at)
            VALUES (:t,:u,:r,:l,:ac,:cu,:cq,:cr,:dc,:exp)
        """), {
            "t":   token,
            "u":   username,
            "r":   user_data.get("role"),
            "l":   user_data.get("label"),
            "ac":  _j(user_data.get("allowedCases")),
            "cu":  int(user_data.get("canUpload",  False)),
            "cq":  int(user_data.get("canQuery",   False)),
            "cr":  int(user_data.get("canReport",  True)),
            "dc":  _j(user_data.get("defaultCase")),
            "exp": expires,
        })
        c.commit()
    return token

def db_get_session(token: str) -> dict | None:
    if not token:
        return None
    with conn() as c:
        row = c.execute(
            text("SELECT * FROM sessions WHERE token=:t AND expires_at > NOW()"),
            {"t": token}
        ).mappings().fetchone()
        if not row:
            return None
        new_exp = datetime.now() + timedelta(seconds=SESSION_TTL)
        c.execute(
            text("UPDATE sessions SET last_activity=NOW(),expires_at=:e WHERE token=:t"),
            {"e": new_exp, "t": token}
        )
        c.commit()
    d = dict(row)
    return {
        "username":     d["username"],
        "role":         d["role"],
        "label":        d["label"],
        "allowedCases": _uj(d["allowed_cases"]),
        "canUpload":    bool(d["can_upload"]),
        "canQuery":     bool(d["can_query"]),
        "canReport":    bool(d["can_report"]),
        "defaultCase":  _uj(d["default_case"]),
    }

def db_delete_session(token: str):
    with conn() as c:
        c.execute(text("DELETE FROM sessions WHERE token=:t"), {"t": token})
        c.commit()

def db_purge_sessions():
    with conn() as c:
        c.execute(text("DELETE FROM sessions WHERE expires_at < NOW()"))
        c.commit()


# ════════════════════════════════════════════════════════════════════════════
# LOGIN ATTEMPTS  (replaces  _LOGIN_ATTEMPTS)
# ════════════════════════════════════════════════════════════════════════════
MAX_ATTEMPTS = 5
LOCKOUT_SECS = 300

def db_check_lockout(ip: str) -> tuple:
    with conn() as c:
        row = c.execute(
            text("SELECT locked_until,attempt_count FROM login_attempts WHERE ip_address=:ip"),
            {"ip": ip}
        ).mappings().fetchone()
    if row and row["locked_until"] and row["locked_until"] > datetime.now():
        rem = int((row["locked_until"] - datetime.now()).total_seconds())
        return False, rem
    return True, 0

def db_record_failure(ip: str) -> int:
    """Returns remaining attempts before lockout."""
    with conn() as c:
        c.execute(text("""
            INSERT INTO login_attempts (ip_address, attempt_count)
            VALUES (:ip, 1)
            ON DUPLICATE KEY UPDATE
                attempt_count = attempt_count + 1,
                locked_until  = IF(
                    attempt_count + 1 >= :mx,
                    DATE_ADD(NOW(), INTERVAL :lk SECOND),
                    NULL
                )
        """), {"ip": ip, "mx": MAX_ATTEMPTS, "lk": LOCKOUT_SECS})
        row = c.execute(
            text("SELECT attempt_count FROM login_attempts WHERE ip_address=:ip"),
            {"ip": ip}
        ).fetchone()
        c.commit()
    cnt = row[0] if row else 1
    return max(0, MAX_ATTEMPTS - cnt)

def db_clear_attempts(ip: str):
    with conn() as c:
        c.execute(text("DELETE FROM login_attempts WHERE ip_address=:ip"), {"ip": ip})
        c.commit()


# ════════════════════════════════════════════════════════════════════════════
# AUDIT LOG  (replaces  job_audit + _audit())
# ════════════════════════════════════════════════════════════════════════════
def db_audit(username: str, action: str, detail: str = "",
             case_id: str = None, ip: str = None):
    with conn() as c:
        c.execute(text("""
            INSERT INTO audit_log (case_id,username,action,detail,ip_address)
            VALUES (:cid,:u,:a,:d,:ip)
        """), {"cid": case_id, "u": username, "a": action, "d": detail, "ip": ip})
        c.commit()

def db_get_case_audit(case_id: str) -> list:
    with conn() as c:
        rows = c.execute(
            text("SELECT * FROM audit_log WHERE case_id=:id ORDER BY created_at"),
            {"id": case_id}
        ).mappings().fetchall()
    return [dict(r) | {"created_at": _ts(r["created_at"])} for r in rows]

def db_get_recent_audit(limit: int = 100) -> list:
    with conn() as c:
        rows = c.execute(
            text("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT :n"),
            {"n": limit}
        ).mappings().fetchall()
    return [dict(r) | {"created_at": _ts(r["created_at"])} for r in rows]


# ════════════════════════════════════════════════════════════════════════════
# CSRF TOKENS  (replaces  _CSRF_TOKENS)
# ════════════════════════════════════════════════════════════════════════════
def db_generate_csrf() -> str:
    token   = secrets.token_urlsafe(32)
    expires = datetime.now() + timedelta(hours=1)
    with conn() as c:
        c.execute(
            text("INSERT INTO csrf_tokens (token,expires_at) VALUES (:t,:e)"),
            {"t": token, "e": expires}
        )
        c.commit()
    return token

def db_validate_csrf(header_token: str, cookie_token: str) -> bool:
    import hmac as _hm
    if not header_token or not cookie_token:
        return False
    if not _hm.compare_digest(header_token, cookie_token):
        return False
    with conn() as c:
        row = c.execute(
            text("SELECT 1 FROM csrf_tokens WHERE token=:t AND expires_at > NOW()"),
            {"t": header_token}
        ).fetchone()
    return row is not None

def db_purge_csrf():
    with conn() as c:
        c.execute(text("DELETE FROM csrf_tokens WHERE expires_at < NOW()"))
        c.commit()
