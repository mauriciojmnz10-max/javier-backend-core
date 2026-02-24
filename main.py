import os
import logging
import requests
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from datetime import datetime, timedelta

# ============================================================
# 1. CONFIGURACIÓN Y LOGS
# ============================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Javier - Sistema de Ventas Pro", version="4.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ============================================================
# 2. CARGA DE CONFIGURACIÓN EXTERNA DINÁMICA
# ============================================================
def cargar_info_tienda():
    # Esta variable la configurarás en Render para cada cliente
    nombre_archivo = os.environ.get("ARCHIVO_CONFIG", "config_tienda.json")
    try:
        with open(nombre_archivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"No se encontró {nombre_archivo}, cargando genérico")
        return {
            "nombre_tienda": "Tienda Genérica",
            "color_primario": "#0066ff",
            "contacto_whatsapp": "584120000000",
            "politicas": "Consultar garantía",
            "metodos_pago": {}
        }

# ============================================================
# 3. SISTEMA DE TASA (MONITOR BCV)
# ============================================================
cache_tasa = {"valor": None, "fecha": None}

def obtener_tasa_bcv():
    ahora = datetime.now()
    if cache_tasa["valor"] and cache_tasa["fecha"] > ahora - timedelta(hours=1):
        return cache_tasa["valor"] [cite: 5]
    
    urls = ["https://ve.dolarapi.com/v1/dolares/oficial", "https://pydolarve.org/api/v1/dollar?monitor=bcv"]
    for url in urls:
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json() [cite: 6]
                v = data.get("price") or data.get("promedio") or data.get("valor")
                if v:
                    cache_tasa.update({"valor": float(v), "fecha": ahora})
                    return float(v) [cite: 7]
        except: continue
    return cache_tasa["valor"] or 42.50

# ============================================================
# 4. ENDPOINTS
# ============================================================
class Message(BaseModel):
    mensaje: str
    historial: list = []

@app.get("/config")
async def get_config():
    """Permite al index.html obtener nombre, color y WhatsApp del cliente"""
    return cargar_info_tienda()

@app.post("/chat")
async def chat(msg: Message):
    try:
        INFO_EMPRESA = cargar_info_tienda()
        tasa = obtener_tasa_bcv()
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

        prompt_sistema = f"""
        Eres Javier, el cerebro de ventas de {INFO_EMPRESA.get('nombre_tienda')}. 
        Tu objetivo es vender y ser preciso[cite: 9, 11]. Tasa BCV: {tasa} Bs[cite: 12].
        
        REGLA: Precios en $ deben incluir valor en Bs ({tasa} x $)[cite: 13, 14].

        DATOS:
        - PRODUCTOS: {INFO_EMPRESA.get('catalogo_telefonos', '')} {INFO_EMPRESA.get('linea_blanca', '')}
        - PAGOS: {INFO_EMPRESA.get('metodos_pago')}
        - POLÍTICAS: {INFO_EMPRESA.get('politicas')}
        """

        mensajes_groq = [{"role": "system", "content": prompt_sistema}]
        for m in msg.historial[-8:]: mensajes_groq.append(m)
        mensajes_groq.append({"role": "user", "content": msg.mensaje})

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=mensajes_groq,
            temperature=0.6,
            max_tokens=800
        )

        resp = completion.choices[0].message.content
        palabras_venta = ["comprar", "precio", "pago", "disponible", "cuanto", "cashea"]
        mostrar_ws = any(p in msg.mensaje.lower() or p in resp.lower() for p in palabras_venta)

        return {"respuesta": resp, "mostrar_whatsapp": mostrar_ws}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error en el asistente")
