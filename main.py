import os
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

# Configuración de la IA (Usa la variable de entorno GROQ_API_KEY en Render)
client = Groq(api_key=os.environ.get("GROQ_API_KEY", "TU_API_KEY_AQUI"))

# --- CONFIGURACIÓN DE TASA Y NEGOCIO ---
# Recuerda actualizar TASA_BCV en el panel de Render cada mañana
TASA_BCV = float(os.environ.get("TASA_BCV", "54.50"))

class ChatRequest(BaseModel):
    mensaje: str
    historial: Optional[List[dict]] = []

# PRODUCTOS Y DATOS (Personaliza esto según tu cliente)
PRODUCTOS = """
- Smart TV 55" Samsung: $450
- Licuadora Oster: $65
- Aire Acondicionado 12k BTU: $310
- Plancha Black+Decker: $25
"""

# PROMPT DEL SISTEMA: Aquí es donde Javier recibe sus instrucciones
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

@app.get("/")
def home():
    return {{"status": "Javier activo", "tasa_actual": TASA_BCV}}

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Cargar historial para que Javier tenga memoria
        if request.historial:
            messages.extend(request.historial[-10:])
        
        messages.append({"role": "user", "content": request.mensaje})

        completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile", # El modelo más potente disponible
            temperature=0.5, # Mantenerlo enfocado en ventas
            max_tokens=600
        )
        
        return {"respuesta": completion.choices[0].message.content}

    except Exception as e:
        return {"respuesta": "Lo siento, tuve un problema con el cálculo. ¿Podemos continuar por WhatsApp para darte el precio exacto?"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
