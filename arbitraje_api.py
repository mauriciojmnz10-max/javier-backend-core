from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import os
from datetime import datetime

app = FastAPI(title="ArbitrajePro API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.environ.get("DB_PATH", "arbitraje.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Mau10")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS operaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, etapa INTEGER, inv TEXT,
            miBs REAL, miUsd REAL, resultBs REAL, resultUsd REAL, tipo TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS sesiones (
            usuario TEXT PRIMARY KEY, inicio TEXT, ultima_accion TEXT, dispositivo TEXT)""")
        conn.commit()
init_db()

class Operacion(BaseModel):
    id: Optional[int] = None
    fecha: str; etapa: int; inv: str
    miBs: float = 0; miUsd: float = 0
    resultBs: float = 0; resultUsd: float = 0
    tipo: str = ""

class Sesion(BaseModel):
    usuario: str
    inicio: str
    ultima_accion: str
    dispositivo: str = "💻 Escritorio"

@app.get("/")
def root(): return {"status": "online", "app": "ArbitrajePro API v2"}

# ============ OPERACIONES ============
@app.get("/api/operaciones")
def get_operaciones(user: Optional[str] = None, admin: Optional[bool] = False):
    with get_db() as conn:
        if admin: rows = conn.execute("SELECT * FROM operaciones ORDER BY id DESC").fetchall()
        elif user: rows = conn.execute("SELECT * FROM operaciones WHERE inv = ? ORDER BY id DESC", (user,)).fetchall()
        else: rows = conn.execute("SELECT * FROM operaciones ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]

@app.post("/api/operaciones")
def save_operacion(op: Operacion):
    with get_db() as conn:
        cursor = conn.execute("""INSERT INTO operaciones (id, fecha, etapa, inv, miBs, miUsd, resultBs, resultUsd, tipo)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (op.id, op.fecha, op.etapa, op.inv, op.miBs, op.miUsd, op.resultBs, op.resultUsd, op.tipo))
        conn.commit()
        return {"status": "success", "id": cursor.lastrowid}

@app.delete("/api/operaciones/{op_id}")
def delete_operacion(op_id: int, password: str):
    if password != ADMIN_PASSWORD: raise HTTPException(status_code=401)
    with get_db() as conn: conn.execute("DELETE FROM operaciones WHERE id = ?", (op_id,)); conn.commit()
    return {"status": "success"}

@app.delete("/api/admin/purge")
def purge_all(password: str):
    if password != ADMIN_PASSWORD: raise HTTPException(status_code=401)
    with get_db() as conn: conn.execute("DELETE FROM operaciones"); conn.commit()
    return {"status": "success"}

# ============ SESIONES (MONITOREO REAL) ============
@app.get("/api/sesiones")
def get_sesiones():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM sesiones").fetchall()
        return [dict(row) for row in rows]

@app.post("/api/sesiones")
def save_sesion(sesion: Sesion):
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO sesiones (usuario, inicio, ultima_accion, dispositivo) VALUES (?,?,?,?)",
                     (sesion.usuario, sesion.inicio, sesion.ultima_accion, sesion.dispositivo))
        conn.commit()
    return {"status": "success"}

@app.put("/api/sesiones/{usuario}")
def update_sesion(usuario: str):
    with get_db() as conn:
        conn.execute("UPDATE sesiones SET ultima_accion = ? WHERE usuario = ?", 
                     (datetime.now().isoformat(), usuario))
        conn.commit()
    return {"status": "success"}

@app.delete("/api/sesiones/{usuario}")
def delete_sesion(usuario: str):
    with get_db() as conn:
        conn.execute("DELETE FROM sesiones WHERE usuario = ?", (usuario,))
        conn.commit()
    return {"status": "success"}

# ============ LIMPIEZA AUTOMÁTICA DE SESIONES INACTIVAS ============
@app.delete("/api/sesiones/cleanup")
def cleanup_sesiones():
    with get_db() as conn:
        conn.execute("DELETE FROM sesiones WHERE datetime(ultima_accion) < datetime('now', '-30 minutes')")
        conn.commit()
    return {"status": "cleaned"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
