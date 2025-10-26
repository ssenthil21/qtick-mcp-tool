
import os
import sqlite3
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
from pathlib import Path  # ✅ <-- Make sure this line exists



load_dotenv()
DB_PATH = os.getenv("DB_PATH", "qtick.db")

app = FastAPI(title="QTick MCP Service (No Auth)", version="1.3.0")

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

class LeadIn(BaseModel):
    name: str
    email: str
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
    return {"message": "Lead created successfully", "lead": {"id": new_id, **lead.model_dump()}}

@app.get("/list_leads")
def list_leads():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, source, company, phone FROM leads ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"leads": rows}

@app.get("/list_reports")
def list_reports():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, title, date FROM reports ORDER BY date DESC")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"reports": rows}

MANIFEST_PATH = Path(__file__).parent / "mcp_config.yaml"

from fastapi.responses import Response

@app.get("/mcp/manifest", include_in_schema=False)
def mcp_manifest():
    content = MANIFEST_PATH.read_text()
    return Response(content=content, media_type="application/yaml")

@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return {
        "message": "QTick MCP is running",
        "manifest": "/mcp/manifest",
        "status": "ok"
    }
