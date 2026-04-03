# -*- coding: utf-8 -*-
"""
===========================================================================
  JD TRADING OIL S.A.S — Telegram Bot ERP/CRM/WMS
  Modular Architecture — Entry Point
  Author: Antigravity Core Engine
===========================================================================
  INSTRUCTIONS:
  1. Set environment variables (or edit config.py fallbacks):
     - TELEGRAM_BOT_TOKEN
     - ADMIN_ID
     - GOOGLE_API_KEY
  2. Install dependencies:
     pip install pyTelegramBotAPI reportlab
  3. Run:
     python jd_trading_bot.py
===========================================================================
"""
import telebot
from telebot import types

from config import TOKEN, COMPANY_NAME, logger
from database import init_database
from handlers import register_all


# =========================================================================
# BOT INSTANCE
# =========================================================================
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")


# =========================================================================
# REGISTER ALL HANDLERS
# =========================================================================
register_all(bot)


# =========================================================================
# TELEGRAM MENU
# =========================================================================
def set_bot_commands():
    """Register all commands in the Telegram menu."""
    commands = [
        types.BotCommand("start", "🏢 Panel principal"),
        types.BotCommand("nuevo_cliente", "Registrar nuevo cliente"),
        types.BotCommand("clientes", "👥 Ver cartera de clientes"),
        types.BotCommand("buscar", "🔍 Buscar cliente"),
        types.BotCommand("vender", "Crear pedido de venta"),
        types.BotCommand("pedidos", "📦 Ver pedidos"),
        types.BotCommand("radar", "Inteligencia comercial"),
        types.BotCommand("ruta_pie", "Radar de prospección territorial"),
        types.BotCommand("ruta_camion", "Ruta vehicular de entregas"),
        types.BotCommand("inventario", "📦 Control de stock"),
        types.BotCommand("remision", "Generar remisión PDF"),
        types.BotCommand("despacho_jd", "Despacho formal de bodega"),
        types.BotCommand("gasto", "Registrar gasto operativo"),
        types.BotCommand("entregar", "Marcar pedido como entregado"),
        types.BotCommand("caja", "Estado de resultados financiero"),
        types.BotCommand("editar", "✏️ Editar un registro"),
        types.BotCommand("eliminar", "🗑️ Eliminar un registro"),
        types.BotCommand("backup", "💾 Respaldar base de datos"),
        types.BotCommand("cancelar", "❌ Cancelar acción en curso"),
    ]
    bot.set_my_commands(commands)


# =========================================================================
# MAIN ENTRY POINT
# =========================================================================
if __name__ == "__main__":
    print("=" * 50)
    print(f"  {COMPANY_NAME} — Telegram Bot")
    print("  Inicializando base de datos...")
    init_database()
    print("  Base de datos lista.")
    set_bot_commands()
    print("  Comandos de menú registrados.")

    # Health check server (keeps Render free tier alive)
    from health import start_health_server
    port = start_health_server()
    print(f"  Health server en puerto {port}.")

    print("  Bot en ejecución. Presiona Ctrl+C para detener.")
    print("=" * 50)
    bot.infinity_polling(timeout=60, long_polling_timeout=60)

