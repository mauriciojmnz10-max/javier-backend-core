import os
import requests
import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from typing import List, Optional
from datetime import datetime, timedelta

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Javier - Asistente de Ventas", version="2.0")

# =========================================================
# CONFIGURACIÓN CORS - CORREGIDA
# =========================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todos los orígenes para evitar bloqueos en GitHub Pages
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar cliente de Groq
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    logger.error("GROQ_API_KEY no está configurada")
    # No levantamos error aquí para permitir que la app inicie y muestre error en logs
    client = None
else:
    client = Groq(api_key=GROQ_API_KEY)

# =========================================================
# SISTEMA DE CACHE PARA TASA BCV
# =========================================================
class CacheTasa:
    def __init__(self):
        self.tasa = None
        self.ultima_actualizacion = None
        self.ttl = 300  # 5 minutos
    
    def obtener(self):
        if self.tasa and self.ultima_actualizacion:
            if datetime.now() - self.ultima_actualizacion < timedelta(seconds=self.ttl):
                return self.tasa
        return None
    
    def actualizar(self, tasa):
        self.tasa = tasa
        self.ultima_actualizacion = datetime.now()
        logger.info(f"Tasa BCV actualizada: {tasa}")

cache_tasa = CacheTasa()

async def obtener_tasa_bcv_con_cache():
    tasa_cache = cache_tasa.obtener()
    if tasa_cache:
        return tasa_cache
    
    tasa = await obtener_tasa_bcv_async()
    if tasa:
        cache_tasa.actualizar(tasa)
        return tasa
    return None

async def obtener_tasa_bcv_async():
    urls = [
        "https://ve.dolarapi.com/v1/dolares/oficial",
        "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv",
    ]
    
    for url in urls:
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: requests.get(url, timeout=5)
            )
            
            if response.status_code == 200:
                data = response.json()
                # DolarAPI format
                if "price" in data:
                    return float(data['price'])
                # PyDolar format
                elif "monitors" in data:
                    return float(data['monitors']['bcv']['price'])
        except Exception as e:
            logger.warning(f"Error consultando {url}: {str(e)}")
            continue
    return None

# =========================================================
# CONFIGURACIÓN DEL NEGOCIO
# =========================================================
def get_config():
    return {
        "USA_CASHEA": os.environ.get("USA_CASHEA", "true").lower() == "true",
        "USA_KRECE": os.environ.get("USA_KRECE", "true").lower() == "true",
        "NOMBRE_TIENDA": os.environ.get("NOMBRE_TIENDA", "Electroventas Cumaná"),
        "PRODUCTOS": os.environ.get("PRODUCTOS", """
📱 TELÉFONOS: Infinix Hot 40 Pro ($195), Tecno Spark 20 Pro ($180), Samsung A15 ($210).
📺 TV: Smart TV 32" ($160), 43" 4K ($280).
🏠 HOGAR: Aire 12.000 BTU ($310), Nevera Ejecutiva ($220).
"""),
        "UBICACION": "Centro de Cumaná, Calle Mariño, Edificio Electroventas",
        "HORARIO": "Lunes a Sábado de 8:30 AM a 5:30 PM",
        "DELIVERY": "Delivery GRATIS en zonas céntricas de Cumaná",
        "WHATSAPP": os.environ.get("WHATSAPP", "584120000000"),
    }

def construir_prompt(tasa, config):
    info_tasa = f"La tasa oficial BCV es: {tasa:.2f} Bs/USD." if tasa else "Consultar tasa al privado."
    
    return f"""Eres Javier, asesor de ventas de {config['NOMBRE_TIENDA']}.
Ubicación: {config['UBICACION']}. Horario: {config['HORARIO']}.
Tasa BCV: {info_tasa}.
Productos: {config['PRODUCTOS']}
Métodos: Cashea (Inicial + 3 cuotas), Krece, Pago Móvil, Zelle.

REGLAS:
1. Sé amable y breve.
2. Si el cliente quiere comprar o pregunta cómo pagar, dile que use el botón de WhatsApp.
3. Siempre menciona que somos tienda física en Cumaná."""

class ChatRequest(BaseModel):
    mensaje: str
    historial: Optional[List[dict]] = []

class ChatResponse(BaseModel):
    respuesta: str
    mostrar_whatsapp: bool = False

@app.get("/")
async def home():
    return {"status": "Javier API Online", "tasa": await obtener_tasa_bcv_con_cache()}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not client:
        return ChatResponse(respuesta="Error: API Key de Groq no configurada.", mostrar_whatsapp=True)
        
    try:
        config = get_config()
        tasa_actual = await obtener_tasa_bcv_con_cache()
        system_prompt = construir_prompt(tasa_actual, config)
        
        messages = [{"role": "system", "content": system_prompt}]
        if request.historial:
            messages.extend(request.historial[-10:])
        messages.append({"role": "user", "content": request.mensaje})
        
        completion = await asyncio.to_thread(
            client.chat.completions.create,
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=500
        )
        
        respuesta = completion.choices[0].message.content
        
        # Lógica mejorada para mostrar WhatsApp
        disparadores = ["comprar", "pago", "precio", "interesa", "ubicacion", "donde estan", "quiero"]
        mostrar_ws = any(p in request.mensaje.lower() or p in respuesta.lower() for p in disparadores)
        
        return ChatResponse(respuesta=respuesta, mostrar_whatsapp=mostrar_ws)
            
    except Exception as e:
        logger.error(f"Error: {e}")
        return ChatResponse(respuesta="Lo siento, tengo un problema técnico. ¿Hablamos por WhatsApp?", mostrar_whatsapp=True)

# No es estrictamente necesario el if __name__ en Render si usas gunicorn, 
# pero lo dejamos por compatibilidad local.
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
