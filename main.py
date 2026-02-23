import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from typing import List, Optional

app = FastAPI()

# CONFIGURACIÓN DE SEGURIDAD (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cuando tengas tu URL definitiva de GitHub Pages, cámbialo por esa URL
    allow_methods=["*"],
    allow_headers=["*"],
)

# MODELO DE DATOS PARA VALIDACIÓN
class MensajeChat(BaseModel):
    mensaje: str
    historial: Optional[List[dict]] = []

# =========================================================
# CONFIGURACIÓN DE JAVIER (CATÁLOGO Y PERSONALIDAD)
# =========================================================
NOMBRE_NEGOCIO = "ElectroVentas Cumaná"
UBICACION = "Av. Bermúdez, Edificio CC Bermúdez, Local 4, Cumaná."
PRODUCTOS = """
- Smart TV 55" Samsung (4K): $450 (1 año garantía)
- Licuadora Oster (10 vel): $65
- Aire Acondicionado 12,000 BTU Split: $310
- Plancha Black+Decker: $25
- Nevera LG 14 Pies: $780
- Microondas Panasonic: $110
"""
PAGOS = "Divisas (Zelle, Binance, Efectivo) y Pago Móvil a tasa BCV."
DELIVERY = "Gratis en el centro de Cumaná para compras > $50. Otros sectores $3."

SYSTEM_PROMPT = f"""
Eres Javier, asesor de ventas experto de {NOMBRE_NEGOCIO}.

INFORMACIÓN DEL NEGOCIO:
- Ubicación: {UBICACION}
- Productos: {PRODUCTOS}
- Métodos de pago: {PAGOS}
- Delivery: {DELIVERY}

DIRECTRICES DE VENTA:
1. Saluda siempre de forma amigable y preséntate como Javier.
2. Escucha las necesidades del cliente y recomienda productos específicos.
3. Cuando el cliente muestre interés, proporciona precio y disponibilidad.
4. Si el cliente quiere comprar, guíalo suavemente a WhatsApp diciendo: "¡Excelente decisión! Para concretar tu compra, haz clic en el botón de WhatsApp y con gusto te atenderé personalmente".
5. NO inventes información. Si no sabes algo, ofrece averiguar con el equipo humano.
6. Sé proactivo y mantén un tono cálido, profesional y oriental/venezolano respetuoso.
"""
# =========================================================

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

@app.get("/")
def home():
    return {"status": "Javier está activo y con memoria mejorada"}

@app.post("/chat")
async def chat(input_data: MensajeChat):
    # Construir el array de mensajes para la IA
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Si hay historial previo, lo agregamos antes del mensaje actual
    if input_data.historial:
        # Limitamos a los últimos 10 mensajes para no saturar
        messages.extend(input_data.historial[-10:])
    
    # Agregamos el mensaje actual del usuario
    messages.append({"role": "user", "content": input_data.mensaje})

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        respuesta_ia = completion.choices[0].message.content
        return {"respuesta": respuesta_ia}
        
    except Exception as e:
        return {"respuesta": "Lo siento, amigo. Hubo un detalle técnico. ¿Podrías repetir tu pregunta?"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
