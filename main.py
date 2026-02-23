import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq

app = FastAPI()

# Configuración de CORS para que tu web se comunique con Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# CONFIGURACIÓN DE JAVIER (EL CATÁLOGO DE RESPUESTAS)
# =========================================================
NOMBRE_EMPRESA = "ElectroVentas Cumaná"
UBICACION = "Av. Bermúdez, Edificio CC Bermúdez, Local 4, Cumaná."
CATALOGO_INFO = """
PRODUCTOS Y PRECIOS:
- Smart TV 55" Samsung (4K): $450 (1 año garantía)
- Licuadora Oster (10 vel): $65
- Aire Acondicionado 12,000 BTU Split: $310
- Plancha Black+Decker: $25
- Nevera LG 14 Pies: $780
- Microondas Panasonic: $110

MÉTODOS DE PAGO:
- Divisas: Efectivo, Zelle, Binance (USDT).
- Bolívares: Pago Móvil a tasa BCV del día.

DELIVERY Y ENVÍOS:
- Casco Central de Cumaná: Gratis (compras > $50).
- Zonas alejadas (San Luis, Los Chaimas): $3.
- Envíos nacionales: MRW o Tealca.

HORARIO:
- Lun a Sab: 8:30 AM a 6:00 PM (Corrido).
"""

SYSTEM_PROMPT = f"""
Eres Javier, el asistente estrella de ventas de {NOMBRE_EMPRESA}.
Ubicación: {UBICACION}.

Tu personalidad: Eres amable, servicial y usas un tono cercano (estilo venezolano/oriental respetuoso). 
Si te preguntan algo que no está en el catálogo, di que consultarás con el equipo humano.
Tu objetivo es cerrar la venta o guiar al cliente al botón de WhatsApp.

Aquí tienes los datos actualizados:
{CATALOGO_INFO}
"""
# =========================================================

# Usamos la variable de entorno para seguridad
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

@app.get("/")
def home():
    return {"status": "Javier está activo y listo para vender"}

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    mensaje_usuario = data.get("mensaje")

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": mensaje_usuario}
        ],
        temperature=0.7,
        max_tokens=500
    )
    
    return {"respuesta": completion.choices[0].message.content}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
