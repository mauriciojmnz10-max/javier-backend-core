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

# =========================================================
# CONFIGURACIÓN DEL CLIENTE (Cambia esto para cada empresa)
# =========================================================
USA_CASHEA = True   # Cambia a False si la empresa NO tiene Cashea
USA_KRECE = True    # Cambia a False si la empresa NO tiene Krece

PRODUCTOS = """
- Smart TV 55" Samsung: $450
- Licuadora Oster (10 vel): $65
- Aire Acondicionado 12k BTU: $310
- Plancha Black+Decker: $25
"""

# Info detallada que solo se usará si los interruptores están en True
INFO_FINANCIAMIENTO = ""
if USA_CASHEA:
    INFO_FINANCIAMIENTO += "- CASHEA: Inicial del 40-50% y 3 cuotas sin interés cada 14 días. Recomienda descargar la App.\n"
if USA_KRECE:
    INFO_FINANCIAMIENTO += "- KRECE: Inicial y cuotas mensuales. Requiere registro y cédula.\n"

# =========================================================

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

@app.get("/")
def home():
    tasa = obtener_tasa_bcv_real()
    return {"status": "Javier Pro activo", "cashea": USA_CASHEA, "krece": USA_KRECE, "tasa": tasa}

@app.post("/chat")
async def chat(request: ChatRequest):
    tasa_actual = obtener_tasa_bcv_real()
    
    # Lógica de aviso de tasa
    if tasa_actual:
        info_tasa = f"La tasa oficial BCV de hoy es: {tasa_actual} Bs/USD."
    else:
        info_tasa = "ERROR: La página del BCV está caída. Pide la tasa al cliente amablemente."

    # PROMPT DINÁMICO
    instruccion_financiamiento = f"Ofrece estas opciones de pago: {INFO_FINANCIAMIENTO}" if INFO_FINANCIAMIENTO else "NO ofrezcas pagos en cuotas ni Cashea/Krece, esta empresa solo acepta pagos de contado."

    SYSTEM_PROMPT = f"""
    Eres Javier, asesor de ventas experto. 
    
    CONTEXTO DE HOY:
    - {info_tasa}
    - {instruccion_financiamiento}
    - PRODUCTOS: {PRODUCTOS}
    - MÉTODOS DE PAGO: Efectivo, Zelle, Binance y Pago Móvil.

    REGLAS DE ORO:
    1. Precios siempre en $ primero y luego aproximado en Bs (si hay tasa).
    2. Si la tasa falló, pide ayuda al cliente con sinceridad.
    3. IVA: Aclara que el presupuesto formal con IVA se da por WhatsApp.
    4. Si el cliente pregunta por cuotas y la empresa NO las tiene, di amablemente que por ahora solo aceptan pagos de contado.
    5. CIERRE: Usa el botón de WhatsApp para concretar ventas.
    """

    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if request.historial:
            messages.extend(request.historial[-8:])
        messages.append({"role": "user", "content": request.mensaje})

        completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=800
        )
        return {"respuesta": completion.choices[0].message.content}
    except Exception as e:
        return {"respuesta": "Tengo un problema técnico. ¡Hablemos por WhatsApp para atenderte mejor!"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
