"""
Monitor de Precios — Falabella & MacOnline → WhatsApp + Dashboard
-----------------------------------------------------------------
Revisa el precio de productos en distintas tiendas chilenas usando scraping
de datos estructurados (JSON-LD) y:
  1. Te avisa por WhatsApp (via CallMeBot) si el precio bajó.
  2. Guarda un historial enriquecido en data/precios.json para el dashboard web.

Diseñado para ejecutarse como cron job en GitHub Actions.
"""

import json
import os
import sys
import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

# ============ CONFIGURACIÓN ============
load_dotenv()

# Variables de entorno (obligatorias para alertas WhatsApp)
WHATSAPP_PHONE = os.getenv("WHATSAPP_PHONE", "").strip()
WHATSAPP_APIKEY = os.getenv("WHATSAPP_APIKEY", "").strip()

if not WHATSAPP_PHONE or not WHATSAPP_APIKEY:
    print("[WARN] Falta WHATSAPP_PHONE o WHATSAPP_APIKEY — alertas WhatsApp desactivadas.")
    WHATSAPP_ENABLED = False
else:
    WHATSAPP_ENABLED = True

# Zona horaria de Chile
CL_TZ = timezone(timedelta(hours=-4))

# Productos a monitorear
PRODUCTOS: List[Dict[str, Any]] = [
    {
        "nombre": "iPhone 16e 128GB",
        "site": "falabella",
        "tienda": "Falabella",
        "url": "https://www.falabella.com/falabella-cl/product/prod133540251/Apple-IPhone-16e-128GB/17406441",
    },
    {
        "nombre": "iPhone 16e 128GB",
        "site": "maconline",
        "tienda": "MacOnline",
        "url": "https://www.maconline.com/products/iphone-16e#default_sku=MD1Q4BE/A",
    },
    # Añade más productos siguiendo la misma estructura
]

# Rutas de archivos
SCRIPT_DIR = Path(__file__).resolve().parent
ARCHIVO_DASHBOARD = SCRIPT_DIR / "data" / "precios.json"
ARCHIVO_DASHBOARD.parent.mkdir(parents=True, exist_ok=True)

# Máximo de entradas en el historial por producto (30 días × 24 horas)
MAX_HISTORIAL = 720

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(SCRIPT_DIR / "monitor_precio_ml.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ============ SESIÓN HTTP ============

def _crear_sesion() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9",
    })
    return session

SESSION = _crear_sesion()


# ============ SCRAPING ============

def _extraer_jsonld_products(html: str) -> list:
    """Extrae todos los bloques JSON-LD de tipo Product del HTML."""
    bloques = re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.DOTALL,
    )
    productos = []
    for bloque in bloques:
        try:
            data = json.loads(bloque)
        except (json.JSONDecodeError, ValueError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get("@type") == "Product":
                productos.append(item)
    return productos


def _precio_desde_jsonld(producto_ld: dict) -> Optional[int]:
    """Extrae el precio numérico de un bloque JSON-LD Product."""
    offers = producto_ld.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    precio_raw = offers.get("price")
    if precio_raw is None:
        return None
    try:
        precio_str = str(precio_raw)
        if "," in precio_str:
            return int(float(precio_str.replace(".", "").replace(",", "")))
        return int(float(precio_str))
    except (ValueError, TypeError):
        return None


def _extraer_precio_html_fallback(html: str) -> Optional[int]:
    """Fallback: extrae precio del HTML buscando formatos CLP ($XXX.XXX)."""
    precios_clp = re.findall(r'\$\s*(\d{2,3}(?:\.\d{3})+)', html)
    if not precios_clp:
        return None
    for precio_str in precios_clp:
        valor = int(precio_str.replace(".", ""))
        if valor >= 50000:
            return valor
    return None


def obtener_precio(url: str, nombre_tienda: str) -> Optional[Dict[str, Any]]:
    """Obtiene precio de una tienda. Intenta JSON-LD primero, luego regex."""
    try:
        resp = SESSION.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error("Error consultando %s (%s): %s", nombre_tienda, url, e)
        return None

    html = resp.text

    # Intento 1: JSON-LD (más confiable)
    productos_ld = _extraer_jsonld_products(html)
    if productos_ld:
        prod = productos_ld[0]
        precio = _precio_desde_jsonld(prod)
        if precio and precio > 0:
            titulo = prod.get("name", f"{nombre_tienda} - producto")
            return {"precio": precio, "titulo": titulo, "disponible": True, "permalink": url}

    # Intento 2: regex en HTML (fallback)
    precio = _extraer_precio_html_fallback(html)
    if precio:
        logger.info("Precio extraído por fallback HTML en %s: %s", nombre_tienda, precio)
        return {"precio": precio, "titulo": f"{nombre_tienda} - producto", "disponible": True, "permalink": url}

    logger.warning("No se pudo extraer precio en %s: %s", nombre_tienda, url)
    return None


# ============ WHATSAPP ============

def enviar_whatsapp(mensaje: str) -> None:
    """Envía un mensaje a tu WhatsApp vía CallMeBot."""
    if not WHATSAPP_ENABLED:
        logger.info("WhatsApp desactivado — mensaje no enviado: %s", mensaje[:80])
        return
    url = "https://api.callmebot.com/whatsapp.php"
    params = {"phone": WHATSAPP_PHONE, "text": mensaje, "apikey": WHATSAPP_APIKEY}
    try:
        resp = SESSION.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            logger.info("WhatsApp enviado correctamente.")
        else:
            logger.warning("WhatsApp respuesta inesperada: %s", resp.status_code)
    except requests.RequestException as e:
        logger.error("Error enviando WhatsApp: %s", e)


# ============ UTILIDADES ============

def formatear_clp(valor: int) -> str:
    """Formatea número como precio en pesos chilenos."""
    return f"${valor:,.0f}".replace(",", ".")


def cargar_datos_dashboard() -> Dict[str, Any]:
    """Carga los datos del dashboard (data/precios.json)."""
    if ARCHIVO_DASHBOARD.exists():
        try:
            return json.loads(ARCHIVO_DASHBOARD.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.error("Error leyendo datos dashboard: %s", e)
    return {"ultima_actualizacion": None, "productos": {}}


def guardar_datos_dashboard(datos: Dict[str, Any]) -> None:
    """Guarda los datos del dashboard en data/precios.json."""
    ARCHIVO_DASHBOARD.write_text(
        json.dumps(datos, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Dashboard actualizado: %s", ARCHIVO_DASHBOARD)


# ============ LÓGICA PRINCIPAL ============

def main() -> None:
    ahora = datetime.now(CL_TZ).isoformat()
    datos = cargar_datos_dashboard()
    hubo_cambios = False

    for producto in PRODUCTOS:
        nombre = producto["nombre"]
        site = producto["site"]
        tienda = producto["tienda"]
        url = producto["url"]

        info = obtener_precio(url, tienda)
        if info is None:
            continue

        precio_actual = info["precio"]
        logger.info("%s - %s: %s (disponible: %s)", nombre, tienda, formatear_clp(precio_actual), info["disponible"])

        # Obtener o crear entrada en el dashboard
        prod_data = datos["productos"].get(site, {
            "nombre": nombre,
            "tienda": tienda,
            "url": url,
            "precio_actual": None,
            "historial": [],
        })

        precio_anterior = prod_data["precio_actual"]

        # Actualizar precio actual
        prod_data["nombre"] = nombre
        prod_data["tienda"] = tienda
        prod_data["url"] = url
        prod_data["precio_actual"] = precio_actual

        # Agregar al historial (solo si el precio cambió o es la primera vez)
        historial = prod_data.get("historial", [])
        if not historial or historial[-1]["precio"] != precio_actual:
            historial.append({"fecha": ahora, "precio": precio_actual})
            # Limitar tamaño del historial
            if len(historial) > MAX_HISTORIAL:
                historial = historial[-MAX_HISTORIAL:]
            prod_data["historial"] = historial

        datos["productos"][site] = prod_data

        # Alertas WhatsApp
        if not info["disponible"]:
            if precio_anterior is not None:
                mensaje = (
                    f"⚠️ Se agotó/dio de baja: {nombre} ({tienda})\n"
                    f"Último precio visto: {formatear_clp(precio_anterior)}"
                )
                enviar_whatsapp(mensaje)
                hubo_cambios = True
        elif precio_anterior is not None and precio_actual < precio_anterior:
            diferencia = precio_anterior - precio_actual
            pct = (diferencia / precio_anterior) * 100
            mensaje = (
                f"📉 ¡Bajó de precio!\n"
                f"🏷️ {nombre} — {tienda}\n"
                f"Antes: {formatear_clp(precio_anterior)}\n"
                f"Ahora: {formatear_clp(precio_actual)}\n"
                f"Ahorras: {formatear_clp(diferencia)} (-{pct:.1f}%)\n"
                f"🔗 {url}"
            )
            enviar_whatsapp(mensaje)
            hubo_cambios = True
        elif precio_anterior is not None and precio_actual > precio_anterior:
            diferencia = precio_actual - precio_anterior
            pct = (diferencia / precio_anterior) * 100
            mensaje = (
                f"📈 Subió de precio:\n"
                f"🏷️ {nombre} — {tienda}\n"
                f"Antes: {formatear_clp(precio_anterior)}\n"
                f"Ahora: {formatear_clp(precio_actual)}\n"
                f"Diferencia: +{formatear_clp(diferencia)} (+{pct:.1f}%)\n"
                f"🔗 {url}"
            )
            enviar_whatsapp(mensaje)
            hubo_cambios = True
        elif precio_anterior is None:
            logger.info("  (primera revisión, precio guardado como referencia)")

    # Guardar datos del dashboard
    datos["ultima_actualizacion"] = ahora
    guardar_datos_dashboard(datos)

    if not hubo_cambios:
        logger.info("Sin cambios de precio esta vez.")


if __name__ == "__main__":
    main()
