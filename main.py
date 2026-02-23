import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# CONFIGURACIÓN DE JAVIER (EDITA SOLO ESTO PARA PERSONALIZAR)
# =========================================================
NOMBRE_EMPRESA = "ElectroVentas Cumaná"
UBICACION = "Av. Bermúdez, Cumaná, Edo. Sucre"
PRODUCTOS_PRECIOS = """
- Smart TV 55 Pulgadas: $450
- Licuadora Oster: $60
- Aire Acondicionado 12k BTU: $320
- Ventilador de Pedestal: $35
"""
# =========================================================

# El "Cerebro" de Javier que lee la configuración de arriba
SYSTEM_PROMPT = f"""
Eres Javier, un asistente virtual de ventas para {NOMBRE_EMPRESA}.
Estás ubicado en {UBICACION}.
Aquí tienes los productos y precios actuales:
{PRODUCTOS_PRECIOS}

Instrucciones: Responde de forma amable, profesional y concisa. 
Si te preguntan por algo que no está en la lista, indica que el equipo de ventas humano le dará el detalle exacto.
"""

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

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
