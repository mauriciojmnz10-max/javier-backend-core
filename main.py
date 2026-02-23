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

# --- FUNCIÓN PARA OBTENER TASA AUTOMÁTICA DEL BCV ---
def obtener_tasa_bcv_real():
    try:
        # API de comunidad para obtener el dólar oficial en Venezuela
        url = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv"
        response = requests.get(url, timeout=5)
        data = response.json()
        # Extraemos el precio del monitor BCV
        return float(data['monitors']['bcv']['price'])
    except Exception as e:
        print(f"Error al obtener tasa: {e}")
        # Si la API falla, usa el valor de respaldo que configuraste en Render
        return float(os.environ.get("TASA_BCV", "405.35"))

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
    return {"status": "Javier activo", "tasa_detectada": tasa}

@app.post("/chat")
async def chat(request: ChatRequest):
    # Paso 1: Obtener la tasa actualizada en el momento de la pregunta
    TASA_BCV = obtener_tasa_bcv_real()

    # Paso 2: Configurar el Prompt con la tasa fresca
    SYSTEM_PROMPT = f"""
    Eres Javier, el asesor de ventas oficial de ElectroVentas Cumaná.

    REGLAS DE PRECIOS Y PAGOS:
    1. La tasa oficial BCV de hoy es: {TASA_BCV} Bs/USD.
    2. Formato de precio: Siempre da el precio en dólares ($) primero. 
    3. Conversión a Bolívares: Di que el monto en bolívares es una REFERENCIA APROXIMADA.
       Ejemplo: "Son $100, que equivalen aproximadamente a {100 * TASA_BCV} Bs."
    4. IVA: Aclara siempre que "Los precios publicados son base. El monto exacto con IVA y céntimos se confirma en su presupuesto formal al finalizar la compra".
    5. Métodos de Pago: Aceptamos Zelle, Binance, Efectivo y Pago Móvil.

    PRODUCTOS DISPONIBLES:
    {PRODUCTOS}

    LÓGICA DE CIERRE (BOTÓN WHATSAPP):
    - Si el cliente pregunta cómo comprar, métodos de pago o muestra interés claro, dile: 
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
            temperature=0.1, # Temperatura baja para cálculos matemáticos precisos
            max_tokens=600
        )
        
        return {"respuesta": completion.choices[0].message.content}

    except Exception as e:
        return {"respuesta": "Lo siento, tuve un problema con el sistema de precios. ¿Podemos continuar por WhatsApp para darte el monto exacto?"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
