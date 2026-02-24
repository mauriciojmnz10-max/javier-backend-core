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

app = FastAPI(title="Javier - Sistema de Ventas Pro", version="6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SISTEMA DE FOTOS (Cero espacio en PC) ---
# Solo añade el nombre del producto en minúsculas y el link de la imagen
PRODUCTOS_FOTOS = {
    "hot 40 pro": "https://miracomosehace.com/wp-content/uploads/2024/02/Infinix-Hot-40-Pro.jpg",
    "smart 8": "https://tiendatodo.com.ve/wp-content/uploads/2024/03/Infinix-Smart-8-Tiendatodo.webp",
    "note 40 pro": "https://storage.googleapis.com/stateless-com-ve-tienda-pan/2024/05/9212a439-note-40-pro-verde.jpg",
    "samsung a15": "https://images.samsung.com/is/image/samsung/p6pim/ve/sm-a155fzkiveo/gallery/ve-galaxy-a15-sm-a155-sm-a155fzkiveo-539308104",
    "cashea": "https://blog.cashea.app/content/images/2023/10/Que-es-Cashea.jpg",
    "krece": "https://images.noticiasvenezuela.com/2024/02/Krece.jpg"
}

# 2. CARGA DE CONFIGURACIÓN DINÁMICA
def cargar_info_tienda():
    nombre_archivo = os.environ.get("ARCHIVO_CONFIG", "config_tienda.json")
    try:
        if os.path.exists(nombre_archivo):
            with open(nombre_archivo, "r", encoding="utf-8") as f:
                return json.load(f)
        raise FileNotFoundError
    except Exception as e:
        logger.error(f"Error cargando {nombre_archivo}: {e}")
        return {
            "nombre_tienda": "TIENDA EN MANTENIMIENTO",
            "color_primario": "#0066ff",
            "mensaje_bienvenida": "Hola, soy Javier. Estamos actualizando nuestra info."
        }

# 3. SISTEMA DE TASA BCV
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
            raise ValueError("Falta la API KEY de Groq")
            
        client = Groq(api_key=api_key)

        prompt_sistema = f"""
        Eres Javier, el cerebro de ventas premium de {INFO.get('nombre_tienda', 'nuestra tienda')}.
        Tu objetivo: Vender con elegancia, persuasión y precisión. Usa emojis.

        CONTEXTO ECONÓMICO:
        - Tasa BCV: {tasa} Bs. 
        - REGLA: Siempre calcula precios en Bs: ($ x {tasa}).

        CONOCIMIENTO DE LA TIENDA:
        - PRODUCTOS/CATÁLOGO: {INFO.get('catalogo_telefonos', 'Consultar disponibilidad')}
        - OFERTAS DEL MES: {INFO.get('ofertas_mes', 'No hay ofertas activas')}
        - FINANCIAMIENTO/CRÉDITO: {INFO.get('financiamiento', 'No disponible')}
        - MÉTODOS DE PAGO: {INFO.get('metodos_pago', 'Consultar')}
        - UBICACIÓN Y HORARIO: {INFO.get('ubicacion', 'Consultar')}
        - PREGUNTAS FRECUENTES/POLÍTICAS: {INFO.get('politicas', 'Consultar')}

        REGLAS DE ORO:
        1. Si el cliente pregunta por algo que NO está en el catálogo, ofrece revisar almacén vía WhatsApp.
        2. Menciona precios tanto en $ como en Bs.
        """

        mensajes_groq = [{"role": "system", "content": prompt_sistema}]
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
        
        # --- LÓGICA DE DETECCIÓN DE IMAGEN ---
        imagen_url = None
        texto_usuario = msg.mensaje.lower()
        
        for producto, url in PRODUCTOS_FOTOS.items():
            if producto in texto_usuario:
                imagen_url = url
                break

        # Palabras que activan el botón de WhatsApp
        disparadores = ["comprar", "precio", "pago", "disponible", "cuanto", "cashea", "krece", "ubicacion", "donde", "interesado", "oferta", "credito"]
        mostrar_ws = any(p in msg.mensaje.lower() or p in resp.lower() for p in disparadores)

        return {
            "respuesta": resp, 
            "mostrar_whatsapp": mostrar_ws,
            "tasa": tasa,
            "imagen": imagen_url # Devolvemos la imagen al frontend
        }
    except Exception as e:
        logger.error(f"Error en chat: {str(e)}")
        return {
            "respuesta": "Lo siento, tengo muchas consultas. ¿Podrías contactarnos por WhatsApp?",
            "mostrar_whatsapp": True
        }
