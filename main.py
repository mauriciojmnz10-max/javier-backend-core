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

app = FastAPI(title="Sistema Multi-Tienda", version="7.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== CONFIGURACIÓN POR TIENDA ==========
# La tienda se selecciona mediante variable de entorno o parámetro
TIENDA_ACTUAL = os.environ.get("TIENDA", "electroventas")  # "electroventas" o "multikap"

def obtener_nombre_config():
    """Retorna el nombre del archivo de configuración según la tienda"""
    configs = {
        "electroventas": "config_electroventas.json",
        "multikap": "config_multikap.json"
    }
    return configs.get(TIENDA_ACTUAL, "config_electroventas.json")

def cargar_info_tienda():
    nombre_archivo = obtener_nombre_config()
    try:
        if os.path.exists(nombre_archivo):
            with open(nombre_archivo, "r", encoding="utf-8") as f:
                return json.load(f)
        raise FileNotFoundError
    except Exception as e:
        logger.error(f"Error cargando {nombre_archivo}: {e}")
        return {"nombre_tienda": "TIENDA", "mensaje_bienvenida": "Hola"}

# ========== TASA BCV (COMPARTIDA) ==========
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

# ========== MODELOS ==========
class Message(BaseModel):
    mensaje: str
    historial: list = []
    advisor: str = "default"  # Para MultiKAP: motos/papeleria/hogar, para otros: default

# ========== GENERADOR DE PROMPTS POR TIENDA ==========
def generar_prompt_segun_tienda(info, tasa, advisor="default"):
    """Genera el prompt del sistema según la tienda activa"""
    
    tienda = info.get("nombre_tienda", "").upper()
    
    # ===== PROMPT PARA ELECTROVENTAS (JAVIER) =====
    if "ELECTROVENTAS" in tienda:
        return f"""
        Eres Javier, el cerebro de ventas de {info.get('nombre_tienda')}.
        Tasa BCV de hoy: {tasa} Bs. Calcula siempre los precios ($ x {tasa}).
        
        Información de la tienda: {info}
        
        Reglas: 
        - Sé elegante, usa emojis, responde breve
        - IMPORTANTE: Siempre que un usuario mencione un producto o marca, identifica el producto más cercano en tu lista de imagenes_productos y envíalo inmediatamente.
        - No preguntes '¿Quieres ver una foto?', simplemente muéstrala mientras das la información técnica.
        - Nunca escribas números de teléfono en el texto.
        - Para finalizar la compra, indica que deben usar el botón verde de WhatsApp.
        """
    
    # ===== PROMPT PARA MULTIKAP (TAZ) =====
    elif "MULTIKAP" in tienda:
        # Prompt según el asesor seleccionado
        prompts_asesor = {
            "motos": "Eres TAZ MOTOS 🏍️, experto en repuestos y accesorios para motos. Responde con energía y pasión por las motos.",
            "papeleria": "Eres TAZ PAPELERÍA 📚, especialista en útiles escolares y de oficina. Responde con creatividad y orden.",
            "hogar": "Eres TAZ HOGAR 🏠, experto en productos de limpieza y organización del hogar. Responde con calidez y practicidad."
        }
        personalidad = prompts_asesor.get(advisor, "Eres TAZ, el asistente virtual de MultiKAP.")
        
        return f"""
        {personalidad}
        
        Tasa BCV de hoy: {tasa} Bs. Calcula siempre los precios ($ x {tasa}).
        
        Información de la tienda: {info}
        
        REGLAS IMPORTANTES:
        1. Este es un sistema SIN IMÁGENES. NO menciones "fotos", "imágenes", "mirar", "ver". Usa SOLO texto.
        2. Si el usuario pregunta por productos, guíalo a usar el botón "📋 Ver catálogo"
        3. Los precios deben mostrarse en $ y Bs (calculado con la tasa)
        4. Sé elegante pero con personalidad (usa emojis, sé dinámico)
        5. NUNCA escribas números de teléfono en el texto
        6. Para finalizar la compra, indica que usen el botón verde de WhatsApp
        7. Puedes mencionar los productos del catálogo en tus respuestas
        """
    
    # ===== PROMPT GENÉRICO (POR SI ACASO) =====
    else:
        return f"""
        Eres el asistente virtual de {info.get('nombre_tienda', 'la tienda')}.
        Tasa BCV de hoy: {tasa} Bs.
        
        Información de la tienda: {info}
        
        Sé amable, breve y útil. Usa emojis cuando sea apropiado.
        """

# ========== ENDPOINTS ==========
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

        # Generar prompt según la tienda y el asesor
        prompt_sistema = generar_prompt_segun_tienda(INFO, tasa, msg.advisor)

        mensajes_groq = [{"role": "system", "content": prompt_sistema}]
        for m in msg.historial[-4:]:
            if isinstance(m, dict) and "role" in m:
                mensajes_groq.append(m)
        
        mensajes_groq.append({"role": "user", "content": msg.mensaje})

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=mensajes_groq,
            temperature=0.6,
            max_tokens=800
        )

        resp = completion.choices[0].message.content
        
        # ===== LÓGICA DE IMÁGENES (SOLO PARA ELECTROVENTAS) =====
        imagen_url = None
        if "ELECTROVENTAS" in INFO.get("nombre_tienda", "").upper():
            txt_user = msg.mensaje.lower()
            diccionario_fotos = INFO.get("imagenes_productos", {}) 
            
            for prod, url in diccionario_fotos.items():
                if prod.lower() in txt_user:
                    imagen_url = url
                    break
        
        # ===== DISPARADORES DE WHATSAPP (COMPARTIDO) =====
        disparadores = ["comprar", "precio", "pago", "disponible", "cuanto", 
                       "cashea", "krece", "ubicacion", "oferta", "credito", 
                       "interesado", "quiero", "deseo", "adquirir"]
        mostrar_ws = any(p in msg.mensaje.lower() or p in resp.lower() for p in disparadores)

        return {
            "respuesta": resp, 
            "mostrar_whatsapp": mostrar_ws,
            "tasa": tasa,
            "imagen": imagen_url  # Solo tendrá valor para Electroventas
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            "respuesta": "Disculpa, estoy recibiendo muchas consultas. ¿Podemos concretar por WhatsApp para darte una mejor atención? 🚀", 
            "mostrar_whatsapp": True,
            "imagen": None
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
