# -*- coding: utf-8 -*-
"""
JD Trading Oil S.A.S — Configuration Module
All constants, environment variables, and business rules.
"""
import os
import logging
from urllib.parse import quote

# =========================================================================
# ENVIRONMENT VARIABLES (Zero Trust)
# =========================================================================
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]           # Required — set in Render dashboard
ADMIN_ID = int(os.environ["ADMIN_ID"])                # Required — your Telegram numeric ID
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "") # Optional — needed for /radar, /ruta_pie

# =========================================================================
# LOGGING
# =========================================================================
logger = logging.getLogger("jd_trading_bot")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# =========================================================================
# PRODUCT CATALOG
# =========================================================================
PRODUCT_CATALOG = {
    "Caja Oleosoberano": {"weight": 15.0, "cargo_type": "Solido"},
    "Bidon 18L":         {"weight": 16.2, "cargo_type": "Liquido"},
    "Bidon 20L":         {"weight": 18.2, "cargo_type": "Liquido"},
}

PRODUCT_PDF_MAP = {
    "Caja Oleosoberano": {
        "description": "Hidrogenados Oleosoberano",
        "presentation": "Caja",
    },
    "Bidon 18L": {
        "description": "Aceite Vegetal",
        "presentation": "Bidon 18L",
    },
    "Bidon 20L": {
        "description": "Aceite Vegetal",
        "presentation": "Bidon 20L",
    },
}

# =========================================================================
# COMPANY CONSTANTS (PDFs & Documents)
# =========================================================================
COMPANY_NAME = "JD Trading Oil S.A.S"
COMPANY_ADDRESS = "Diagonal 182#20-71"
COMPANY_CITY = "Bogota"
COMPANY_PHONE = "3204929054"
COMPANY_EMAIL = "Yosoyjorgeduque08@hotmail.com"
WAREHOUSE_ORIGIN = quote("Diagonal 182#20-71, Bogota", safe="")
OWNER_NAME = "Jorge Armando Duque Medina"
OWNER_CC = "10.666.225"

# =========================================================================
# GOOGLE MAPS & ROUTING
# =========================================================================
MAX_WAYPOINTS = 10

# =========================================================================
# BUSINESS INTELLIGENCE — TARGET MARKET
# =========================================================================
MINUTES_PER_STOP = 4
MAX_ROUTE_HOURS = 4
MAX_DISCOVERY_STOPS = 20
DEFAULT_SEARCH_RADIUS = 1500

TARGET_BUSINESS_TYPES = {
    "Polleria/Asadero": {
        "emoji": "🍗",
        "label": "Pollería / Asadero de Pollo",
        "pitch": "Campeones del consumo. Fríen pollo broaster, papas y plátano todo el día. Compran bidones de 18L/20L o cajas semanales.",
        "search_keywords": ["polleria", "asadero de pollo", "pollo broaster", "pollo frito"],
    },
    "Salsamentaria": {
        "emoji": "🍖",
        "label": "Salsamentaria",
        "pitch": "Mini-distribuidores. Abastecen carritos de comidas rápidas de su zona. Si les das buen precio, la salsamentaria vende tus cajas por ti.",
        "search_keywords": ["salsamentaria", "carnes frias", "charcuteria"],
    },
    "Restaurante/Piqueteadero": {
        "emoji": "🍲",
        "label": "Restaurante / Piqueteadero / Empanadas",
        "pitch": "Corrientazos gigantes, fritangas famosas de barrio, fábricas de empanadas. Consumen cajas de 15kg de sólido para fritura que no humee.",
        "search_keywords": ["restaurante corrientazo", "piqueteadero", "fritanga", "empanadas"],
    },
    "Comidas Rapidas": {
        "emoji": "🍔",
        "label": "Comidas Rápidas Independientes",
        "pitch": "Hamburguesas y salchipapas de barrio con 3-4 freidoras industriales prendidas toda la noche.",
        "search_keywords": ["comidas rapidas", "hamburguesas", "salchipapas", "freidora"],
    },
}

SEARCH_RADIUS_OPTIONS = {
    "🚶 500m (muy cerca)": 500,
    "🚶 1 km (ideal)": 1000,
    "🚶 1.5 km (extendido)": 1500,
    "🚶 2 km (caminata larga)": 2000,
    "🚶 3 km (máximo)": 3000,
}

BLACKLIST_KEYWORDS = [
    "kokoriko", "frisby", "kfc", "el corral", "mcdonalds", "mcdonald's",
    "crepes", "waffles", "exito", "éxito", "carulla", "d1", "ara",
    "isimo", "ísimo", "makro", "jumbo", "metro", "olimpica", "olímpica",
    "franquicia", "cadena",
]

BLACKLIST_WARNING = (
    "🚫 <b>¡ALERTA ANTI-TARGET!</b>\n\n"
    "Este tipo de negocio (franquicias/cadenas) paga a 60-120 días "
    "y te secuestra el capital. Tu sistema necesita rotación rápida: "
    "cobrar el viernes para surtir el lunes.\n\n"
    "¿Deseas registrarlo de todas formas? (Si/No)"
)

# TransMilenio stations (return points for walking routes)
TRANSMILENIO_STATIONS = {
    "Portal Norte": "Portal del Norte TransMilenio, Bogota",
    "Toberin": "Estacion Toberin TransMilenio, Bogota",
    "Cardio Infantil": "Estacion Cardio Infantil TransMilenio, Bogota",
    "Calle 187": "Estacion Calle 187 TransMilenio, Bogota",
    "Calle 170": "Estacion Calle 170 TransMilenio, Bogota",
    "Calle 146": "Estacion Calle 146 TransMilenio, Bogota",
    "Calle 142": "Estacion Calle 142 TransMilenio, Bogota",
    "Alcala": "Estacion Alcala TransMilenio, Bogota",
    "Prado": "Estacion Prado TransMilenio, Bogota",
    "Calle 127": "Estacion Calle 127 TransMilenio, Bogota",
}
