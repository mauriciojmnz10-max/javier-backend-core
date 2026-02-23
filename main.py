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

# Configuración de la IA
client = Groq(api_key=os.environ.get("GROQ_API_KEY", "TU_API_KEY_AQUI"))

# --- FUNCIÓN PARA OBTENER TASA CON DETECCIÓN DE ERRORES ---
def obtener_tasa_bcv_real():
    try:
        # API de comunidad para obtener el dólar oficial en Venezuela
        url = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data['monitors']['bcv']['price'])
        return None
    except Exception as e:
        print(f"Error al obtener tasa: {e}")
        return None

class ChatRequest(BaseModel):
    mensaje: str
    historial: Optional[List[dict]] = []

# PRODUCTOS Y DATOS
PRODUCTOS = """
- Smart TV 55" Samsung: $450
- Licuadora Oster: $65
- Aire Acondicionado 12k BTU: $310
- Plancha Black+Decker: $25
"""

@app.get("/")
def home():
    tasa = obtener_tasa_bcv_real()
    return {"status": "Javier activo", "tasa_detectada": tasa if tasa else "Página caída"}

@app.post("/chat")
async def chat(request: ChatRequest):
    # Paso 1: Intentar obtener la tasa
    tasa_actual = obtener_tasa_bcv_real()

    # Paso 2: Definir el mensaje sobre la tasa para el sistema
    if tasa_actual:
        info_tasa = f"La tasa oficial BCV de hoy es: {tasa_actual} Bs/USD."
    else:
        # Instrucción especial si la página falla
        info_tasa = "ERROR: La página del BCV está caída. DEBES decir: 'Oye, te pido mil disculpas, la página del BCV parece estar caída justo ahora y no puedo ver la tasa oficial. ¿Tú la sabes? Si me das el monto actual, con gusto te calculo el total rápidamente'."

    # Paso 3: Configurar el Prompt con la lógica condicional
    SYSTEM_PROMPT = f"""
    Eres Javier, el asesor de ventas oficial de ElectroVentas Cumaná.

    ESTADO DE LA TASA: {info_tasa}

    REGLAS DE PRECIOS Y PAGOS:
    1. Si la tasa está disponible ({tasa_actual}), da el precio en dólares ($) primero y luego en Bolívares.
    2. Conversión a Bolívares: Di que el monto es una REFERENCIA APROXIMADA.
    3. IVA: Aclara siempre que "Los precios publicados son base. El monto exacto con IVA se confirma en su presupuesto formal al finalizar la compra".
    4. SI LA TASA FALLÓ: No inventes precios en Bs. Pide la tasa al cliente amablemente como se indicó arriba. Si el cliente te la da en el chat, úsala para calcular.
    5. Métodos de Pago: Aceptamos Zelle, Binance, Efectivo y Pago Móvil.

    PRODUCTOS DISPONIBLES:
    {PRODUCTOS}

    LÓGICA DE CIERRE (BOTÓN WHATSAPP):
    - Si el cliente muestra interés claro o quiere pagar, dile: 
      "Para enviarle su presupuesto formal con IVA y concretar el pago, haga clic en el botón de WhatsApp que aparecerá abajo".
    """

    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        if request.historial:
            messages.extend(request.historial[-10:])
        
        messages.append({"role": "user", "content": request.mensaje})

        completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=0.1, 
            max_tokens=600
        )
        
        return {"respuesta": completion.choices[0].message.content}

    except Exception as e:
        return {"respuesta": "Lo siento, tuve un problema con el sistema de precios. ¿Podemos continuar por WhatsApp para darte el monto exacto?"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
