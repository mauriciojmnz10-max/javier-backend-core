import os
import logging
import requests
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from datetime import datetime, timedelta

# 1. CONFIGURACIÓN Y LOGS [cite: 19]
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Javier - Sistema de Ventas Pro", version="4.5")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# 2. CARGA DE CONFIGURACIÓN DINÁMICA [cite: 18, 20]
def cargar_info_tienda():
    # Render usará esta variable para decidir qué archivo cargar
    nombre_archivo = os.environ.get("ARCHIVO_CONFIG", "config_tienda.json")
    try:
        with open(nombre_archivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"No se encontró {nombre_archivo}")
        return {
            "nombre_tienda": "ELECTROVENTAS CUMANÁ",
            "color_primario": "#0066ff",
            "contacto_whatsapp": "584120000000",
            "mensaje_bienvenida": "¡Hola! 👋 Soy Javier. ¿Cómo puedo ayudarte hoy?",
            "tagline": "Asesoría en Tecnología"
        }

# 3. SISTEMA DE TASA BCV [cite: 22, 24]
cache_tasa = {"valor": None, "fecha": None}

def obtener_tasa_bcv():
    ahora = datetime.now()
    if cache_tasa["valor"] and cache_tasa["fecha"] > ahora - timedelta(hours=1):
        return cache_tasa["valor"]
    
    urls = ["https://ve.dolarapi.com/v1/dolares/oficial", "https://pydolarve.org/api/v1/dollar?monitor=bcv"]
    for url in urls:
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                v = data.get("price") or data.get("promedio") or data.get("valor")
                if v:
                    cache_tasa.update({"valor": float(v), "fecha": ahora})
                    return float(v)
        except: continue
    return cache_tasa["valor"] or 43.50

# 4. ENDPOINTS [cite: 25]
class Message(BaseModel):
    mensaje: str
    historial: list = []

@app.get("/config")
async def get_config():
    """Entrega la configuración visual al frontend"""
    return cargar_info_tienda()

@app.post("/chat")
async def chat(msg: Message):
    try:
        INFO = cargar_info_tienda()
        tasa = obtener_tasa_bcv()
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

        prompt_sistema = f"""
        Eres Javier, el cerebro de ventas de {INFO['nombre_tienda']}. [cite: 26]
        Tu objetivo: Vender con precisión y elegancia. [cite: 26]
        Tasa actual: {tasa} Bs. [cite: 26]

        REGLA CRÍTICA: Precios en $ deben mostrar el cálculo en Bs ({tasa} x $). [cite: 26]

        INFORMACIÓN:
        - PRODUCTOS: {INFO.get('catalogo_telefonos')} | {INFO.get('linea_blanca')}
        - PAGOS: {INFO.get('metodos_pago')}
        - UBICACIÓN: {INFO.get('ubicacion')}
        - POLÍTICAS: {INFO.get('politicas')}
        """

        mensajes_groq = [{"role": "system", "content": prompt_sistema}]
        for m in msg.historial[-8:]: mensajes_groq.append(m)
        mensajes_groq.append({"role": "user", "content": msg.mensaje})

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile", # [cite: 30]
            messages=mensajes_groq,
            temperature=0.6
        )

        resp = completion.choices[0].message.content
        palabras_venta = ["comprar", "precio", "pago", "disponible", "cuanto", "cashea", "krece", "ubicacion"] [cite: 31]
        mostrar_ws = any(p in msg.mensaje.lower() or p in resp.lower() for p in palabras_venta)

        return {"respuesta": resp, "mostrar_whatsapp": mostrar_ws}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
