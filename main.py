import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from typing import List, Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.environ.get("GROQ_API_KEY", "TU_API_KEY_AQUI"))

def obtener_tasa_bcv_real():
    try:
        url = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data['monitors']['bcv']['price'])
        return None
    except:
        return None

class ChatRequest(BaseModel):
    mensaje: str
    historial: Optional[List[dict]] = []

PRODUCTOS = """
- Smart TV 55" Samsung: $450 (Disponible en Cashea)
- Licuadora Oster: $65
- Aire Acondicionado 12k BTU: $310 (Disponible en Krece)
- Plancha Black+Decker: $25
"""

# INFO FINANCIAMIENTO
INFO_PAGOS = """
CASHEA: 
- Pagas una inicial (usualmente 40% o 50%) y 3 cuotas sin interés cada 14 días. 
- Requisito: Tener la app activa y cupo disponible.
KRECE: 
- Pagas inicial y cuotas. Ideal para electrodomésticos. 
- Requisito: Registro en la plataforma Krece.
"""

@app.post("/chat")
async def chat(request: ChatRequest):
    tasa_actual = obtener_tasa_bcv_real()
    
    if tasa_actual:
        info_tasa = f"La tasa oficial BCV de hoy es: {tasa_actual} Bs/USD."
    else:
        info_tasa = "ERROR: La página del BCV está caída. Pide la tasa al cliente amablemente."

    SYSTEM_PROMPT = f"""
    Eres Javier, el asesor experto de ElectroVentas Cumaná.

    ESTADO DE LA TASA: {info_tasa}
    FINANCIAMIENTO: {INFO_PAGOS}

    REGLAS DE VENTA:
    1. Si el cliente pregunta por cuotas, Cashea o Krece, explica brevemente cómo funciona según la INFO_PAGOS.
    2. Ejemplo Cashea: "Para el TV de $450, pagarías una inicial aproximada de $180 y el resto en cuotas con la App Cashea".
    3. Si la tasa falló, mantén la regla de pedir ayuda al cliente con el monto del dólar.
    4. IVA: Recuérdales que el presupuesto final con IVA se da por WhatsApp.

    PRODUCTOS:
    {PRODUCTOS}
    """

    try:
        completion = client.chat.completions.create(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + (request.historial[-10:] if request.historial else []) + [{"role": "user", "content": request.mensaje}],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=700
        )
        return {"respuesta": completion.choices[0].message.content}
    except Exception as e:
        return {"respuesta": "Lo siento, tuve un error técnico. Escríbenos al WhatsApp para ayudarte."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
