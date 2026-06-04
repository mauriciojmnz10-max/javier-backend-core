from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import os

app = FastAPI(title="ArbitrajePro API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.environ.get("DB_PATH", "arbitraje.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "MultiKAP2026")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS operaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                etapa INTEGER NOT NULL,
                inv TEXT NOT NULL,
                mi REAL, tc REAL, tv REAL, bdv REAL, bpay REAL,
                usd REAL, mbdv REAL, mbpay REAL, neto REAL,
                venta REAL, correr REAL, gan REAL
            )
        """)
        conn.commit()

init_db()

class Operacion(BaseModel):
    id: Optional[int] = None
    fecha: str
    etapa: int
    inv: str
    mi: float
    tc: float
    tv: float
    bdv: float
    bpay: float
    usd: float
    mbdv: float
    mbpay: float
    neto: float
    venta: float
    correr: float
    gan: float

class AdminAuth(BaseModel):
    password: str

class SyncData(BaseModel):
    operaciones: List[Operacion]

@app.get("/")
def root():
    return {"status": "online", "app": "ArbitrajePro API", "version": "2.0"}

@app.post("/api/admin/verify")
def verify_admin(auth: AdminAuth):
    if auth.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    return {"status": "success", "admin": True}

@app.get("/api/operaciones")
def get_operaciones(user: Optional[str] = None, admin: Optional[bool] = False):
    with get_db() as conn:
        if admin:
            rows = conn.execute("SELECT * FROM operaciones ORDER BY id DESC").fetchall()
        elif user:
            rows = conn.execute("SELECT * FROM operaciones WHERE inv = ? ORDER BY id DESC", (user,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM operaciones ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]

@app.post("/api/operaciones")
def save_operacion(op: Operacion):
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO operaciones (fecha, etapa, inv, mi, tc, tv, bdv, bpay, usd, mbdv, mbpay, neto, venta, correr, gan)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (op.fecha, op.etapa, op.inv, op.mi, op.tc, op.tv, op.bdv, op.bpay, op.usd, op.mbdv, op.mbpay, op.neto, op.venta, op.correr, op.gan))
        conn.commit()
        op.id = cursor.lastrowid
        return {"status": "success", "operacion": op.dict()}

@app.post("/api/sync")
def sync_data(data: SyncData):
    """Sincroniza datos desde GitHub Gist hacia Render"""
    with get_db() as conn:
        for op in data.operaciones:
            existing = conn.execute("SELECT id FROM operaciones WHERE id = ?", (op.id,)).fetchone()
            if not existing:
                conn.execute("""
                    INSERT INTO operaciones (id, fecha, etapa, inv, mi, tc, tv, bdv, bpay, usd, mbdv, mbpay, neto, venta, correr, gan)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (op.id, op.fecha, op.etapa, op.inv, op.mi, op.tc, op.tv, op.bdv, op.bpay, op.usd, op.mbdv, op.mbpay, op.neto, op.venta, op.correr, op.gan))
        conn.commit()
    return {"status": "success", "synced": len(data.operaciones)}

@app.delete("/api/operaciones/{op_id}")
def delete_operacion(op_id: int, password: str):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="No autorizado")
    with get_db() as conn:
        conn.execute("DELETE FROM operaciones WHERE id = ?", (op_id,))
        conn.commit()
    return {"status": "success"}

@app.delete("/api/admin/purge")
def purge_all(password: str):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="No autorizado")
    with get_db() as conn:
        conn.execute("DELETE FROM operaciones")
        conn.commit()
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 ArbitrajePro API en puerto {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
