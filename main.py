import os
import sqlite3
import secrets
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Request, Form
from fastapi.responses import Response, RedirectResponse, JSONResponse, FileResponse
from pydantic import BaseModel, EmailStr
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "qtick.db")
BASE_URL = os.getenv("BASE_URL", "https://urchin-app-ax5kp.ondigitalocean.app")

app = FastAPI(title="QTick MCP with OAuth2", version="2.0")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            source TEXT,
            company TEXT,
            phone TEXT
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT NOT NULL
        );
    """)
    cur.execute("SELECT COUNT(*) as c FROM reports")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO reports (title, date) VALUES (?, ?)",
            [("Weekly Sales Report", "2025-10-15"), ("Q3 Pipeline Overview", "2025-09-30")],
        )
    conn.commit()
    conn.close()

init_db()

class LeadIn(BaseModel):
    name: str
    email: EmailStr
    source: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None

@app.post("/create_lead")
def create_lead(lead: LeadIn):
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
    return {"message": "Lead created", "lead": {"id": new_id, **lead.model_dump()}}

@app.get("/list_leads")
def list_leads():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM leads ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"leads": rows}

@app.get("/list_reports")
def list_reports():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM reports ORDER BY date DESC")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"reports": rows}

TOKENS = {}

@app.get("/.well-known/openid-configuration", include_in_schema=False)
def openid_config():
    return {
        "issuer": BASE_URL,
        "authorization_endpoint": f"{BASE_URL}/oauth/authorize",
        "token_endpoint": f"{BASE_URL}/oauth/token",
        "grant_types_supported": ["authorization_code"],
        "response_types_supported": ["code"],
        "scopes_supported": ["basic"],
        "token_endpoint_auth_methods_supported": ["client_secret_post"]
    }

@app.get("/oauth/authorize", include_in_schema=False)
def authorize(client_id: str, redirect_uri: str, state: str):
    code = secrets.token_hex(8)
    TOKENS[code] = {"client_id": client_id}
    redirect = f"{redirect_uri}?code={code}&state={state}"
    return RedirectResponse(url=redirect)

@app.post("/oauth/token", include_in_schema=False)
async def token(grant_type: str = Form(...),
                code: str = Form(...),
                redirect_uri: str = Form(...),
                client_id: str = Form(...),
                client_secret: str = Form(...)):
    if code not in TOKENS:
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    access_token = secrets.token_hex(16)
    TOKENS[access_token] = {"client_id": client_id}
    return {"access_token": access_token, "token_type": "bearer", "expires_in": 3600}

MANIFEST_PATH = Path(__file__).parent / "mcp_config.yaml"

@app.api_route("/mcp/manifest", methods=["GET", "POST"], include_in_schema=False)
def mcp_manifest(request: Request):
    with open("mcp_config.yaml", "r", encoding="utf-8") as f:
        manifest_text = f.read()
    return Response(content=manifest_text, media_type="text/yaml")

@app.get("/", include_in_schema=False)
def root():
    return {"message": "QTick MCP with OAuth2 is running", "manifest": "/mcp/manifest"}

@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
