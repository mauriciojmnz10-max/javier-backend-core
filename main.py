import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from typing import List, Optional

app = FastAPI()

# Configuración de seguridad para conectar con tu index.html en GitHub
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de la IA (Asegúrate de tener la variable GROQ_API_KEY en Render)
client = Groq(api_key=os.environ.get("GROQ_API_KEY", "TU_API_KEY_AQUI"))

# =========================================================
# 1. CONFIGURACIÓN DEL NEGOCIO (Personalizable)
# =========================================================
USA_CASHEA = True   # Cambiar a False si el cliente no usa Cashea
USA_KRECE = True    # Cambiar a False si el cliente no usa Krece

PRODUCTOS = """
- Smart TV 55" Samsung: $450 (Acepta Cashea)
- Licuadora Oster (10 vel): $65 (Solo contado)
- Aire Acondicionado 12k BTU: $310 (Acepta Krece/Cashea)
- Plancha Black+Decker: $25 (Solo contado)
- Nevera LG 14 Pies: $780 (Acepta Cashea/Krece)
"""

# =========================================================
# 2. SISTEMA DE REDUNDANCIA DE TASA (3 FUENTES)
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
                # Lógica para diferentes formatos de API
                if "monitors" in data:
                    return float(data['monitors']['bcv']['price'])
                elif "promedio" in data:
                    return float(data['promedio'])
                elif "price" in data:
                    return float(data['price'])
        except:
            continue # Si una falla, intenta con la siguiente
    return None # Si todas fallan

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
        "cashea_activo": USA_CASHEA,
        "krece_activo": USA_KRECE
    }

@app.post("/chat")
async def chat(request: ChatRequest):
    tasa_actual = obtener_tasa_bcv_ultra()
    
    # Manejo de la información de la tasa para el prompt
    if tasa_actual:
        info_tasa = f"La tasa oficial BCV de hoy es: {tasa_actual} Bs/USD."
        calculo_instruccion = f"Usa {tasa_actual} para calcular precios aproximados en Bs."
    else:
        info_tasa = "AVISO: Las fuentes del BCV están caídas."
        calculo_instruccion = "No tienes la tasa. Pide disculpas sinceramente y solicita al cliente si conoce el valor del BCV para ayudarle con la cuenta."

    # Lógica de financiamiento opcional
    opciones_pago = "Solo aceptamos pagos de contado por ahora."
    if USA_CASHEA or USA_KRECE:
        opciones_pago = "Contamos con: "
        if USA_CASHEA: opciones_pago += "Cashea (Inicial + 3 cuotas cada 14 días). "
        if USA_KRECE: opciones_pago += "Krece (Financiamiento por cuotas con registro)."

    # SYSTEM PROMPT: La personalidad y reglas de Javier
    SYSTEM_PROMPT = f"""
    Eres Javier, el asesor experto de ElectroVentas Cumaná. 
    Tu meta es vender y ser extremadamente amable.

    INFO ACTUALIZADA:
    - {info_tasa}
    - {calculo_instruccion}
    - FINANCIAMIENTO: {opciones_pago}
    - CATÁLOGO: {PRODUCTOS}

    REGLAS ESTRICTAS:
    1. Precios siempre en $ primero. Si hay tasa, da el equivalente en Bs aclarando que es "Aproximado".
    2. IVA: Indica siempre que el presupuesto formal con IVA se entrega por WhatsApp.
    3. FINANCIAMIENTO: Si preguntan por cuotas, explica Cashea/Krece solo si están activos en la INFO arriba. Calcula una inicial estimada del 50%.
    4. SI LA TASA FALLA: Di exactamente esto: 'Mil disculpas, mis fuentes oficiales del BCV están fallando. ¿Tendrás el monto de la tasa a mano? Así te doy el precio exacto en bolívares.'
    5. CIERRE: Invita siempre a usar el botón de WhatsApp para concretar la compra.
    """

    try:
        # Construir mensajes con el historial para que tenga memoria
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if request.historial:
            # Tomamos los últimos 8 mensajes para no saturar la memoria
            messages.extend(request.historial[-8:])
        messages.append({"role": "user", "content": request.mensaje})

        completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=0.1, # Muy baja para que no invente números
            max_tokens=800
        )
        
        return {"respuesta": completion.choices[0].message.content}

    except Exception as e:
        return {"respuesta": "Lo siento, mi conexión con el cerebro central falló. ¿Podemos hablar por WhatsApp?"}

if __name__ == "__main__":
    import uvicorn
    # Render usa la variable de entorno PORT
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
