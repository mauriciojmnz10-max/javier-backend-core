import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from typing import List, Optional

app = FastAPI()

# Configuración de seguridad para conectar con tu index.html
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de la IA (Asegúrate de tener la variable GROQ_API_KEY en Render)
client = Groq(api_key=os.environ.get("GROQ_API_KEY", "TU_API_KEY_AQUI"))

# =========================================================
# 1. CONFIGURACIÓN DEL NEGOCIO (Actualizado con tu nueva info)
# =========================================================
USA_CASHEA = True   
USA_KRECE = True    

# Aquí puedes actualizar tus productos cuando quieras
PRODUCTOS = """
- Smartphones: Infinix, Tecno y Samsung (Disponibles con Cashea)
- Smart TV 55" Samsung: $450 (Acepta Cashea)
- Aire Acondicionado 12k BTU: $310 (Acepta Krece/Cashea)
- Nevera LG 14 Pies: $780 (Acepta Cashea/Krece)
- Licuadora Oster: $65
- Plancha Black+Decker: $25
"""

# Info Logística de Electroventas Cumaná
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

    # SYSTEM PROMPT: El cerebro inyectado con la nueva lógica
    SYSTEM_PROMPT = f"""
    Eres Javier, el asesor experto de Electroventas Cumaná. Tu tono es profesional, servicial y experto.

    INFORMACIÓN CRUCIAL DEL NEGOCIO:
    - UBICACIÓN: {UBICACION}
    - HORARIO: {HORARIO}
    - DELIVERY: {DELIVERY}
    - {info_tasa}
    - {calculo_instruccion}
    - PAGOS: {opciones_pago}
    - CATÁLOGO: {PRODUCTOS}

    REGLAS DE ORO:
    1. Si preguntan por UBICACIÓN o DÓNDE ESTÁN, da la dirección exacta en el centro y menciona que somos tienda física.
    2. Si preguntan por DELIVERY, explica que es gratis en el centro de Cumaná.
    3. Si preguntan por CATÁLOGO, menciona las categorías principales y marcas (Infinix, Tecno, Samsung).
    4. Si hay tasa, da precios en $ y aproximado en Bs.
    5. Siempre invita a usar el botón de WhatsApp para concretar o ver el catálogo en PDF.
    6. Mantén las respuestas claras y con buen uso de negritas (**texto**).
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
        return {"respuesta": "Lo siento, mi conexión falló. ¿Puedes escribirme por WhatsApp para atenderte mejor?"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
