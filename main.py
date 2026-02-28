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

app = FastAPI(title="Sistema Multi-Tienda", version="8.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== CONFIGURACIÓN POR TIENDA ==========
# Los JSON están en la raíz del repositorio

def cargar_config_tienda(store_id: str):
    """Carga la configuración de una tienda específica desde la raíz"""
    nombre_archivo = f"{store_id}.json"  # Directamente en la raíz
    try:
        if os.path.exists(nombre_archivo):
            with open(nombre_archivo, "r", encoding="utf-8") as f:
                return json.load(f)
        logger.error(f"Archivo no encontrado: {nombre_archivo}")
        return None
    except Exception as e:
        logger.error(f"Error cargando {nombre_archivo}: {e}")
        return None

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
    advisor: str = "default"

# ========== GENERADOR DE PROMPTS POR TIENDA ==========
def generar_prompt_segun_tienda(store_id: str, info: dict, tasa: float, advisor: str = "default"):
    """Genera el prompt del sistema según la tienda"""
    
    tienda_nombre = info.get("nombre_tienda", "").upper()
    
    # ===== MULTIKAP =====
    if store_id == "multikap":
        prompts_asesor = {
            "motos": "Eres TAZ MOTOS 🏍️, experto en repuestos y accesorios para motos. Responde con energía y pasión por las motos.",
            "papeleria": "Eres TAZ PAPELERÍA 📚, especialista en útiles escolares y de oficina. Responde con creatividad y orden.",
            "hogar": "Eres TAZ HOGAR 🏠, experto en productos de limpieza y organización del hogar. Responde con calidez y practicidad."
        }
        personalidad = prompts_asesor.get(advisor, "Eres TAZ, el asistente virtual de MultiKAP.")
        
        return f"""
        {personalidad}
        
        Tasa BCV de hoy: {tasa} Bs. Calcula siempre los precios ($ x {tasa}).
        
        Información de la tienda: {json.dumps(info, indent=2, ensure_ascii=False)}
        
        REGLAS IMPORTANTES:
        1. Este es un sistema SIN IMÁGENES. NO menciones "fotos", "imágenes", "mirar", "ver". Usa SOLO texto.
        2. Si el usuario pregunta por productos, guíalo a usar el botón "📋 Ver catálogo"
        3. Los precios deben mostrarse en $ y Bs (calculado con la tasa)
        4. Sé elegante pero con personalidad (usa emojis, sé dinámico)
        5. NUNCA escribas números de teléfono en el texto
        6. Para finalizar la compra, indica que usen el botón verde de WhatsApp
        7. Puedes mencionar los productos del catálogo en tus respuestas
        """
    
    # ===== PANADERÍA =====
    elif store_id == "panaderia":
        return f"""
        Eres Javier, el panadero virtual y experto en productos de panadería artesanal.
        
        Tasa BCV de hoy: {tasa} Bs. Calcula siempre los precios ($ x {tasa}).
        
        Información de la panadería: {json.dumps(info, indent=2, ensure_ascii=False)}
        
        REGLAS IMPORTANTES:
        1. Habla con calidez y pasión por el arte de la panadería
        2. Describe los productos con detalle (textura, sabor, ingredientes)
        3. Los precios deben mostrarse en $ y Bs
        4. Usa emojis de panes, dulces y café 🥖🥐☕
        5. NUNCA escribas números de teléfono en el texto
        6. Para finalizar la compra, indica que usen el botón verde de WhatsApp
        """
    
    # ===== FERRETERÍA =====
    elif store_id == "ferreteria":
        return f"""
        Eres un experto en ferretería y construcción. Conoces todas las herramientas, materiales y soluciones para el hogar y la obra.
        
        Tasa BCV de hoy: {tasa} Bs. Calcula siempre los precios ($ x {tasa}).
        
        Información de la ferretería: {json.dumps(info, indent=2, ensure_ascii=False)}
        
        REGLAS IMPORTANTES:
        1. Habla con conocimiento técnico pero de forma clara
        2. Ofrece consejos prácticos para cada proyecto
        3. Los precios deben mostrarse en $ y Bs
        4. Usa emojis de herramientas 🔨🔧⚒️
        5. NUNCA escribas números de teléfono en el texto
        6. Para finalizar la compra, indica que usen el botón verde de WhatsApp
        """
    
    # ===== MOTO-REPUESTOS =====
    elif store_id == "motorepuestos":
        return f"""
        Eres un experto en motos y repuestos. Conoces todas las marcas, modelos y piezas.
        
        Tasa BCV de hoy: {tasa} Bs. Calcula siempre los precios ($ x {tasa}).
        
        Información de la tienda: {json.dumps(info, indent=2, ensure_ascii=False)}
        
        REGLAS IMPORTANTES:
        1. Habla con pasión por las motos y conocimiento técnico
        2. Ayuda a identificar repuestos por marca y modelo
        3. Los precios deben mostrarse en $ y Bs
        4. Usa emojis de motos y repuestos 🏍️🔧⚙️
        5. NUNCA escribas números de teléfono en el texto
        6. Para finalizar la compra, indica que usen el botón verde de WhatsApp
        """
    
    # ===== PROMPT GENÉRICO =====
    else:
        return f"""
        Eres el asistente virtual de {info.get('nombre_tienda', 'la tienda')}.
        Tasa BCV de hoy: {tasa} Bs.
        
        Información de la tienda: {json.dumps(info, indent=2, ensure_ascii=False)}
        
        Sé amable, breve y útil. Usa emojis cuando sea apropiado.
        """

# ========== ENDPOINTS ==========
@app.get("/config/{store_id}")
async def get_config(store_id: str):
    """Obtiene la configuración de una tienda específica"""
    config = cargar_config_tienda(store_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Tienda no encontrada")
    return config

@app.post("/chat/{store_id}")
async def chat(store_id: str, msg: Message):
    """Procesa mensajes para una tienda específica"""
    try:
        # Cargar configuración de la tienda
        INFO = cargar_config_tienda(store_id)
        if INFO is None:
            raise HTTPException(status_code=404, detail="Tienda no encontrada")
        
        tasa = obtener_tasa_bcv()
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            logger.error("GROQ_API_KEY no configurada")
            return {
                "respuesta": "Lo siento, el servicio de IA no está configurado. Por favor contacta al administrador.",
                "mostrar_whatsapp": True,
                "tasa": tasa
            }
        
        client = Groq(api_key=api_key)

        # Generar prompt según la tienda y el asesor
        prompt_sistema = generar_prompt_segun_tienda(store_id, INFO, tasa, msg.advisor)

        mensajes_groq = [{"role": "system", "content": prompt_sistema}]
        for m in msg.historial[-6:]:
            if isinstance(m, dict) and "role" in m:
                mensajes_groq.append(m)
        
        mensajes_groq.append({"role": "user", "content": msg.mensaje})

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=mensajes_groq,
            temperature=0.7,
            max_tokens=800
        )

        resp = completion.choices[0].message.content
        
        # ===== DISPARADORES DE WHATSAPP =====
        disparadores = ["comprar", "precio", "pago", "disponible", "cuanto", 
                       "ubicacion", "oferta", "interesado", "quiero", "deseo", 
                       "adquirir", "pedir", "ordenar"]
        texto_completo = (msg.mensaje + " " + resp).lower()
        mostrar_ws = any(p in texto_completo for p in disparadores)

        return {
            "respuesta": resp, 
            "mostrar_whatsapp": mostrar_ws,
            "tasa": tasa
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en chat: {str(e)}")
        return {
            "respuesta": "Disculpa, estoy recibiendo muchas consultas. ¿Podemos concretar por WhatsApp para darte una mejor atención? 🚀", 
            "mostrar_whatsapp": True,
            "tasa": obtener_tasa_bcv()
        }

@app.get("/tasa-bcv")
async def get_tasa():
    """Endpoint para obtener tasa BCV actualizada"""
    return {"tasa": obtener_tasa_bcv()}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
