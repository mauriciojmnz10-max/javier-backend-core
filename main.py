import os
import logging
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from datetime import datetime, timedelta

# Configuración de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Javier - Asistente de Ventas", version="3.0")

# =========================================================
# CONFIGURACIÓN CORS (ACTUALIZADA PARA PRODUCCIÓN)
# =========================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# =========================================================
# LÓGICA DE TASA BCV (MULTIFUENTE + CACHÉ)
# =========================================================
cache_tasa = {"valor": None, "fecha": None}

def obtener_tasa_bcv():
    """Busca la tasa en múltiples fuentes para evitar fallos"""
    ahora = datetime.now()
    
    # Si tenemos tasa en caché de hace menos de 1 hora, la usamos
    if cache_tasa["valor"] and cache_tasa["fecha"] > ahora - timedelta(hours=1):
        return cache_tasa["valor"]

    urls = [
        "https://pydolarve.org/api/v1/dollar?monitor=bcv",
        "https://ve.dolarapi.com/v1/dolares/oficial"
    ]

    for url in urls:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                # Extraer valor según la estructura de la API
                valor = data.get("price") or data.get("promedio") or data.get("valor")
                if valor:
                    cache_tasa["valor"] = float(valor)
                    cache_tasa["fecha"] = ahora
                    logger.info(f"✅ Tasa BCV actualizada: {valor}")
                    return float(valor)
        except Exception as e:
            logger.error(f"❌ Error consultando {url}: {e}")
            continue
    
    return cache_tasa["valor"] or 40.50  # Valor de respaldo si todo falla

# =========================================================
# CONFIGURACIÓN DE NEGOCIO
# =========================================================
CONFIG_TIENDA = {
    "NOMBRE_TIENDA": "ELECTROVENTAS CUMANÁ",
    "UBICACION": "Cumaná, Estado Sucre (Centro de la ciudad)",
    "DELIVERY": "Gratis en zona central, costos bajos para zonas periféricas",
    "PRODUCTOS": """
    - Infinix Hot 40 Pro ($190)
    - Infinix Note 40 Pro ($260)
    - Tecno Spark 20 Pro ($175)
    - Samsung A15 ($155)
    - Televisor 32" Smart ($130)
    - (Preguntar por otros modelos disponibles)
    """,
    "METODOS_PAGO": "Pago Móvil, Zelle, Efectivo, Cashea (Cuotas), Krece."
}

# =========================================================
# MODELOS DE DATOS
# =========================================================
class Message(BaseModel):
    mensaje: str
    historial: list = []

# =========================================================
# ENDPOINT PRINCIPAL
# =========================================================
@app.post("/chat")
async def chat(msg: Message):
    try:
        tasa = obtener_tasa_bcv()
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

        # CONSTRUCCIÓN DEL PROMPT CON CÁLCULO FORZADO
        prompt_sistema = f"""
        Eres Javier, asesor experto de {CONFIG_TIENDA['NOMBRE_TIENDA']}.
        
        SITUACIÓN FINANCIERA HOY:
        - Tasa Oficial BCV: {tasa} Bs/USD.
        
        INSTRUCCIÓN MATEMÁTICA OBLIGATORIA:
        - Siempre que menciones un precio, muestra primero el monto en $ y luego calcula e indica el monto en Bs. usando la tasa de {tasa}.
        - Ejemplo de formato: 'El costo es de $100 ({100 * tasa:,.2f} Bs. a tasa BCV)'.
        
        INFORMACIÓN ADICIONAL:
        - Ubicación: {CONFIG_TIENDA['UBICACION']}
        - Delivery: {CONFIG_TIENDA['DELIVERY']}
        - Métodos de Pago: {CONFIG_TIENDA['METODOS_PAGO']}
        
        CATÁLOGO:
        {CONFIG_TIENDA['PRODUCTOS']}

        REGLAS DE PERSONALIDAD:
        - Sé elegante, breve y muy servicial.
        - Si el cliente menciona 'comprar', 'precio', 'pago' o un producto específico, activa el botón de WhatsApp.
        """

        # Preparar mensajes para Groq
        mensajes_groq = [{"role": "system", "content": prompt_sistema}]
        for m in msg.historial[-6:]:  # Enviamos los últimos 6 mensajes para contexto
            mensajes_groq.append(m)
        mensajes_groq.append({"role": "user", "content": msg.mensaje})

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=mensajes_groq,
            temperature=0.7,
            max_tokens=500
        )

        respuesta_texto = completion.choices[0].message.content
        
        # Lógica para mostrar botón de WhatsApp
        palabras_venta = ["comprar", "precio", "pago", "disponible", "cuanto cuesta", "cashea", "krece"]
        mostrar_ws = any(p in msg.mensaje.lower() or p in respuesta_texto.lower() for p in palabras_venta)

        return {
            "respuesta": respuesta_texto,
            "mostrar_whatsapp": mostrar_ws,
            "tasa_usada": tasa
        }

    except Exception as e:
        logger.error(f"Error en el endpoint /chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
