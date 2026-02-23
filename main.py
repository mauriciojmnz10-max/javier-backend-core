import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from typing import List, Optional

app = FastAPI()

# Configuración de seguridad
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de la IA
client = Groq(api_key=os.environ.get("GROQ_API_KEY", "TU_API_KEY_AQUI"))

# =========================================================
# 1. CONFIGURACIÓN DEL NEGOCIO
# =========================================================
USA_CASHEA = True   
USA_KRECE = True    

PRODUCTOS = """
📱 TELÉFONOS (Disponibles con Cashea):
- Infinix Hot 40 Pro: $195
- Tecno Spark 20 Pro: $180
- Samsung A15: $210
- Infinix Smart 8: $105

📺 ENTRETENIMIENTO:
- Smart TV 32" (Varios modelos): $160
- Smart TV 43" 4K: $280
- Smart TV 55" Samsung Crystal: $450 (Acepta Cashea)

🏠 HOGAR Y LÍNEA BLANCA:
- Aire Acondicionado 12.000 BTU (Split): $310
- Nevera Ejecutiva: $220
- Licuadora Oster 10 velocidades: $65
- Ventilador de Pedestal 18": $35
"""

UBICACION = "Centro de Cumaná, Calle Mariño, Edificio Electroventas (frente a la Plaza)."
HORARIO = "Lunes a Sábado de 8:30 AM a 5:30 PM."
DELIVERY = "Contamos con Delivery GRATIS en zonas céntricas de Cumaná. Envíos nacionales por Zoom y Tealca."

# =========================================================
# 2. SISTEMA DE REDUNDANCIA DE TASA
# =========================================================
def obtener_tasa_bcv_ultra():
    urls = [
        "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv",
        "https://ve.dolarapi.com/v1/dolares/oficial",
        "https://pydolarvenezuela-api.vercel.app/api/v1/dollar/page?page=bcv"
    ]
    
    for url in urls:
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                if "monitors" in data:
                    return float(data['monitors']['bcv']['price'])
                elif "promedio" in data:
                    return float(data['promedio'])
                elif "price" in data:
                    return float(data['price'])
        except:
            continue
    return None

# =========================================================
# 3. DEFINICIÓN DEL CHAT
# =========================================================
class ChatRequest(BaseModel):
    mensaje: str
    historial: Optional[List[dict]] = []

@app.get("/")
def home():
    tasa = obtener_tasa_bcv_ultra()
    return {
        "status": "Javier Pro Online",
        "tasa_en_memoria": tasa if tasa else "Fuentes caídas",
        "negocio": "Electroventas Cumaná"
    }

@app.post("/chat")
async def chat(request: ChatRequest):
    tasa_actual = obtener_tasa_bcv_ultra()
    
    if tasa_actual:
        info_tasa = f"La tasa oficial BCV de hoy es: {tasa_actual} Bs/USD."
        calculo_instruccion = f"Usa {tasa_actual} para calcular precios aproximados en Bs."
    else:
        info_tasa = "AVISO: Las fuentes del BCV están caídas."
        calculo_instruccion = "No tienes la tasa. Pide disculpas y solicita al cliente si conoce el valor del BCV."

    opciones_pago = "Solo contado."
    if USA_CASHEA or USA_KRECE:
        opciones_pago = "Aceptamos: "
        if USA_CASHEA: opciones_pago += "Cashea (Inicial + 3 cuotas cada 14 días). "
        if USA_KRECE: opciones_pago += "Krece (Financiamiento por cuotas)."

    SYSTEM_PROMPT = f"""
    Eres Javier, el asesor experto de Electroventas Cumaná. Tu tono es profesional y experto.

    INFORMACIÓN CRUCIAL:
    - UBICACIÓN: {UBICACION}
    - HORARIO: {HORARIO}
    - DELIVERY: {DELIVERY}
    - {info_tasa}
    - {calculo_instruccion}
    - PAGOS: {opciones_pago}
    - CATÁLOGO: {PRODUCTOS}

    REGLAS:
    1. Si preguntan por UBICACIÓN, da la dirección y menciona que somos tienda física.
    2. Si preguntan por DELIVERY, explica que es gratis en el centro.
    3. Si preguntan por CATÁLOGO, menciona marcas como Infinix, Tecno y Samsung.
    4. Si el cliente está listo para comprar o pregunta cómo pagar, dile que escriba la palabra 'comprar' o 'concretar' para que aparezca el enlace directo a WhatsApp.
    5. No inventes precios.
    """

    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if request.historial:
            messages.extend(request.historial[-8:])
        messages.append({"role": "user", "content": request.mensaje})

        completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=0.2, 
            max_tokens=800
        )
        
        return {"respuesta": completion.choices[0].message.content}

    except Exception as e:
        return {"respuesta": "Lo siento, mi conexión falló. ¿Puedes escribirme por WhatsApp?"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
