import os
import logging
import requests
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Javier - Sistema de Ventas Pro", version="6.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def cargar_info_tienda():
    nombre_archivo = os.environ.get("ARCHIVO_CONFIG", "config_tienda.json")
    try:
        if os.path.exists(nombre_archivo):
            with open(nombre_archivo, "r", encoding="utf-8") as f:
                return json.load(f)
        raise FileNotFoundError
    except Exception as e:
        logger.error(f"Error cargando {nombre_archivo}: {e}")
        return {"nombre_tienda": "TIENDA", "mensaje_bienvenida": "Hola"}

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
    return cache_tasa["valor"] or 45.00

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
        client = Groq(api_key=api_key)

        # Prompt del sistema (Mantenemos toda la INFO de tu JSON para Javier)
        prompt_sistema = f"""
        Eres Javier, el cerebro de ventas de {INFO.get('nombre_tienda')}.
        Tasa BCV de hoy: {tasa} Bs. Calcula siempre los precios ($ x {tasa}).
        Información de la tienda: {INFO}
        Reglas: Sé elegante, usa emojis, responde breve y ofrece WhatsApp para cerrar la venta.
        """

        mensajes_groq = [{"role": "system", "content": prompt_sistema}]
        for m in msg.historial[-6:]:
            if isinstance(m, dict) and "role" in m:
                mensajes_groq.append(m)
        
        mensajes_groq.append({"role": "user", "content": msg.mensaje})

        completion = client.chat.completions.create(
            model="llama-3-8b-8192",
            messages=mensajes_groq,
            temperature=0.6,
            max_tokens=800
        )

        resp = completion.choices[0].message.content
        
        # --- LÓGICA DE IMÁGENES MEJORADA ---
        imagen_url = None
        txt_user = msg.mensaje.lower()
        # Traemos el diccionario de imágenes del JSON
        diccionario_fotos = INFO.get("imagenes_productos", {}) 
        
        # Verificamos si alguna palabra clave del JSON está en el mensaje del usuario
        for prod, url in diccionario_fotos.items():
            if prod.lower() in txt_user:
                imagen_url = url
                break
        
        # Disparadores para el botón de WhatsApp
        disparadores = ["comprar", "precio", "pago", "disponible", "cuanto", "cashea", "krece", "ubicacion", "oferta", "credito", "interesado"]
        mostrar_ws = any(p in txt_user or p in resp.lower() for p in disparadores)

        return {
            "respuesta": resp, 
            "mostrar_whatsapp": mostrar_ws,
            "tasa": tasa,
            "imagen": imagen_url
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        # En caso de error, devolvemos un mensaje seguro y el botón de contacto
        return {
            "respuesta": "Disculpa, estoy recibiendo muchas consultas. ¿Podemos concretar por WhatsApp para darte una mejor atención? 🚀", 
            "mostrar_whatsapp": True,
            "imagen": None
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)

