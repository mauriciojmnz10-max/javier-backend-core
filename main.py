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
# CONFIGURACIÓN CORS - MODIFICAR SEGÚN TUS NECESIDADES
# =========================================================
ALLOWED_ORIGINS = [
    "https://tugithub.io",  # CAMBIAR por tu dominio de GitHub Pages
    "http://localhost:5500",  # Para pruebas locales
    "http://127.0.0.1:5500",  # Para pruebas locales
    "https://tudominio.com",  # Si tienes dominio propio
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Inicializar cliente de Groq
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    logger.error("GROQ_API_KEY no está configurada")
    raise ValueError("GROQ_API_KEY es requerida")

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
    """Obtiene la tasa del cache o la actualiza si es necesario"""
    # Intentar obtener del cache primero
    tasa_cache = cache_tasa.obtener()
    if tasa_cache:
        return tasa_cache
    
    # Si no hay cache, consultar APIs
    tasa = await obtener_tasa_bcv_async()
    if tasa:
        cache_tasa.actualizar(tasa)
        return tasa
    
    # Si todo falla, retornar None (el prompt manejará este caso)
    return None

async def obtener_tasa_bcv_async():
    """Consulta múltiples fuentes para la tasa BCV de forma asíncrona"""
    urls = [
        "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv",
        "https://ve.dolarapi.com/v1/dolares/oficial",
    ]
    
    for url in urls:
        try:
            # Ejecutar request en un hilo separado para no bloquear
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: requests.get(url, timeout=3)
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Intentar diferentes formatos de respuesta
                if "monitors" in data:  # Formato pydolarvenezuela
                    return float(data['monitors']['bcv']['price'])
                elif "promedio" in data:  # Otro formato
                    return float(data['promedio'])
                elif "price" in data:  # Formato dolarapi
                    return float(data['price'])
                    
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout consultando {url}")
        except Exception as e:
            logger.warning(f"Error consultando {url}: {str(e)}")
            continue
    
    logger.error("Todas las fuentes de tasa BCV fallaron")
    return None

# =========================================================
# CONFIGURACIÓN DEL NEGOCIO (desde variables de entorno)
# =========================================================
def get_config():
    """Obtiene la configuración del negocio desde variables de entorno"""
    return {
        "USA_CASHEA": os.environ.get("USA_CASHEA", "true").lower() == "true",
        "USA_KRECE": os.environ.get("USA_KRECE", "true").lower() == "true",
        "NOMBRE_TIENDA": os.environ.get("NOMBRE_TIENDA", "Electroventas Cumaná"),
        "PRODUCTOS": os.environ.get("PRODUCTOS", """
📱 TELÉFONOS (Disponibles con Cashea):
- Infinix Hot 40 Pro: $195
- Tecno Spark 20 Pro: $180
- Samsung A15: $210
- Infinix Smart 8: $105

📺 ENTRETENIMIENTO:
- Smart TV 32" (Varios modelos): $160
- Smart TV 43" 4K: $280
- Smart TV 55" Samsung Crystal: $450

🏠 HOGAR:
- Aire Acondicionado 12.000 BTU: $310
- Nevera Ejecutiva: $220
- Licuadora Oster: $65
- Ventilador de Pedestal 18": $35
"""),
        "UBICACION": os.environ.get("UBICACION", "Centro de Cumaná, Calle Mariño, Edificio Electroventas"),
        "HORARIO": os.environ.get("HORARIO", "Lunes a Sábado de 8:30 AM a 5:30 PM"),
        "DELIVERY": os.environ.get("DELIVERY", "Delivery GRATIS en zonas céntricas de Cumaná"),
        "WHATSAPP": os.environ.get("WHATSAPP", "584120000000"),
    }

def construir_prompt(tasa, config):
    """Construye el prompt del sistema dinámicamente"""
    
    # Información de tasa
    if tasa:
        info_tasa = f"La tasa oficial BCV actual es: {tasa:.2f} Bs/USD."
        calculo_instruccion = f"Usa {tasa:.2f} para calcular precios aproximados en bolívares cuando te pregunten."
    else:
        info_tasa = "⚠️ NOTA: Las fuentes del BCV están temporalmente no disponibles."
        calculo_instruccion = "Si te preguntan por precios en bolívares, indica amablemente que consulten la tasa del día por WhatsApp para mayor precisión."
    
    # Opciones de pago
    opciones_pago = []
    if config["USA_CASHEA"]:
        opciones_pago.append("✅ **Cashea**: Inicial + 3 cuotas (cada 14 días)")
    if config["USA_KRECE"]:
        opciones_pago.append("✅ **Krece**: Financiamiento flexible por cuotas")
    
    if not opciones_pago:
        opciones_pago_texto = "💰 Solo pago de contado en efectivo, transferencia o pago móvil."
    else:
        opciones_pago_texto = "💰 Métodos de pago:\n" + "\n".join(opciones_pago)
        opciones_pago_texto += "\n💰 También aceptamos: Transferencia, Pago Móvil, Zelle, Binance"

    return f"""Eres Javier, asesor experto de ventas en {config['NOMBRE_TIENDA']}. 

INFORMACIÓN DE LA TIENDA:
- 🏪 **Ubicación**: {config['UBICACION']}
- ⏰ **Horario**: {config['HORARIO']}
- 🚚 **Delivery**: {config['DELIVERY']}

💰 **TASA BCV**: {info_tasa}
{calculo_instruccion}

{opciones_pago_texto}

📦 **CATÁLOGO DE PRODUCTOS**:
{config['PRODUCTOS']}

REGLAS DE CONDUCTA:
1. Saluda siempre de forma amigable: "¡Hola! Soy Javier, ¿en qué puedo ayudarte?"
2. Cuando preguntan por ubicación, da la dirección exacta y menciona que somos tienda física
3. Para preguntas de delivery, explica la cobertura y que es gratis en zonas céntricas
4. Para catálogo, menciona las marcas disponibles (Infinix, Tecno, Samsung) y los precios en dólares
5. Si preguntan por Cashea o Krece, explica los términos con entusiasmo
6. **IMPORTANTE - CIERRE DE VENTAS**: Si el cliente muestra interés de compra (pregunta cómo pagar, dice "me interesa", "quiero comprar", etc.), indícale: "¡Excelente! Para concretar tu compra, haz clic en el botón de WhatsApp que aparecerá y con gusto te asistiré personalmente. ¿Te parece?"
7. Nunca inventes productos que no están en el catálogo
8. Sé conciso pero amable, como un vendedor de tienda física

EJEMPLO DE RESPUESTA IDEAL:
Cliente: "¿Tienen neveras?"
Javier: "¡Hola! Sí, tenemos neveras ejecutivas en $220 con delivery gratis en Cumaná. También tenemos opciones de neveras con congelador. ¿Te gustaría conocer más detalles específicos?" """

# =========================================================
# MODELOS DE DATOS
# =========================================================
class ChatRequest(BaseModel):
    mensaje: str
    historial: Optional[List[dict]] = []

class ChatResponse(BaseModel):
    respuesta: str
    mostrar_whatsapp: bool = False

# =========================================================
# ENDPOINTS
# =========================================================
@app.get("/", response_model=dict)
async def home():
    """Endpoint de bienvenida y verificación"""
    tasa = await obtener_tasa_bcv_con_cache()
    config = get_config()
    
    return {
        "status": "✅ Javier - Asistente Virtual Online",
        "version": "2.0",
        "negocio": config["NOMBRE_TIENDA"],
        "tasa_bcv": tasa if tasa else "No disponible",
        "metodos_pago": {
            "cashea": config["USA_CASHEA"],
            "krece": config["USA_KRECE"]
        },
        "whatsapp": f"https://wa.me/{config['WHATSAPP']}",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Endpoint para monitoreo de Render"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint principal para conversar con Javier
    """
    try:
        # Validar mensaje
        if not request.mensaje or len(request.mensaje) > 2000:
            raise HTTPException(status_code=400, detail="Mensaje inválido o demasiado largo")
        
        # Obtener configuración y tasa
        config = get_config()
        tasa_actual = await obtener_tasa_bcv_con_cache()
        
        # Construir prompt del sistema
        system_prompt = construir_prompt(tasa_actual, config)
        
        # Preparar mensajes para Groq
        messages = [{"role": "system", "content": system_prompt}]
        
        # Agregar historial (limitado a últimos 10 para no exceder tokens)
        if request.historial:
            messages.extend(request.historial[-10:])
        
        # Agregar mensaje actual
        messages.append({"role": "user", "content": request.mensaje})
        
        logger.info(f"Procesando mensaje: {request.mensaje[:50]}...")
        
        # Llamar a Groq con timeout
        try:
            completion = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.chat.completions.create(
                        messages=messages,
                        model="llama-3.3-70b-versatile",
                        temperature=0.2,
                        max_tokens=800,
                        top_p=0.9,
                    )
                ),
                timeout=15.0
            )
            
            respuesta = completion.choices[0].message.content
            
            # Detectar si debe mostrar botón de WhatsApp
            palabras_compra = ["comprar", "quiero", "me interesa", "pago", "concretar", "cómo pago", "qué hago para comprar"]
            mostrar_ws = any(palabra in request.mensaje.lower() for palabra in palabras_compra)
            
            logger.info(f"Respuesta generada. Mostrar WhatsApp: {mostrar_ws}")
            
            return ChatResponse(
                respuesta=respuesta,
                mostrar_whatsapp=mostrar_ws
            )
            
        except asyncio.TimeoutError:
            logger.error("Timeout en llamada a Groq")
            return ChatResponse(
                respuesta="Lo siento, la respuesta está tomando demasiado tiempo. ¿Prefieres contactarnos directamente por WhatsApp para atenderte mejor?",
                mostrar_whatsapp=True
            )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        return ChatResponse(
            respuesta="Lo siento, tuve un problema técnico. ¿Puedes intentar de nuevo o contactarnos por WhatsApp?",
            mostrar_whatsapp=True
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
