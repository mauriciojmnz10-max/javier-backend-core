import os
import logging
import requests
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from datetime import datetime, timedelta

# 1. CONFIGURACIÓN Y LOGS
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Javier - Sistema de Ventas Pro", version="5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. CARGA DE CONFIGURACIÓN DINÁMICA (CON MANEJO DE ERRORES)
def cargar_info_tienda():
    nombre_archivo = os.environ.get("ARCHIVO_CONFIG", "config_tienda.json")
    try:
        # Verificamos si el archivo existe antes de abrirlo
        if os.path.exists(nombre_archivo):
            with open(nombre_archivo, "r", encoding="utf-8") as f:
                return json.load(f)
        raise FileNotFoundError
    except Exception as e:
        logger.error(f"Error cargando {nombre_archivo}: {e}")
        # Retorno de emergencia para que la app nunca se caiga
        return {
            "nombre_tienda": "ELECTROVENTAS",
            "color_primario": "#0066ff",
            "contacto_whatsapp": "584120000000",
            "mensaje_bienvenida": "¡Hola! Soy Javier. ¿En qué puedo ayudarte?",
            "tagline": "Asesoría en Tecnología"
        }

# 3. SISTEMA DE TASA BCV (CON FALLBACK)
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
    return cache_tasa["valor"] or 45.00 # Tasa de respaldo actualizada

# 4. ENDPOINTS
class Message(BaseModel):
    mensaje: str
    historial: list = []

@app.get("/config")
async def get_config():
    return cargar_info_tienda()

@app.post("/chat")
async def chat(msg: Message):
    try:
        INFO = cargar_info_tienda()
        tasa = obtener_tasa_bcv()
        
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Falta la API KEY de Groq en las variables de entorno")
            
        client = Groq(api_key=api_key)

        # Formateo de precios en el prompt para precisión matemática
        prompt_sistema = f"""
        Eres Javier, el cerebro de ventas premium de {INFO.get('nombre_tienda', 'la tienda')}.
        Tu objetivo: Vender con elegancia y persuasión.
        Tasa BCV hoy: {tasa} Bs.

        REGLA CRÍTICA DE PRECIOS:
        Cada vez que menciones un precio en $, calcula el equivalente en Bolívares inmediatamente: (Precio $ x {tasa}).
        Ejemplo: "Cuesta $100 ({tasa * 100} Bs)".

        CONOCIMIENTO ACTUALIZADO:
        - CATÁLOGO: {INFO.get('catalogo_telefonos', 'Consultar')}
        - HOGAR: {INFO.get('linea_blanca', 'Consultar')}
        - PAGOS: {INFO.get('metodos_pago', 'Consultar')}
        - UBICACIÓN: {INFO.get('ubicacion', 'Consultar')}

        REGLAS DE ORO:
        1. Si el producto NO está en la lista, invita a preguntar en almacén vía WhatsApp.
        2. Mantén un tono ejecutivo, usa emojis y sé muy amable.
        """

        mensajes_groq = [{"role": "system", "content": prompt_sistema}]
        # Validación de historial para evitar errores de formato
        for m in msg.historial[-6:]:
            if isinstance(m, dict) and "role" in m:
                mensajes_groq.append(m)
        
        mensajes_groq.append({"role": "user", "content": msg.mensaje})

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=mensajes_groq,
            temperature=0.6,
            max_tokens=800
        )

        resp = completion.choices[0].message.content
        
        # Lógica de cierre de ventas (Activación de botón de WhatsApp)
        palabras_cierre = ["comprar", "precio", "pago", "disponible", "cuanto", "cashea", "krece", "ubicacion", "donde", "interesado"]
        mostrar_ws = any(p in msg.mensaje.lower() or p in resp.lower() for p in palabras_cierre)

        return {
            "respuesta": resp, 
            "mostrar_whatsapp": mostrar_ws,
            "tasa": tasa
        }
    except Exception as e:
        logger.error(f"Error en chat: {str(e)}")
        # Respuesta amigable en caso de error técnico
        return {
            "respuesta": "Lo siento, estoy recibiendo muchas consultas. ¿Podrías repetirme eso o contactarnos por WhatsApp?",
            "mostrar_whatsapp": True
        }
