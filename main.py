import os
import sqlite3
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import yaml

load_dotenv()
API_KEY = os.getenv("API_KEY", "change-me")
DB_PATH = os.getenv("DB_PATH", "qtick.db")

app = FastAPI(title="QTick MCP Service (OAuth + JSON Manifest)", version="3.0.0")

# ---------------------- Database Setup ----------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            source TEXT,
            company TEXT,
            phone TEXT
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT NOT NULL
        );
        """
    )
    cur.execute("SELECT COUNT(*) as c FROM reports")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO reports (title, date) VALUES (?, ?)",
            [("Weekly Sales Report", "2025-10-15"), ("Q3 Pipeline Overview", "2025-09-30")],
        )
    conn.commit()
    conn.close()

init_db()

# ---------------------- OAuth Mock ----------------------
@app.get("/oauth/authorize", include_in_schema=False)
def oauth_authorize(response_type: str, client_id: str, redirect_uri: str, state: str):
    redirect = f"{redirect_uri}?code=dummy_auth_code&state={state}"
    return RedirectResponse(url=redirect)

@app.post("/oauth/token", include_in_schema=False)
def oauth_token_post(
    grant_type: str = Form(...),
    code: str = Form(None),
    redirect_uri: str = Form(None),
    client_id: str = Form(None),
    client_secret: str = Form(None),
):
    return {"access_token": "dummy_access_token", "token_type": "bearer", "expires_in": 3600}

@app.get("/oauth/token", include_in_schema=False)
def oauth_token_get():
    return {"access_token": "dummy_access_token", "token_type": "bearer", "expires_in": 3600}

# ---------------------- OpenID Discovery ----------------------
@app.get("/.well-known/openid-configuration", include_in_schema=False)
def openid_config():
    base = "https://urchin-app-ax5kp.ondigitalocean.app"
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "scopes_supported": [],
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
    }

# ---------------------- Auth Check ----------------------
def verify_auth(request: Request):
    auth_header = request.headers.get("authorization")
    api_key_header = request.headers.get("x-api-key")
    if not ((api_key_header and api_key_header == API_KEY) or (auth_header and "dummy_access_token" in auth_header)):
        raise HTTPException(status_code=401, detail="Unauthorized")

# ---------------------- Models ----------------------
class LeadIn(BaseModel):
    name: str
    email: EmailStr
    source: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None

# ---------------------- Endpoints ----------------------
@app.post("/create_lead")
def create_lead(lead: LeadIn, _: None = Depends(verify_auth)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO leads (name, email, source, company, phone) VALUES (?, ?, ?, ?, ?)",
        (lead.name, lead.email, lead.source, lead.company, lead.phone),
    )
    conn.commit()
    new_id = cur.lastrowid
    cur.close()
    conn.close()
    return {"message": "Lead created successfully", "lead": {"id": new_id, **lead.model_dump()}}

@app.get("/list_leads")
def list_leads(_: None = Depends(verify_auth)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, source, company, phone FROM leads ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"leads": rows}

@app.get("/list_reports")
def list_reports(_: None = Depends(verify_auth)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, title, date FROM reports ORDER BY date DESC")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"reports": rows}

# ---------------------- Manifest Endpoint (JSON) ----------------------

@app.api_route("/mcp/manifest", methods=["GET", "POST"], include_in_schema=False)
def mcp_manifest(request: Request):
    with open("mcp_config.yaml", "r", encoding="utf-8") as f:
        manifest_yaml = yaml.safe_load(f)
    if "version" not in manifest_yaml:
        manifest_yaml["version"] = "1.0.0"
    return JSONResponse(content=manifest_yaml)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}

@app.get("/", include_in_schema=False)
def root():
    return {
        "message": "QTick MCP Service is running",
        "status": "ok",
        "endpoints": ["/mcp/manifest", "/create_lead", "/list_leads", "/list_reports"]
    }