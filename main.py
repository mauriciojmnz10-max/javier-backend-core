import os
import logging
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from datetime import datetime, timedelta

# Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Javier - Sistema de Ventas Pro", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# --- SISTEMA DE TASA ---
cache_tasa = {"valor": None, "fecha": None}
def obtener_tasa_bcv():
    ahora = datetime.now()
    if cache_tasa["valor"] and cache_tasa["fecha"] > ahora - timedelta(hours=1):
        return cache_tasa["valor"]
    
    urls = ["https://ve.dolarapi.com/v1/dolares/oficial", "https://pydolarve.org/api/v1/dollar?monitor=bcv"]
    for url in urls:
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                v = data.get("price") or data.get("promedio") or data.get("valor")
                if v:
                    cache_tasa.update({"valor": float(v), "fecha": ahora})
                    return float(v)
        except: continue
    return cache_tasa["valor"] or 42.50

# --- BASE DE DATOS EXTENSA (Aquí puedes meter todo) ---
INFO_EMPRESA = {
    "DATOS_GENERALES": {
        "nombre": "ELECTROVENTAS CUMANÁ",
        "ubicacion": "Calle Mariño, Edif. Centro, Local 2, Cumaná, Sucre.",
        "horario": "Lunes a Sábado: 8:00 AM - 6:00 PM (Corrido)",
        "contacto": "+58 412-0000000"
    },
    "METODOS_PAGO": {
        "bolivares": "Pago Móvil (Banesco/Mercantil), Transferencia.",
        "divisas": "Efectivo, Zelle, Binance Pay.",
        "financiamiento": "Cashea (Paga en cuotas sin interés), Krece (Créditos para teléfonos)."
    },
    "CATALOGO_TELEFONOS": """
        - INFINIX: Hot 40 Pro ($190), Note 40 Pro ($260), Smart 8 ($95).
        - TECNO: Spark 20 Pro ($175), Pova 6 Pro ($240), Spark 20C ($120).
        - SAMSUNG: Galaxy A15 ($155), A54 ($310), A05 ($115).
        - XIAOMI: Redmi Note 13 ($185), Poco X6 Pro ($340).
    """,
    "LINEA_BLANCA_Y_HOGAR": """
        - Neveras: Samsung 11p ($550), Haier ($420).
        - Lavadoras: LG 12kg ($380), Midea 10kg ($290).
        - Televisores: Smart TV 32" ($130), 43" 4K ($260), 55" QLED ($480).
        - Aires Acondicionados: Split 12.000 BTU ($280), 18.000 BTU ($450).
    """,
    "POLITICAS": """
        - Garantía: 1 año por defectos de fábrica en teléfonos, 6 meses en línea blanca.
        - Delivery: Gratis en Cumaná (Casco central), $3-5 zonas foráneas.
        - Cashea: Requiere nivel 1 en adelante. Pago inicial del 40-50%.
    """
}

class Message(BaseModel):
    mensaje: str
    historial: list = []

@app.post("/chat")
async def chat(msg: Message):
    try:
        tasa = obtener_tasa_bcv()
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

        # PROMPT ESTRUCTURADO PARA MANEJAR MUCHA INFO
        prompt_sistema = f"""
        Eres Javier, el cerebro de ventas de {INFO_EMPRESA['DATOS_GENERALES']['nombre']}. 
        Tu objetivo es vender y ser extremadamente preciso.

        ESTADO FINANCIERO: Tasa BCV = {tasa} Bs.
        
        INSTRUCCIÓN DE CÁLCULO:
        Cualquier precio mencionado en $ debe ir acompañado de su valor en Bs. (Precio * {tasa}). 
        Ejemplo: $100 -> 100 * {tasa} = {100*tasa} Bs.

        CONOCIMIENTO DE LA TIENDA:
        - UBICACIÓN Y HORARIO: {INFO_EMPRESA['DATOS_GENERALES']['ubicacion']} | {INFO_EMPRESA['DATOS_GENERALES']['horario']}
        - PAGOS: {INFO_EMPRESA['METODOS_PAGO']}
        - PRODUCTOS MÓVILES: {INFO_EMPRESA['CATALOGO_TELEFONOS']}
        - PRODUCTOS HOGAR: {INFO_EMPRESA['LINEA_BLANCA_Y_HOGAR']}
        - POLÍTICAS Y GARANTÍA: {INFO_EMPRESA['POLITICAS']}

        REGLAS DE RESPUESTA:
        1. Si no encuentras un producto específico en la lista, di que "podemos consultar disponibilidad en almacén" y ofrece contactar por WhatsApp.
        2. Mantén un tono elegante, usa emojis de forma profesional.
        3. No inventes precios.
        """

        mensajes_groq = [{"role": "system", "content": prompt_sistema}]
        for m in msg.historial[-8:]: # Aumentamos historial para conversaciones largas
            mensajes_groq.append(m)
        mensajes_groq.append({"role": "user", "content": msg.mensaje})

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=mensajes_groq,
            temperature=0.6,
            max_tokens=800
        )

        resp = completion.choices[0].message.content
        palabras_venta = ["comprar", "precio", "pago", "disponible", "cuanto", "cashea", "krece", "ubicacion"]
        mostrar_ws = any(p in msg.mensaje.lower() or p in resp.lower() for p in palabras_venta)

        return {"respuesta": resp, "mostrar_whatsapp": mostrar_ws}

    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Error interno")
