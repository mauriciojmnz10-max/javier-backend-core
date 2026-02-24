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
# 1. CONFIGURACIÓN Y LOGS [cite: 1, 2]
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
    # Render usará esta variable para decidir qué cliente cargar
    nombre_archivo = os.environ.get("ARCHIVO_CONFIG", "config_tienda.json")
    try:
        with open(nombre_archivo, "r", encoding="utf-8") as f:
            logger.info(f"Cargando configuración desde: {nombre_archivo}")
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Error: No se encontró el archivo {nombre_archivo}")
        return {
            "nombre_tienda": "Tienda Genérica",
            "color_primario": "#0066ff",
            "ubicacion": "Consultar vía WhatsApp",
            "horario": "No especificado",
            "contacto_whatsapp": "+580000000000",
            "metodos_pago": {"bolivares": "Consultar", "divisas": "Consultar"},
            "catalogo_telefonos": "Consultar disponibilidad",
            "linea_blanca": "Consultar disponibilidad",
            "politicas": "Consultar garantía"
        }

# ============================================================
# 3. SISTEMA DE TASA (MONITOR BCV) [cite: 5]
# ============================================================
cache_tasa = {"valor": None, "fecha": None}

def obtener_tasa_bcv():
    ahora = datetime.now()
    if cache_tasa["valor"] and cache_tasa["fecha"] > ahora - timedelta(hours=1):
        return cache_tasa["valor"]
    
    urls = [
        "https://ve.dolarapi.com/v1/dolares/oficial", 
        "https://pydolarve.org/api/v1/dollar?monitor=bcv"
    ]
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
    return cache_tasa["valor"] or 42.50

# ============================================================
# 4. ENDPOINTS [cite: 8]
# ============================================================
class Message(BaseModel):
    mensaje: str
    historial: list = []

@app.get("/config")
async def get_config():
    """Endpoint para que el index.html sepa cómo vestirse"""
    return cargar_info_tienda()

@app.post("/chat")
async def chat(msg: Message):
    try:
        INFO_EMPRESA = cargar_info_tienda()
        tasa = obtener_tasa_bcv()
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

        prompt_sistema = f"""
        Eres Javier, el cerebro de ventas de {INFO_EMPRESA['nombre_tienda']}. 
        Tu objetivo es vender y ser extremadamente preciso. [cite: 11]

        ESTADO FINANCIERO: Tasa BCV = {tasa} Bs. [cite: 12]
        
        INSTRUCCIÓN DE CÁLCULO OBLIGATORIA:
        Cualquier precio mencionado en $ debe ir acompañado de su valor en Bs. [cite: 13]
        Calcula: Precio en $ multiplicado por {tasa}. [cite: 14]

        CONOCIMIENTO DE LA TIENDA:
        - UBICACIÓN: {INFO_EMPRESA['ubicacion']}
        - HORARIO: {INFO_EMPRESA['horario']}
        - PAGOS: {INFO_EMPRESA['metodos_pago']}
        - PRODUCTOS MÓVILES: {INFO_EMPRESA.get('catalogo_telefonos', '')}
        - PRODUCTOS HOGAR: {INFO_EMPRESA.get('linea_blanca', '')}
        - POLÍTICAS: {INFO_EMPRESA['politicas']}

        REGLAS DE ORO:
        1. Si un producto no está en la lista, ofrece consultar vía WhatsApp. [cite: 15]
        2. Tono persuasivo. Usa emojis. [cite: 16]
        3. No inventes precios. [cite: 16]
        """

        mensajes_groq = [{"role": "system", "content": prompt_sistema}]
        for m in msg.historial[-8:]:
            mensajes_groq.append(m)
        mensajes_groq.append({"role": "user", "content": msg.mensaje})

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=mensajes_groq,
            temperature=0.6,
            max_tokens=800
        )

        resp = completion.choices[0].message.content
        palabras_venta = ["comprar", "precio", "pago", "disponible", "cuanto", "cashea", "krece"]
        mostrar_ws = any(p in msg.mensaje.lower() or p in resp.lower() for p in palabras_venta)

        return {"respuesta": resp, "mostrar_whatsapp": mostrar_ws}

    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Error interno")
