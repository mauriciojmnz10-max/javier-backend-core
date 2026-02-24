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
# [cite_start]1. CONFIGURACIÓN Y LOGS [cite: 1]
# ============================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Javier - Sistema de Ventas Pro", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ============================================================
# 2. CARGA DE CONFIGURACIÓN EXTERNA (NUEVO)
# ============================================================
def cargar_info_tienda():
    try:
        with open("config_tienda.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Error: No se encontró el archivo config_tienda.json")
        # Retorno de emergencia para que la app no explote si olvidas el archivo
        return {
            "nombre_tienda": "Tienda Genérica",
            "ubicacion": "Consultar vía WhatsApp",
            "horario": "No especificado",
            "contacto_whatsapp": "+580000000000",
            "metodos_pago": {"bolivares": "Consultar", "divisas": "Consultar", "financiamiento": "No disponible"},
            "catalogo_telefonos": "Consultar disponibilidad",
            "linea_blanca": "Consultar disponibilidad",
            "politicas": "Consultar garantía"
        }

INFO_EMPRESA = cargar_info_tienda()

# ============================================================
# [cite_start]3. SISTEMA DE TASA (MONITOR BCV) [cite: 2]
# ============================================================
cache_tasa = {"valor": None, "fecha": None}

def obtener_tasa_bcv():
    ahora = datetime.now()
    if cache_tasa["valor"] and cache_tasa["fecha"] > ahora - timedelta(hours=1):
        [cite_start]return cache_tasa["valor"] [cite: 2]
    
    urls = [
        "https://ve.dolarapi.com/v1/dolares/oficial", 
        "https://pydolarve.org/api/v1/dollar?monitor=bcv"
    ]
    for url in urls:
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                [cite_start]data = res.json() [cite: 3]
                v = data.get("price") or data.get("promedio") or data.get("valor")
                if v:
                    cache_tasa.update({"valor": float(v), "fecha": ahora})
                    [cite_start]return float(v) [cite: 4]
        except: continue
    return cache_tasa["valor"] or 42.50

# ============================================================
# [cite_start]4. MODELOS DE DATOS Y ENDPOINTS [cite: 10]
# ============================================================
class Message(BaseModel):
    mensaje: str
    historial: list = []

@app.post("/chat")
async def chat(msg: Message):
    try:
        tasa = obtener_tasa_bcv()
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

        # --- CONFIGURACIÓN DEL PROMPT (CEREBRO) ---
        prompt_sistema = f"""
        Eres Javier, el cerebro de ventas de {INFO_EMPRESA['nombre_tienda']}. 
        [cite_start]Tu objetivo es vender y ser extremadamente preciso. [cite: 11]

        [cite_start]ESTADO FINANCIERO: Tasa BCV = {tasa} Bs. [cite: 12]
        
        INSTRUCCIÓN DE CÁLCULO OBLIGATORIA:
        [cite_start]Cualquier precio mencionado en $ debe ir acompañado de su valor en Bs. [cite: 13]
        [cite_start]Calcula: Precio en $ multiplicado por {tasa}. [cite: 14]
        [cite_start]Ejemplo: Si algo cuesta $10, di "$10 ({10*tasa} Bs.)". [cite: 14]

        CONOCIMIENTO DE LA TIENDA:
        - UBICACIÓN: {INFO_EMPRESA['ubicacion']}
        - HORARIO: {INFO_EMPRESA['horario']}
        - PAGOS: {INFO_EMPRESA['metodos_pago']}
        - PRODUCTOS MÓVILES: {INFO_EMPRESA['catalogo_telefonos']}
        - PRODUCTOS HOGAR: {INFO_EMPRESA['linea_blanca']}
        - POLÍTICAS: {INFO_EMPRESA['politicas']}

        REGLAS DE ORO:
        1. [cite_start]Si un producto no está en la lista, ofrece consultar en almacén vía WhatsApp. [cite: 15]
        2. Tono profesional, elegante y persuasivo. [cite_start]Usa emojis. [cite: 16]
        3. [cite_start]No inventes precios ni características. [cite: 16]
        """

        mensajes_groq = [{"role": "system", "content": prompt_sistema}]
        for m in msg.historial[-8:]:
            mensajes_groq.append(m)
        mensajes_groq.append({"role": "user", "content": msg.mensaje})

        # --- LLAMADA A LA IA (Llama 3.3 70B) ---
        completion = client.chat.completions.create(
            [cite_start]model="llama-3.3-70b-versatile", [cite: 17]
            messages=mensajes_groq,
            temperature=0.6,
            max_tokens=800
        )

        resp = completion.choices[0].message.content

        # --- LÓGICA DE ACTIVACIÓN DE WHATSAPP ---
        [cite_start]palabras_venta = ["comprar", "precio", "pago", "disponible", "cuanto", "cashea", "krece", "ubicacion", "garantia"] [cite: 18]
        mostrar_ws = any(p in msg.mensaje.lower() or p in resp.lower() for p in palabras_venta)

        return {"respuesta": resp, "mostrar_whatsapp": mostrar_ws}

    except Exception as e:
        logger.error(f"Error en el servidor: {e}")
        raise HTTPException(status_code=500, detail="Error interno del asistente")
