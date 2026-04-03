# -*- coding: utf-8 -*-
"""
Handlers: CRM & Commercial Intelligence
Commands: /nuevo_cliente, /clientes, /buscar, /radar
"""
from telebot import types
from datetime import date, timedelta
import re

from config import TARGET_BUSINESS_TYPES, BLACKLIST_KEYWORDS, BLACKLIST_WARNING
from database import get_connection
from utils import is_admin, safe_split, sanitize_phone_co


def register(bot):

    # --------------- /nuevo_cliente ---------------

    @bot.message_handler(commands=["nuevo_cliente"])
    def cmd_new_client(message):
        if not is_admin(message):
            return
        try:
            bot.send_message(message.chat.id, "📝 <b>Registro de Nuevo Cliente</b>\n\nEscribe el <b>nombre</b> del cliente:")
            bot.register_next_step_handler(message, step_client_name)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_client_name(message):
        if not is_admin(message):
            return
        try:
            client_data = {"nombre": message.text.strip()}
            bot.send_message(message.chat.id, "📱 Escribe el <b>teléfono</b> del cliente:")
            bot.register_next_step_handler(message, step_client_phone, client_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_client_phone(message, client_data):
        if not is_admin(message):
            return
        try:
            client_data["telefono"] = message.text.strip()
            bot.send_message(message.chat.id, "📍 Escribe la <b>dirección</b> del cliente:")
            bot.register_next_step_handler(message, step_client_address, client_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_client_address(message, client_data):
        if not is_admin(message):
            return
        try:
            client_data["direccion"] = message.text.strip()

            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            for key, info in TARGET_BUSINESS_TYPES.items():
                markup.add(f"{info['emoji']} {info['label']}")
            markup.add("🏪 Otro tipo de negocio")

            bot.send_message(
                message.chat.id,
                "🎯 Selecciona el <b>tipo de negocio</b>:\n(Estos son tus clientes ideales VIP)",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_client_business_select, client_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_client_business_select(message, client_data):
        if not is_admin(message):
            return
        try:
            selected = message.text.strip()

            if "Otro" in selected:
                bot.send_message(message.chat.id, "🏪 Escribe el <b>tipo de negocio</b> manualmente:", reply_markup=types.ReplyKeyboardRemove())
                bot.register_next_step_handler(message, step_client_business_manual, client_data)
                return

            for key, info in TARGET_BUSINESS_TYPES.items():
                if info["label"] in selected:
                    client_data["tipo_negocio"] = key
                    break
            else:
                client_data["tipo_negocio"] = selected

            save_client(bot, message, client_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_client_business_manual(message, client_data):
        if not is_admin(message):
            return
        try:
            business_name = message.text.strip()
            if any(kw in business_name.lower() for kw in BLACKLIST_KEYWORDS):
                client_data["tipo_negocio"] = business_name
                bot.send_message(message.chat.id, BLACKLIST_WARNING)
                bot.register_next_step_handler(message, step_client_blacklist_confirm, client_data)
                return

            client_data["tipo_negocio"] = business_name
            save_client(bot, message, client_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_client_blacklist_confirm(message, client_data):
        if not is_admin(message):
            return
        try:
            answer = message.text.strip().lower()
            if answer in ["si", "sí", "s", "yes"]:
                save_client(bot, message, client_data)
            else:
                bot.send_message(message.chat.id, "✅ Registro cancelado. ¡Sigue buscando clientes VIP!")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /clientes ---------------

    @bot.message_handler(commands=["clientes"])
    def cmd_clients(message):
        if not is_admin(message):
            return
        try:
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("✅ Activos", "⏳ Prospectos", "📋 Todos")
            markup.add("❌ Cancelar")
            bot.send_message(message.chat.id, "👥 <b>CARTERA DE CLIENTES</b>\n\n¿Qué filtro aplicar?", reply_markup=markup)
            bot.register_next_step_handler(message, step_clients_filter)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_clients_filter(message):
        if not is_admin(message):
            return
        try:
            selected = message.text.strip()
            if "Cancelar" in selected:
                bot.send_message(message.chat.id, "❌ Cancelado.", reply_markup=types.ReplyKeyboardRemove())
                return

            conn = get_connection()
            try:
                if "Activos" in selected:
                    clients = conn.execute("SELECT * FROM clientes WHERE estado = 'Activo' ORDER BY nombre").fetchall()
                    label = "ACTIVOS"
                elif "Prospectos" in selected:
                    clients = conn.execute("SELECT * FROM clientes WHERE estado = 'Prospecto' ORDER BY nombre").fetchall()
                    label = "PROSPECTOS"
                else:
                    clients = conn.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
                    label = "TODOS"
            finally:
                conn.close()

            if not clients:
                bot.send_message(message.chat.id, f"📭 No hay clientes ({label}).", reply_markup=types.ReplyKeyboardRemove())
                return

            response = f"👥 <b>CLIENTES — {label}</b> ({len(clients)}):\n\n"
            for c in clients:
                state_icon = "✅" if c["estado"] == "Activo" else "⏳"
                response += f"{state_icon} <b>{c['id']}. {c['nombre']}</b>\n"
                response += f"   📱 {c['telefono'] or 'N/A'} | 🏪 {c['tipo_negocio'] or 'N/A'}\n"
                response += f"   📍 {c['direccion'] or 'N/A'}\n\n"

            if len(response) > 4000:
                for part in safe_split(response):
                    bot.send_message(message.chat.id, part, reply_markup=types.ReplyKeyboardRemove())
            else:
                bot.send_message(message.chat.id, response, reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /buscar ---------------

    @bot.message_handler(commands=["buscar"])
    def cmd_search(message):
        if not is_admin(message):
            return
        try:
            bot.send_message(message.chat.id, "🔍 Escribe el <b>nombre</b> del cliente a buscar:")
            bot.register_next_step_handler(message, step_search)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_search(message):
        if not is_admin(message):
            return
        try:
            query = message.text.strip()
            conn = get_connection()
            try:
                results = conn.execute("SELECT * FROM clientes WHERE nombre LIKE ?", (f"%{query}%",)).fetchall()
            finally:
                conn.close()

            if not results:
                bot.send_message(message.chat.id, f"🔍 No se encontraron clientes con \"{query}\".")
                return

            response = f"🔍 <b>Resultados para \"{query}\":</b>\n\n"
            for c in results:
                state_icon = "✅" if c["estado"] == "Activo" else "⏳"
                response += f"{state_icon} <b>{c['id']}. {c['nombre']}</b>\n"
                response += f"   📱 {c['telefono'] or 'N/A'} | 🏪 {c['tipo_negocio'] or 'N/A'}\n"
                response += f"   📍 {c['direccion'] or 'N/A'}\n\n"

            bot.send_message(message.chat.id, response)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /radar ---------------

    @bot.message_handler(commands=["radar"])
    def cmd_radar(message):
        if not is_admin(message):
            return
        try:
            conn = get_connection()
            try:
                today = date.today()
                report = "📡 <b>RADAR COMERCIAL — JD Trading Oil S.A.S</b>\n"
                report += f"📅 {today.strftime('%d/%m/%Y')}\n"
                report += "━" * 30 + "\n\n"

                # TOP 3 VIP
                top_vip = conn.execute("""
                    SELECT c.id, c.nombre, SUM(p.cantidad * p.precio_venta) as total_ventas
                    FROM clientes c JOIN pedidos p ON c.id = p.cliente_id
                    GROUP BY c.id ORDER BY total_ventas DESC LIMIT 3
                """).fetchall()

                report += "🏆 <b>TOP 3 CLIENTES VIP</b>\n"
                if top_vip:
                    medals = ["🥇", "🥈", "🥉"]
                    for i, row in enumerate(top_vip):
                        report += f"  {medals[i]} {row['nombre']} — ${row['total_ventas']:,.0f}\n"
                else:
                    report += "  Sin datos de ventas aún.\n"
                report += "\n"

                # ALERTA FUGA
                cutoff_date = (today - timedelta(days=14)).isoformat()
                fugue_clients = conn.execute("""
                    SELECT c.id, c.nombre, c.telefono, c.ultima_interaccion
                    FROM clientes c
                    WHERE c.estado = 'Activo' AND c.ultima_interaccion < ?
                    AND NOT EXISTS (SELECT 1 FROM pedidos p WHERE p.cliente_id = c.id AND p.fecha >= ?)
                """, (cutoff_date, cutoff_date)).fetchall()

                report += "🚨 <b>ALERTA FUGA</b> (Sin compras +14 días)\n"
                if fugue_clients:
                    for row in fugue_clients:
                        phone = sanitize_phone_co(row["telefono"])
                        wa_link = f"https://wa.me/{phone}"
                        report += f"  ⚠️ {row['nombre']} — Último contacto: {row['ultima_interaccion']}\n"
                        report += f"     📲 <a href='{wa_link}'>Contactar por WhatsApp</a>\n"
                else:
                    report += "  ✅ Sin alertas de fuga.\n"
                report += "\n"

                # PROSPECTOS FRÍOS
                cold_date = (today - timedelta(days=7)).isoformat()
                cold_prospects = conn.execute("""
                    SELECT id, nombre, telefono, fecha_registro
                    FROM clientes WHERE estado = 'Prospecto' AND fecha_registro < ?
                """, (cold_date,)).fetchall()

                report += "🧊 <b>PROSPECTOS FRÍOS</b> (Registrados hace +7 días)\n"
                if cold_prospects:
                    for row in cold_prospects:
                        report += f"  ❄️ {row['nombre']} — Registrado: {row['fecha_registro']}\n"
                else:
                    report += "  ✅ Sin prospectos fríos.\n"
            finally:
                conn.close()

            bot.send_message(message.chat.id, report, disable_web_page_preview=True)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error al generar radar: {e}")


# =========================================================================
# HELPERS (module-level, outside register())
# =========================================================================

def save_client(bot, message, client_data):
    """Persist client to database and confirm."""
    try:
        today = date.today().isoformat()
        tipo = client_data["tipo_negocio"]

        conn = get_connection()
        try:
            cursor = conn.execute(
                """INSERT INTO clientes (nombre, telefono, direccion, tipo_negocio, estado, fecha_registro, ultima_interaccion)
                   VALUES (?, ?, ?, ?, 'Prospecto', ?, ?)""",
                (client_data["nombre"], client_data["telefono"],
                 client_data["direccion"], tipo, today, today)
            )
            conn.commit()
            client_id = cursor.lastrowid
        finally:
            conn.close()

        pitch = ""
        for key, info in TARGET_BUSINESS_TYPES.items():
            if key == tipo:
                pitch = f"\n\n💡 <b>Tip de venta:</b> {info['pitch']}"
                break

        bot.send_message(
            message.chat.id,
            f"✅ <b>Cliente registrado con éxito</b>\n\n"
            f"🆔 ID: <b>{client_id}</b>\n"
            f"👤 {client_data['nombre']}\n"
            f"📱 {client_data['telefono']}\n"
            f"📍 {client_data['direccion']}\n"
            f"🏪 {tipo}\n"
            f"📌 Estado: Prospecto{pitch}",
            reply_markup=types.ReplyKeyboardRemove()
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Error al guardar cliente: {e}")
