# -*- coding: utf-8 -*-
"""
Handlers: CRM & Commercial Intelligence
Commands: /nuevo_cliente, /clientes, /buscar, /radar, /asignar_dia, /nota, /ficha, /seguimiento
"""
from telebot import types
from datetime import date, timedelta
import re

from config import TARGET_BUSINESS_TYPES, BLACKLIST_KEYWORDS, BLACKLIST_WARNING, logger
from database import get_connection
from utils import is_admin, safe_split, sanitize_phone_co, geocode_address

WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
WEEKDAY_EMOJIS = {"Lunes": "1️⃣", "Martes": "2️⃣", "Miércoles": "3️⃣", "Jueves": "4️⃣", "Viernes": "5️⃣", "Sábado": "6️⃣"}


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
            bot.send_message(
                message.chat.id,
                "📍 Escribe la <b>dirección</b> del cliente:\n"
                "<i>(Sé lo más preciso posible para la geolocalización)</i>\n"
                "Ej: Calle 170 #9-15, Bogota"
            )
            bot.register_next_step_handler(message, step_client_address, client_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_client_address(message, client_data):
        if not is_admin(message):
            return
        try:
            client_data["direccion"] = message.text.strip()

            # Auto-geocode the address
            bot.send_message(message.chat.id, "🔍 Geolocalizando dirección...")
            lat, lng = geocode_address(client_data["direccion"])
            if lat is not None:
                client_data["latitud"] = lat
                client_data["longitud"] = lng
                bot.send_message(
                    message.chat.id,
                    f"✅ Ubicación encontrada: <code>{lat:.5f}, {lng:.5f}</code>"
                )
            else:
                client_data["latitud"] = None
                client_data["longitud"] = None
                bot.send_message(
                    message.chat.id,
                    "⚠️ No se encontró ubicación GPS. El cliente se guardará sin coordenadas.\n"
                    "<i>(Puedes actualizarla después con /editar)</i>"
                )

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

            # Ask for visit day
            ask_visit_day(bot, message, client_data)
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
            ask_visit_day(bot, message, client_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_client_blacklist_confirm(message, client_data):
        if not is_admin(message):
            return
        try:
            answer = message.text.strip().lower()
            if answer in ["si", "sí", "s", "yes"]:
                ask_visit_day(bot, message, client_data)
            else:
                bot.send_message(message.chat.id, "✅ Registro cancelado. ¡Sigue buscando clientes VIP!")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def ask_visit_day(bot, message, client_data):
        """Ask user which day of the week to visit this client."""
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        for day in WEEKDAYS:
            markup.add(f"{WEEKDAY_EMOJIS[day]} {day}")
        markup.add("⏭️ Omitir (asignar después)")

        bot.send_message(
            message.chat.id,
            "📅 <b>¿Qué día de la semana visitas a este cliente?</b>\n"
            "<i>(Para armar tu ruta semanal fija)</i>",
            reply_markup=markup
        )
        bot.register_next_step_handler(message, step_client_visit_day, client_data)

    def step_client_visit_day(message, client_data):
        if not is_admin(message):
            return
        try:
            selected = message.text.strip()
            if "Omitir" in selected:
                client_data["dia_visita"] = None
            else:
                for day in WEEKDAYS:
                    if day in selected:
                        client_data["dia_visita"] = day
                        break
                else:
                    client_data["dia_visita"] = None

            save_client(bot, message, client_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /asignar_dia ---------------

    @bot.message_handler(commands=["asignar_dia"])
    def cmd_assign_day(message):
        if not is_admin(message):
            return
        try:
            bot.send_message(message.chat.id, "📅 Escribe el <b>ID del cliente</b> para asignarle un día de visita:")
            bot.register_next_step_handler(message, step_assign_day_id)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_assign_day_id(message):
        if not is_admin(message):
            return
        try:
            client_id = int(message.text.strip())
            conn = get_connection()
            try:
                client = conn.execute("SELECT nombre, dia_visita FROM clientes WHERE id = %s", (client_id,)).fetchone()
            finally:
                conn.close()

            if not client:
                bot.send_message(message.chat.id, f"❌ No existe cliente con ID {client_id}")
                return

            current_day = client["dia_visita"] or "Sin asignar"

            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            for day in WEEKDAYS:
                markup.add(f"{WEEKDAY_EMOJIS[day]} {day}")
            markup.add("🚫 Quitar día asignado")

            bot.send_message(
                message.chat.id,
                f"📅 <b>{client['nombre']}</b>\nDía actual: <b>{current_day}</b>\n\n¿Qué día asignar?",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_assign_day_save, client_id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID inválido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_assign_day_save(message, client_id):
        if not is_admin(message):
            return
        try:
            selected = message.text.strip()
            new_day = None

            if "Quitar" in selected:
                new_day = None
            else:
                for day in WEEKDAYS:
                    if day in selected:
                        new_day = day
                        break

            conn = get_connection()
            try:
                conn.execute("UPDATE clientes SET dia_visita = %s WHERE id = %s", (new_day, client_id))
                conn.commit()
            finally:
                conn.close()

            label = new_day or "Sin asignar"
            bot.send_message(message.chat.id, f"✅ Día de visita actualizado: <b>{label}</b>", reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /clientes ---------------

    @bot.message_handler(commands=["clientes"])
    def cmd_clients(message):
        if not is_admin(message):
            return
        try:
            markup = types.InlineKeyboardMarkup(row_width=3)
            markup.row(
                types.InlineKeyboardButton("✅ Activos", callback_data="clients_filter:Activo"),
                types.InlineKeyboardButton("⏳ Prospectos", callback_data="clients_filter:Prospecto"),
                types.InlineKeyboardButton("📋 Todos", callback_data="clients_filter:Todos"),
            )
            bot.send_message(message.chat.id, "👥 <b>CARTERA DE CLIENTES</b>\n\n¿Qué filtro aplicar?", reply_markup=markup)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("clients_filter:"))
    def handle_clients_filter(call):
        """Handle client filter inline buttons."""
        try:
            bot.answer_callback_query(call.id)
            filter_type = call.data.replace("clients_filter:", "")

            conn = get_connection()
            try:
                if filter_type == "Todos":
                    clients = conn.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
                    label = "TODOS"
                else:
                    clients = conn.execute("SELECT * FROM clientes WHERE estado = %s ORDER BY nombre", (filter_type,)).fetchall()
                    label = filter_type.upper() + "S"
            finally:
                conn.close()

            if not clients:
                bot.send_message(call.message.chat.id, f"📭 No hay clientes ({label}).")
                return

            response = f"👥 <b>CLIENTES — {label}</b> ({len(clients)}):\n\n"
            markup = types.InlineKeyboardMarkup(row_width=2)

            for c in clients:
                state_icon = "✅" if c["estado"] == "Activo" else "⏳"
                day_tag = f" | 📅 {c['dia_visita']}" if c["dia_visita"] else ""
                gps_tag = " 📌" if c["latitud"] else ""
                response += f"{state_icon} <b>{c['id']}. {c['nombre']}</b>{gps_tag}\n"
                response += f"   📱 {c['telefono'] or 'N/A'} | 🏪 {c['tipo_negocio'] or 'N/A'}{day_tag}\n\n"

                markup.add(
                    types.InlineKeyboardButton(f"📋 Ficha #{c['id']} — {c['nombre'][:20]}", callback_data=f"ficha:{c['id']}"),
                )

            if len(response) > 4000:
                for part in safe_split(response):
                    bot.send_message(call.message.chat.id, part)
                # Send buttons separately
                bot.send_message(call.message.chat.id, "👇 <b>Ver ficha de un cliente:</b>", reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, response, reply_markup=markup)
        except Exception as e:
            bot.send_message(call.message.chat.id, f"⚠️ Error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("ficha:"))
    def handle_ficha_callback(call):
        """Handle ficha button — redirect to /ficha command."""
        try:
            bot.answer_callback_query(call.id)
            client_id = call.data.replace("ficha:", "")
            call.message.from_user = call.from_user
            call.message.text = f"/ficha {client_id}"
            bot.process_new_messages([call.message])
        except Exception as e:
            bot.answer_callback_query(call.id, f"⚠️ Error: {e}")

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
                results = conn.execute("SELECT * FROM clientes WHERE nombre ILIKE %s", (f"%{query}%",)).fetchall()
            finally:
                conn.close()

            if not results:
                bot.send_message(message.chat.id, f"🔍 No se encontraron clientes con \"{query}\".")
                return

            response = f"🔍 <b>Resultados para \"{query}\":</b>\n\n"
            for c in results:
                state_icon = "✅" if c["estado"] == "Activo" else "⏳"
                day_tag = f" | 📅 {c['dia_visita']}" if c["dia_visita"] else ""
                response += f"{state_icon} <b>{c['id']}. {c['nombre']}</b>\n"
                response += f"   📱 {c['telefono'] or 'N/A'} | 🏪 {c['tipo_negocio'] or 'N/A'}{day_tag}\n"
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
                    WHERE c.estado = 'Activo' AND c.ultima_interaccion < %s
                    AND NOT EXISTS (SELECT 1 FROM pedidos p WHERE p.cliente_id = c.id AND p.fecha >= %s)
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
                    FROM clientes WHERE estado = 'Prospecto' AND fecha_registro < %s
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

    # --------------- /nota ---------------

    @bot.message_handler(commands=["nota"])
    def cmd_note(message):
        if not is_admin(message):
            return
        try:
            parts = message.text.strip().split(maxsplit=1)
            if len(parts) < 2:
                bot.send_message(message.chat.id, "❌ Uso: /nota [ID_Cliente]")
                return

            client_id = int(parts[1])
            conn = get_connection()
            try:
                client = conn.execute("SELECT nombre FROM clientes WHERE id = %s", (client_id,)).fetchone()
            finally:
                conn.close()

            if not client:
                bot.send_message(message.chat.id, f"❌ No existe cliente con ID {client_id}")
                return

            bot.send_message(
                message.chat.id,
                f"📝 <b>NOTA PARA: {client['nombre']}</b>\n\n"
                "Escribe la nota de visita, observación o recordatorio:"
            )
            bot.register_next_step_handler(message, step_note_save, client_id, client["nombre"])
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID inválido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_note_save(message, client_id, client_name):
        if not is_admin(message):
            return
        try:
            text = message.text.strip()
            today = date.today().isoformat()

            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO notas_cliente (cliente_id, texto, fecha) VALUES (%s, %s, %s)",
                    (client_id, text, today)
                )
                conn.execute("UPDATE clientes SET ultima_interaccion = %s WHERE id = %s", (today, client_id))
                conn.commit()
            finally:
                conn.close()

            bot.send_message(
                message.chat.id,
                f"✅ <b>Nota guardada</b>\n\n"
                f"👤 {client_name}\n"
                f"📝 {text}\n"
                f"📅 {today}"
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /ficha ---------------

    @bot.message_handler(commands=["ficha"])
    def cmd_profile(message):
        if not is_admin(message):
            return
        try:
            parts = message.text.strip().split(maxsplit=1)
            if len(parts) < 2:
                bot.send_message(message.chat.id, "❌ Uso: /ficha [ID_Cliente]")
                return

            client_id = int(parts[1])
            conn = get_connection()
            try:
                client = conn.execute("SELECT * FROM clientes WHERE id = %s", (client_id,)).fetchone()
                if not client:
                    bot.send_message(message.chat.id, f"❌ No existe cliente con ID {client_id}")
                    return

                # Last 5 orders
                orders = conn.execute("""
                    SELECT id, producto, cantidad, precio_venta, estado, estado_pago, fecha
                    FROM pedidos WHERE cliente_id = %s ORDER BY id DESC LIMIT 5
                """, (client_id,)).fetchall()

                # Total billed
                totals = conn.execute("""
                    SELECT COALESCE(SUM(cantidad * precio_venta), 0) as total_vendido,
                           COALESCE(SUM(cantidad * (precio_venta - costo_compra)), 0) as total_utilidad,
                           COUNT(*) as num_pedidos
                    FROM pedidos WHERE cliente_id = %s
                """, (client_id,)).fetchone()

                # Last 3 notes
                notes = conn.execute("""
                    SELECT texto, fecha FROM notas_cliente WHERE cliente_id = %s ORDER BY id DESC LIMIT 3
                """, (client_id,)).fetchall()
            finally:
                conn.close()

            # Build profile
            state_icon = "✅" if client["estado"] == "Activo" else "⏳"
            phone = sanitize_phone_co(client["telefono"])
            wa_url = f"https://wa.me/{phone}"

            days_since = ""
            if client["ultima_interaccion"]:
                delta = (date.today() - date.fromisoformat(client["ultima_interaccion"])).days
                days_since = f" ({delta} días)"

            response = f"📋 <b>FICHA DEL CLIENTE</b>\n"
            response += "━" * 30 + "\n\n"

            response += f"{state_icon} <b>{client['nombre']}</b> (ID: {client_id})\n"
            response += f"📱 {client['telefono'] or 'N/A'} | 🏪 {client['tipo_negocio'] or 'N/A'}\n"
            response += f"📍 {client['direccion'] or 'N/A'}\n"
            if client["dia_visita"]:
                response += f"📅 Día de visita: <b>{client['dia_visita']}</b>\n"
            if client["latitud"]:
                maps_url = f"https://www.google.com/maps?q={client['latitud']},{client['longitud']}"
                response += f"📌 <a href='{maps_url}'>Ver en Google Maps</a>\n"
            response += f"📲 <a href='{wa_url}'>Contactar por WhatsApp</a>\n"
            response += f"📅 Registro: {client['fecha_registro']} | Última interacción: {client['ultima_interaccion']}{days_since}\n\n"

            # Financials
            response += f"💰 <b>Total facturado:</b> ${totals['total_vendido']:,.0f}\n"
            response += f"📈 <b>Utilidad generada:</b> ${totals['total_utilidad']:,.0f}\n"
            response += f"📦 <b>Pedidos totales:</b> {totals['num_pedidos']}\n\n"

            # Orders
            if orders:
                response += "📦 <b>Últimos pedidos:</b>\n"
                for o in orders:
                    total = o["cantidad"] * o["precio_venta"]
                    pay_icon = "🟢" if o["estado_pago"] == "Pagado" else "🔴"
                    response += f"  #{o['id']} | {o['cantidad']}x {o['producto']} | ${total:,.0f} | {o['estado']} {pay_icon}\n"
                response += "\n"

            # Notes
            if notes:
                response += "📝 <b>Últimas notas:</b>\n"
                for n in notes:
                    response += f"  • [{n['fecha']}] {n['texto']}\n"
                response += "\n"

            response += f"💡 Comandos rápidos:\n"
            response += f"  /nota {client_id} — Agregar nota\n"
            response += f"  /repetir {client_id} — Repetir último pedido\n"
            response += f"  /asignar_dia — Cambiar día de visita"

            bot.send_message(message.chat.id, response, disable_web_page_preview=True)
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID inválido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /seguimiento ---------------

    @bot.message_handler(commands=["seguimiento"])
    def cmd_pipeline(message):
        if not is_admin(message):
            return
        try:
            conn = get_connection()
            try:
                states = conn.execute("""
                    SELECT estado, COUNT(*) as c FROM clientes GROUP BY estado ORDER BY
                    CASE estado
                        WHEN 'Prospecto' THEN 1
                        WHEN 'Activo' THEN 2
                        WHEN 'VIP' THEN 3
                        WHEN 'Inactivo' THEN 4
                        ELSE 5
                    END
                """).fetchall()

                total = sum(row["c"] for row in states)

                # VIP candidates (clients with 3+ orders)
                vip_candidates = conn.execute("""
                    SELECT c.id, c.nombre, COUNT(p.id) as num_orders
                    FROM clientes c JOIN pedidos p ON c.id = p.cliente_id
                    WHERE c.estado = 'Activo'
                    GROUP BY c.id HAVING COUNT(p.id) >= 3
                    ORDER BY num_orders DESC LIMIT 5
                """).fetchall()

                # Inactive candidates (active clients, no orders in 30 days)
                cutoff_30 = (date.today() - timedelta(days=30)).isoformat()
                inactive_candidates = conn.execute("""
                    SELECT c.id, c.nombre, c.ultima_interaccion
                    FROM clientes c WHERE c.estado = 'Activo'
                    AND NOT EXISTS (SELECT 1 FROM pedidos p WHERE p.cliente_id = c.id AND p.fecha >= %s)
                """, (cutoff_30,)).fetchall()
            finally:
                conn.close()

            state_emojis = {
                "Prospecto": "⏳", "Activo": "✅", "VIP": "🏆", "Inactivo": "💤"
            }

            response = "📊 <b>PIPELINE COMERCIAL</b>\n"
            response += "━" * 30 + "\n\n"
            response += f"👥 Total clientes: <b>{total}</b>\n\n"

            for row in states:
                emoji = state_emojis.get(row["estado"], "⬜")
                bar_len = int((row["c"] / total) * 15) if total > 0 else 0
                bar = "█" * bar_len + "░" * (15 - bar_len)
                response += f"{emoji} <b>{row['estado']}</b>: {row['c']}\n"
                response += f"   <code>{bar}</code>\n\n"

            if vip_candidates:
                response += "🏆 <b>CANDIDATOS A VIP</b> (3+ compras):\n"
                for v in vip_candidates:
                    response += f"  ⭐ {v['nombre']} — {v['num_orders']} pedidos\n"
                response += "\n"

            if inactive_candidates:
                response += "💤 <b>RIESGO DE INACTIVIDAD</b> (0 pedidos en 30 días):\n"
                for ic in inactive_candidates:
                    response += f"  ⚠️ {ic['nombre']} — Último: {ic['ultima_interaccion']}\n"

            bot.send_message(message.chat.id, response)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")


# =========================================================================
# HELPERS (module-level, outside register())
# =========================================================================

def save_client(bot, message, client_data):
    """Persist client to database with GPS coordinates and visit day."""
    try:
        today = date.today().isoformat()
        tipo = client_data["tipo_negocio"]

        conn = get_connection()
        try:
            cursor = conn.execute(
                """INSERT INTO clientes
                   (nombre, telefono, direccion, tipo_negocio, estado, fecha_registro, ultima_interaccion, latitud, longitud, dia_visita)
                   VALUES (%s, %s, %s, %s, 'Prospecto', %s, %s, %s, %s, %s) RETURNING id""",
                (client_data["nombre"], client_data["telefono"],
                 client_data["direccion"], tipo, today, today,
                 client_data.get("latitud"), client_data.get("longitud"),
                 client_data.get("dia_visita"))
            )
            client_id = cursor.fetchone()["id"]
            conn.commit()
        finally:
            conn.close()

        pitch = ""
        for key, info in TARGET_BUSINESS_TYPES.items():
            if key == tipo:
                pitch = f"\n\n💡 <b>Tip de venta:</b> {info['pitch']}"
                break

        gps_line = ""
        if client_data.get("latitud"):
            gps_line = f"\n📌 GPS: <code>{client_data['latitud']:.5f}, {client_data['longitud']:.5f}</code>"

        day_line = ""
        if client_data.get("dia_visita"):
            day_line = f"\n📅 Día de visita: {client_data['dia_visita']}"

        bot.send_message(
            message.chat.id,
            f"✅ <b>Cliente registrado con éxito</b>\n\n"
            f"🆔 ID: <b>{client_id}</b>\n"
            f"👤 {client_data['nombre']}\n"
            f"📱 {client_data['telefono']}\n"
            f"📍 {client_data['direccion']}{gps_line}{day_line}\n"
            f"🏪 {tipo}\n"
            f"📌 Estado: Prospecto{pitch}",
            reply_markup=types.ReplyKeyboardRemove()
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Error al guardar cliente: {e}")
