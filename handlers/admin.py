# -*- coding: utf-8 -*-
"""
Handlers: Admin & Dashboard
Commands: /start, /cancelar, /eliminar, /editar, /backup
"""
from telebot import types
from datetime import date, datetime
import os

from config import COMPANY_NAME, PRODUCT_CATALOG
from database import get_connection
from utils import is_admin, safe_split


def register(bot):

    # ── MODULE DEFINITIONS (used by drill-down menu) ──

    MODULES = {
        "crm": {
            "title": "👥 MÓDULO CRM",
            "desc": "Gestión de clientes, notas y seguimiento comercial",
            "buttons": [
                ("👤 Nuevo Cliente", "cmd_nuevo_cliente"),
                ("👥 Ver Cartera", "cmd_clientes"),
                ("🔍 Buscar", "cmd_buscar"),
                ("📋 Ficha Cliente", "cmd_ficha"),
                ("📝 Nota de Visita", "cmd_nota"),
                ("📊 Pipeline", "cmd_seguimiento"),
                ("📡 Radar Comercial", "cmd_radar"),
                ("📅 Asignar Día", "cmd_asignar_dia"),
            ],
        },
        "ventas": {
            "title": "🛒 MÓDULO VENTAS",
            "desc": "Pedidos, entregas y cobros",
            "buttons": [
                ("🛒 Crear Pedido", "cmd_vender"),
                ("🔄 Repetir Pedido", "cmd_repetir"),
                ("📦 Ver Pedidos", "cmd_pedidos"),
                ("✅ Marcar Entregado", "cmd_entregar"),
                ("💳 Cobros Pendientes", "cmd_cobrar"),
                ("💵 Marcar Pagado", "cmd_pagar"),
            ],
        },
        "precios": {
            "title": "💰 MÓDULO PRECIOS",
            "desc": "Lista de precios, PDF y cotizaciones WhatsApp",
            "buttons": [
                ("💰 Ver Precios", "cmd_precios"),
                ("📄 PDF Precios", "price_pdf"),
                ("📲 Cotizar WhatsApp", "cmd_cotizar"),
            ],
        },
        "logistica": {
            "title": "🚚 MÓDULO LOGÍSTICA",
            "desc": "Rutas de trabajo, inventario y distribución",
            "buttons": [
                ("📅 Ruta Semanal", "cmd_ruta_semanal"),
                ("🗺️ Prospección Pie", "cmd_ruta_pie"),
                ("🚚 Entregas Camión", "cmd_ruta_camion"),
                ("📦 Inventario", "cmd_inventario"),
            ],
        },
        "finanzas": {
            "title": "💼 MÓDULO FINANZAS",
            "desc": "Caja, cartera, márgenes y metas de ventas",
            "buttons": [
                ("💼 Estado de Caja", "cmd_caja"),
                ("💳 Cartera x Cobrar", "cmd_cuentas_por_cobrar"),
                ("📝 Registrar Gasto", "cmd_gasto"),
                ("📈 Margen Rentabilidad", "cmd_margen"),
                ("🎯 Meta Mensual", "cmd_meta"),
                ("⚙️ Configurar Meta", "cmd_meta_set"),
            ],
        },
        "documentos": {
            "title": "📄 MÓDULO DOCUMENTOS",
            "desc": "Remisiones y despachos formales en PDF",
            "buttons": [
                ("📄 Remisión PDF", "cmd_remision"),
                ("🚛 Despacho Formal", "cmd_despacho_jd"),
            ],
        },
        "admin": {
            "title": "⚙️ MÓDULO ADMIN",
            "desc": "Edición, eliminación y respaldos",
            "buttons": [
                ("✏️ Editar Registro", "cmd_editar"),
                ("🗑️ Eliminar Registro", "cmd_eliminar"),
                ("💾 Backup BD", "cmd_backup"),
            ],
        },
    }

    MODULE_MENU_BUTTONS = [
        ("👥 CRM", "mod_crm"),
        ("🛒 Ventas", "mod_ventas"),
        ("💰 Precios", "mod_precios"),
        ("🚚 Logística", "mod_logistica"),
        ("💼 Finanzas", "mod_finanzas"),
        ("📄 Documentos", "mod_documentos"),
        ("⚙️ Admin", "mod_admin"),
    ]

    def build_main_menu_markup():
        """Build the main module selector inline keyboard."""
        mk = types.InlineKeyboardMarkup(row_width=2)
        mk.row(
            types.InlineKeyboardButton("👥 CRM", callback_data="mod_crm"),
            types.InlineKeyboardButton("🛒 Ventas", callback_data="mod_ventas"),
        )
        mk.row(
            types.InlineKeyboardButton("💰 Precios", callback_data="mod_precios"),
            types.InlineKeyboardButton("🚚 Logística", callback_data="mod_logistica"),
        )
        mk.row(
            types.InlineKeyboardButton("💼 Finanzas", callback_data="mod_finanzas"),
            types.InlineKeyboardButton("📄 Documentos", callback_data="mod_documentos"),
        )
        mk.row(
            types.InlineKeyboardButton("⚙️ Admin", callback_data="mod_admin"),
        )
        return mk

    def build_main_menu_text(total_clients, active_clients, prospects, pending_orders, unpaid, today_sales):
        """Build the main dashboard text."""
        text = "🏢 <b>JD TRADING OIL S.A.S</b>\n"
        text += f"📅 {date.today().strftime('%d/%m/%Y')}\n"
        text += "━" * 32 + "\n\n"
        text += "📊 <b>PANEL RÁPIDO:</b>\n"
        text += f"  👥 Clientes: {total_clients} (✅ {active_clients} | ⏳ {prospects})\n"
        text += f"  📦 Pendientes: <b>{pending_orders}</b>\n"
        text += f"  💳 Sin pagar: <b>{unpaid}</b>\n"
        text += f"  💰 Ventas hoy: <b>${today_sales:,.0f}</b>\n\n"
        text += "👇 <b>Selecciona un módulo:</b>"
        return text

    def build_module_markup(module_key):
        """Build inline keyboard for a specific module's sub-commands."""
        mod = MODULES[module_key]
        mk = types.InlineKeyboardMarkup(row_width=2)
        buttons = mod["buttons"]
        for i in range(0, len(buttons), 2):
            row = [types.InlineKeyboardButton(buttons[i][0], callback_data=buttons[i][1])]
            if i + 1 < len(buttons):
                row.append(types.InlineKeyboardButton(buttons[i+1][0], callback_data=buttons[i+1][1]))
            mk.row(*row)
        mk.row(types.InlineKeyboardButton("← Volver al Panel", callback_data="mod_back"))
        return mk

    def build_module_text(module_key):
        """Build text for a specific module view."""
        mod = MODULES[module_key]
        text = f"{mod['title']}\n"
        text += f"<i>{mod['desc']}</i>\n"
        text += "━" * 32 + "\n\n"
        text += "👇 <b>Selecciona una opción:</b>"
        return text

    # --------------- /start ---------------

    @bot.message_handler(commands=["start"])
    def cmd_start(message):
        if not is_admin(message):
            return
        try:
            conn = get_connection()
            try:
                total_clients = conn.execute("SELECT COUNT(*) as c FROM clientes").fetchone()["c"]
                active_clients = conn.execute("SELECT COUNT(*) as c FROM clientes WHERE estado = 'Activo'").fetchone()["c"]
                prospects = conn.execute("SELECT COUNT(*) as c FROM clientes WHERE estado = 'Prospecto'").fetchone()["c"]
                pending_orders = conn.execute("SELECT COUNT(*) as c FROM pedidos WHERE estado = 'Pendiente'").fetchone()["c"]
                unpaid = conn.execute("SELECT COUNT(*) as c FROM pedidos WHERE estado = 'Entregado' AND (estado_pago IS NULL OR estado_pago = 'Pendiente')").fetchone()["c"]
                today = date.today().isoformat()
                today_sales = conn.execute(
                    "SELECT COALESCE(SUM(cantidad * precio_venta), 0) as t FROM pedidos WHERE fecha = %s", (today,)
                ).fetchone()["t"]
            finally:
                conn.close()

            text = build_main_menu_text(total_clients, active_clients, prospects, pending_orders, unpaid, today_sales)
            bot.send_message(message.chat.id, text, reply_markup=build_main_menu_markup())
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- MODULE DRILL-DOWN ---------------

    @bot.callback_query_handler(func=lambda call: call.data.startswith("mod_"))
    def handle_module_navigation(call):
        """Handle module selection — edit message to show sub-options."""
        try:
            bot.answer_callback_query(call.id)
            action = call.data.replace("mod_", "")

            if action == "back":
                # Return to main menu — re-fetch stats
                conn = get_connection()
                try:
                    total_clients = conn.execute("SELECT COUNT(*) as c FROM clientes").fetchone()["c"]
                    active_clients = conn.execute("SELECT COUNT(*) as c FROM clientes WHERE estado = 'Activo'").fetchone()["c"]
                    prospects = conn.execute("SELECT COUNT(*) as c FROM clientes WHERE estado = 'Prospecto'").fetchone()["c"]
                    pending_orders = conn.execute("SELECT COUNT(*) as c FROM pedidos WHERE estado = 'Pendiente'").fetchone()["c"]
                    unpaid = conn.execute("SELECT COUNT(*) as c FROM pedidos WHERE estado = 'Entregado' AND (estado_pago IS NULL OR estado_pago = 'Pendiente')").fetchone()["c"]
                    today = date.today().isoformat()
                    today_sales = conn.execute(
                        "SELECT COALESCE(SUM(cantidad * precio_venta), 0) as t FROM pedidos WHERE fecha = %s", (today,)
                    ).fetchone()["t"]
                finally:
                    conn.close()

                text = build_main_menu_text(total_clients, active_clients, prospects, pending_orders, unpaid, today_sales)
                bot.edit_message_text(
                    text, call.message.chat.id, call.message.message_id,
                    reply_markup=build_main_menu_markup()
                )
            elif action in MODULES:
                text = build_module_text(action)
                bot.edit_message_text(
                    text, call.message.chat.id, call.message.message_id,
                    reply_markup=build_module_markup(action)
                )
        except Exception as e:
            try:
                bot.answer_callback_query(call.id, f"⚠️ Error: {e}")
            except Exception:
                pass

    # --------------- INLINE BUTTON ROUTER ---------------

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cmd_"))
    def handle_command_buttons(call):
        """Route inline button presses to their corresponding commands."""
        try:
            bot.answer_callback_query(call.id)
            cmd = call.data.replace("cmd_", "")
            call.message.from_user = call.from_user
            call.message.text = f"/{cmd}"
            bot.process_new_messages([call.message])
        except Exception as e:
            bot.answer_callback_query(call.id, f"⚠️ Error: {e}")

    # --------------- /cancelar ---------------

    @bot.message_handler(commands=["cancelar"])
    def cmd_cancel(message):
        if not is_admin(message):
            return
        bot.clear_step_handler_by_chat_id(message.chat.id)
        bot.send_message(
            message.chat.id,
            "❌ <b>Acción cancelada.</b>\nTodos los flujos pendientes han sido detenidos.",
            reply_markup=types.ReplyKeyboardRemove()
        )

    # --------------- /backup ---------------

    @bot.message_handler(commands=["backup"])
    def cmd_backup(message):
        if not is_admin(message):
            return
        try:
            import io
            tables = ["clientes", "pedidos", "finanzas", "inventario", "precios", "metas", "notas_cliente"]
            backup_text = f"-- JD Trading Backup — {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"

            for table in tables:
                conn = get_connection()
                try:
                    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                finally:
                    conn.close()

                backup_text += f"-- TABLE: {table} ({len(rows)} rows)\n"
                if rows:
                    cols = list(rows[0].keys())
                    backup_text += ",".join(cols) + "\n"
                    for r in rows:
                        backup_text += ",".join(str(r[c]) if r[c] is not None else "" for c in cols) + "\n"
                backup_text += "\n"

            file_bytes = io.BytesIO(backup_text.encode("utf-8"))
            file_bytes.name = f"jd_trading_backup_{date.today().isoformat()}.csv"

            bot.send_document(
                message.chat.id,
                file_bytes,
                visible_file_name=file_bytes.name,
                caption=f"💾 Respaldo de BD (Supabase) — {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error al generar backup: {e}")

    # --------------- /eliminar ---------------

    @bot.message_handler(commands=["eliminar"])
    def cmd_delete(message):
        if not is_admin(message):
            return
        try:
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("👤 Eliminar Cliente")
            markup.add("📦 Eliminar Pedido")
            markup.add("💰 Eliminar Registro Financiero")
            markup.add("❌ Cancelar")

            bot.send_message(
                message.chat.id,
                "🗑️ <b>ELIMINAR REGISTRO</b>\n\n"
                "¿Qué tipo de registro deseas eliminar?",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_delete_type)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_delete_type(message):
        if not is_admin(message):
            return
        try:
            selected = message.text.strip()
            if "Cancelar" in selected:
                bot.send_message(message.chat.id, "❌ Operación cancelada.", reply_markup=types.ReplyKeyboardRemove())
                return

            if "Cliente" in selected:
                conn = get_connection()
                try:
                    clients = conn.execute("SELECT id, nombre, telefono, estado FROM clientes ORDER BY id DESC LIMIT 20").fetchall()
                finally:
                    conn.close()

                if not clients:
                    bot.send_message(message.chat.id, "💭 No hay clientes registrados.", reply_markup=types.ReplyKeyboardRemove())
                    return

                listing = "👤 <b>CLIENTES (últimos 20):</b>\n\n"
                for c in clients:
                    listing += f"  🆔 <b>{c['id']}</b> — {c['nombre']} ({c['estado']})\n"
                listing += "\n✍️ Escribe el <b>ID</b> del cliente a eliminar:"

                bot.send_message(message.chat.id, listing, reply_markup=types.ReplyKeyboardRemove())
                bot.register_next_step_handler(message, step_delete_client_confirm)

            elif "Pedido" in selected:
                conn = get_connection()
                try:
                    orders = conn.execute("""
                        SELECT p.id, c.nombre, p.producto, p.cantidad, p.estado, p.fecha
                        FROM pedidos p JOIN clientes c ON p.cliente_id = c.id
                        ORDER BY p.id DESC LIMIT 20
                    """).fetchall()
                finally:
                    conn.close()

                if not orders:
                    bot.send_message(message.chat.id, "📦 No hay pedidos registrados.", reply_markup=types.ReplyKeyboardRemove())
                    return

                listing = "📦 <b>PEDIDOS (últimos 20):</b>\n\n"
                for o in orders:
                    listing += (f"  🆔 <b>{o['id']}</b> — {o['nombre']} | "
                                f"{o['cantidad']}x {o['producto']} | {o['estado']} | {o['fecha']}\n")
                listing += "\n✍️ Escribe el <b>ID</b> del pedido a eliminar:"

                bot.send_message(message.chat.id, listing, reply_markup=types.ReplyKeyboardRemove())
                bot.register_next_step_handler(message, step_delete_order_confirm)

            elif "Financiero" in selected:
                conn = get_connection()
                try:
                    records = conn.execute("SELECT id, tipo, concepto, monto, fecha FROM finanzas ORDER BY id DESC LIMIT 20").fetchall()
                finally:
                    conn.close()

                if not records:
                    bot.send_message(message.chat.id, "💰 No hay registros financieros.", reply_markup=types.ReplyKeyboardRemove())
                    return

                listing = "💰 <b>REGISTROS FINANCIEROS (últimos 20):</b>\n\n"
                for r in records:
                    listing += (f"  🆔 <b>{r['id']}</b> — {r['tipo']} | "
                                f"{r['concepto']} | ${r['monto']:,.0f} | {r['fecha']}\n")
                listing += "\n✍️ Escribe el <b>ID</b> del registro a eliminar:"

                bot.send_message(message.chat.id, listing, reply_markup=types.ReplyKeyboardRemove())
                bot.register_next_step_handler(message, step_delete_finance_confirm)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_delete_client_confirm(message):
        if not is_admin(message):
            return
        try:
            record_id = int(message.text.strip())
            conn = get_connection()
            try:
                client = conn.execute("SELECT nombre FROM clientes WHERE id = %s", (record_id,)).fetchone()
            finally:
                conn.close()

            if not client:
                bot.send_message(message.chat.id, f"❌ No existe un cliente con ID {record_id}")
                return

            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("✅ Sí, eliminar", "❌ No, cancelar")

            bot.send_message(
                message.chat.id,
                f"⚠️ <b>¿Eliminar al cliente \"{client['nombre']}\" (ID: {record_id})?</b>\n\n"
                "🚨 Esto también eliminará todos sus pedidos y registros financieros.",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_delete_client_execute, record_id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Debes escribir un número de ID válido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_delete_client_execute(message, record_id):
        if not is_admin(message):
            return
        try:
            if "Sí" in message.text:
                conn = get_connection()
                try:
                    conn.execute("DELETE FROM finanzas WHERE pedido_id IN (SELECT id FROM pedidos WHERE cliente_id = %s)", (record_id,))
                    conn.execute("DELETE FROM pedidos WHERE cliente_id = %s", (record_id,))
                    conn.execute("DELETE FROM clientes WHERE id = %s", (record_id,))
                    conn.commit()
                finally:
                    conn.close()
                bot.send_message(message.chat.id, f"✅ Cliente ID {record_id} eliminado con todos sus registros.",
                                 reply_markup=types.ReplyKeyboardRemove())
            else:
                bot.send_message(message.chat.id, "❌ Eliminación cancelada.", reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_delete_order_confirm(message):
        if not is_admin(message):
            return
        try:
            record_id = int(message.text.strip())
            conn = get_connection()
            try:
                order = conn.execute("""
                    SELECT p.producto, p.cantidad, c.nombre
                    FROM pedidos p JOIN clientes c ON p.cliente_id = c.id
                    WHERE p.id = %s
                """, (record_id,)).fetchone()
            finally:
                conn.close()

            if not order:
                bot.send_message(message.chat.id, f"❌ No existe un pedido con ID {record_id}")
                return

            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("✅ Sí, eliminar", "❌ No, cancelar")

            bot.send_message(
                message.chat.id,
                f"⚠️ <b>¿Eliminar pedido ID {record_id}?</b>\n"
                f"👤 {order['nombre']} — {order['cantidad']}x {order['producto']}",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_delete_order_execute, record_id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Debes escribir un número de ID válido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_delete_order_execute(message, record_id):
        if not is_admin(message):
            return
        try:
            if "Sí" in message.text:
                conn = get_connection()
                try:
                    conn.execute("DELETE FROM finanzas WHERE pedido_id = %s", (record_id,))
                    conn.execute("DELETE FROM pedidos WHERE id = %s", (record_id,))
                    conn.commit()
                finally:
                    conn.close()
                bot.send_message(message.chat.id, f"✅ Pedido ID {record_id} eliminado.", reply_markup=types.ReplyKeyboardRemove())
            else:
                bot.send_message(message.chat.id, "❌ Eliminación cancelada.", reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_delete_finance_confirm(message):
        if not is_admin(message):
            return
        try:
            record_id = int(message.text.strip())
            conn = get_connection()
            try:
                record = conn.execute("SELECT tipo, concepto, monto FROM finanzas WHERE id = %s", (record_id,)).fetchone()
            finally:
                conn.close()

            if not record:
                bot.send_message(message.chat.id, f"❌ No existe un registro financiero con ID {record_id}")
                return

            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("✅ Sí, eliminar", "❌ No, cancelar")

            bot.send_message(
                message.chat.id,
                f"⚠️ <b>¿Eliminar registro financiero ID {record_id}?</b>\n"
                f"💰 {record['tipo']} — {record['concepto']} — ${record['monto']:,.0f}",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_delete_finance_execute, record_id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Debes escribir un número de ID válido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_delete_finance_execute(message, record_id):
        if not is_admin(message):
            return
        try:
            if "Sí" in message.text:
                conn = get_connection()
                try:
                    conn.execute("DELETE FROM finanzas WHERE id = %s", (record_id,))
                    conn.commit()
                finally:
                    conn.close()
                bot.send_message(message.chat.id, f"✅ Registro financiero ID {record_id} eliminado.", reply_markup=types.ReplyKeyboardRemove())
            else:
                bot.send_message(message.chat.id, "❌ Eliminación cancelada.", reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /editar ---------------

    @bot.message_handler(commands=["editar"])
    def cmd_edit(message):
        if not is_admin(message):
            return
        try:
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("👤 Editar Cliente")
            markup.add("📦 Editar Pedido")
            markup.add("🚫 Cancelar Pedido")
            markup.add("❌ Cancelar")

            bot.send_message(message.chat.id, "✏️ <b>EDITAR REGISTRO</b>\n\n¿Qué deseas editar?", reply_markup=markup)
            bot.register_next_step_handler(message, step_edit_type)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_edit_type(message):
        if not is_admin(message):
            return
        try:
            selected = message.text.strip()
            if "Cancelar Pedido" in selected:
                # Cancel order flow
                conn = get_connection()
                try:
                    orders = conn.execute("""
                        SELECT p.id, c.nombre, p.producto, p.cantidad, p.estado, p.fecha
                        FROM pedidos p JOIN clientes c ON p.cliente_id = c.id
                        WHERE p.estado != 'Cancelado'
                        ORDER BY p.id DESC LIMIT 20
                    """).fetchall()
                finally:
                    conn.close()

                if not orders:
                    bot.send_message(message.chat.id, "📦 No hay pedidos activos.", reply_markup=types.ReplyKeyboardRemove())
                    return

                listing = "🚫 <b>CANCELAR PEDIDO</b>\n\n"
                for o in orders:
                    listing += f"  🆔 <b>{o['id']}</b> — {o['nombre']} | {o['cantidad']}x {o['producto']} | {o['estado']} | {o['fecha']}\n"
                listing += "\n✍️ Escribe el <b>ID</b> del pedido a cancelar:"

                bot.send_message(message.chat.id, listing, reply_markup=types.ReplyKeyboardRemove())
                bot.register_next_step_handler(message, step_cancel_order_id)

            elif "Editar Pedido" in selected:
                conn = get_connection()
                try:
                    orders = conn.execute("""
                        SELECT p.id, c.nombre, p.producto, p.cantidad, p.precio_venta, p.estado, p.fecha
                        FROM pedidos p JOIN clientes c ON p.cliente_id = c.id
                        WHERE p.estado = 'Pendiente'
                        ORDER BY p.id DESC LIMIT 20
                    """).fetchall()
                finally:
                    conn.close()

                if not orders:
                    bot.send_message(message.chat.id, "📦 No hay pedidos pendientes para editar.", reply_markup=types.ReplyKeyboardRemove())
                    return

                listing = "📦 <b>EDITAR PEDIDO</b>\n<i>Solo pedidos pendientes</i>\n\n"
                for o in orders:
                    total = o['cantidad'] * o['precio_venta']
                    listing += f"  🆔 <b>{o['id']}</b> — {o['nombre']} | {o['cantidad']}x {o['producto']} | ${total:,.0f}\n"
                listing += "\n✍️ Escribe el <b>ID</b> del pedido a editar:"

                bot.send_message(message.chat.id, listing, reply_markup=types.ReplyKeyboardRemove())
                bot.register_next_step_handler(message, step_edit_order_id)

            elif "Editar Cliente" in selected:
                bot.send_message(message.chat.id, "✍️ Escribe el <b>ID del cliente</b> a editar:", reply_markup=types.ReplyKeyboardRemove())
                bot.register_next_step_handler(message, step_edit_client_id)

            elif "Cancelar" in selected:
                bot.send_message(message.chat.id, "❌ Cancelado.", reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # ── Cancel Order ──

    def step_cancel_order_id(message):
        if not is_admin(message):
            return
        try:
            order_id = int(message.text.strip())
            conn = get_connection()
            try:
                order = conn.execute("""
                    SELECT p.id, p.producto, p.cantidad, p.precio_venta, p.estado, c.nombre
                    FROM pedidos p JOIN clientes c ON p.cliente_id = c.id
                    WHERE p.id = %s
                """, (order_id,)).fetchone()
            finally:
                conn.close()

            if not order:
                bot.send_message(message.chat.id, f"❌ No existe pedido #{order_id}")
                return

            if order["estado"] == "Cancelado":
                bot.send_message(message.chat.id, f"⚠️ El pedido #{order_id} ya está cancelado.")
                return

            total = order["cantidad"] * order["precio_venta"]
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("✅ Sí, cancelar pedido", "❌ No, mantener")

            bot.send_message(
                message.chat.id,
                f"🚫 <b>¿Cancelar pedido #{order_id}?</b>\n\n"
                f"👤 Cliente: {order['nombre']}\n"
                f"📦 {order['cantidad']}x {order['producto']}\n"
                f"💰 Total: ${total:,.0f}\n"
                f"📌 Estado actual: {order['estado']}\n\n"
                f"⚠️ Se eliminará el registro financiero asociado.",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_cancel_order_execute, order_id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID inválido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_cancel_order_execute(message, order_id):
        if not is_admin(message):
            return
        try:
            if "Sí" in message.text:
                conn = get_connection()
                try:
                    conn.execute("UPDATE pedidos SET estado = 'Cancelado' WHERE id = %s", (order_id,))
                    conn.execute("DELETE FROM finanzas WHERE pedido_id = %s", (order_id,))
                    conn.commit()
                finally:
                    conn.close()
                bot.send_message(message.chat.id, f"✅ Pedido #{order_id} cancelado exitosamente.", reply_markup=types.ReplyKeyboardRemove())
            else:
                bot.send_message(message.chat.id, "❌ Operación cancelada.", reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # ── Edit Order ──

    def step_edit_order_id(message):
        if not is_admin(message):
            return
        try:
            order_id = int(message.text.strip())
            conn = get_connection()
            try:
                order = conn.execute("""
                    SELECT p.*, c.nombre as cliente_nombre
                    FROM pedidos p JOIN clientes c ON p.cliente_id = c.id
                    WHERE p.id = %s AND p.estado = 'Pendiente'
                """, (order_id,)).fetchone()
            finally:
                conn.close()

            if not order:
                bot.send_message(message.chat.id, f"❌ Pedido #{order_id} no encontrado o no está pendiente.")
                return

            total = order["cantidad"] * order["precio_venta"]
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("🔢 Cantidad", "💰 Precio de Venta")
            markup.add("💲 Costo de Compra", "📦 Producto")
            markup.add("❌ Cancelar")

            bot.send_message(
                message.chat.id,
                f"✏️ <b>Editando Pedido #{order_id}</b>\n\n"
                f"👤 Cliente: {order['cliente_nombre']}\n"
                f"📦 Producto: {order['producto']}\n"
                f"🔢 Cantidad: {order['cantidad']}\n"
                f"💲 Costo compra: ${order['costo_compra']:,.0f}\n"
                f"💰 Precio venta: ${order['precio_venta']:,.0f}\n"
                f"💵 Total: ${total:,.0f}\n\n"
                f"¿Qué campo deseas editar?",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_edit_order_field, order_id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID inválido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_edit_order_field(message, order_id):
        if not is_admin(message):
            return
        try:
            selected = message.text.strip()
            if "Cancelar" in selected:
                bot.send_message(message.chat.id, "❌ Cancelado.", reply_markup=types.ReplyKeyboardRemove())
                return

            field_map = {
                "Cantidad": "cantidad",
                "Precio de Venta": "precio_venta",
                "Costo de Compra": "costo_compra",
                "Producto": "producto",
            }

            db_field = None
            for key, val in field_map.items():
                if key in selected:
                    db_field = val
                    break

            if not db_field:
                bot.send_message(message.chat.id, "❌ Campo no válido.", reply_markup=types.ReplyKeyboardRemove())
                return

            if db_field == "producto":
                markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                for p in PRODUCT_CATALOG:
                    markup.add(p)
                bot.send_message(message.chat.id, "📦 Selecciona el nuevo producto:", reply_markup=markup)
            else:
                bot.send_message(message.chat.id, f"✍️ Escribe el nuevo valor para <b>{selected}</b>:", reply_markup=types.ReplyKeyboardRemove())

            bot.register_next_step_handler(message, step_edit_order_value, order_id, db_field)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_edit_order_value(message, order_id, db_field):
        if not is_admin(message):
            return
        try:
            new_value = message.text.strip()

            if db_field == "producto":
                if new_value not in PRODUCT_CATALOG:
                    bot.send_message(message.chat.id, "❌ Producto no válido.", reply_markup=types.ReplyKeyboardRemove())
                    return
                # Also update weight and cargo type
                product_info = PRODUCT_CATALOG[new_value]
                conn = get_connection()
                try:
                    order = conn.execute("SELECT cantidad FROM pedidos WHERE id = %s", (order_id,)).fetchone()
                    new_weight = order["cantidad"] * product_info["weight"]
                    conn.execute(
                        "UPDATE pedidos SET producto = %s, tipo_carga = %s, peso_kg = %s WHERE id = %s",
                        (new_value, product_info["cargo_type"], new_weight, order_id)
                    )
                    conn.commit()
                finally:
                    conn.close()
            elif db_field == "cantidad":
                qty = int(new_value)
                if qty <= 0:
                    bot.send_message(message.chat.id, "❌ Debe ser mayor a 0.")
                    return
                conn = get_connection()
                try:
                    order = conn.execute("SELECT producto FROM pedidos WHERE id = %s", (order_id,)).fetchone()
                    product_info = PRODUCT_CATALOG.get(order["producto"], {"weight": 0})
                    new_weight = qty * product_info.get("weight", 0)
                    conn.execute("UPDATE pedidos SET cantidad = %s, peso_kg = %s WHERE id = %s", (qty, new_weight, order_id))
                    conn.commit()
                finally:
                    conn.close()
            else:
                num_value = float(new_value.replace(",", "."))
                if num_value <= 0:
                    bot.send_message(message.chat.id, "❌ Debe ser mayor a $0.")
                    return
                conn = get_connection()
                try:
                    conn.execute(f"UPDATE pedidos SET {db_field} = %s WHERE id = %s", (num_value, order_id))
                    conn.commit()
                finally:
                    conn.close()

            bot.send_message(
                message.chat.id,
                f"✅ Pedido #{order_id} actualizado.\n<b>{db_field}</b> → {new_value}",
                reply_markup=types.ReplyKeyboardRemove()
            )
        except ValueError:
            bot.send_message(message.chat.id, "❌ Valor inválido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_edit_client_id(message):
        if not is_admin(message):
            return
        try:
            client_id = int(message.text.strip())
            conn = get_connection()
            try:
                client = conn.execute("SELECT * FROM clientes WHERE id = %s", (client_id,)).fetchone()
            finally:
                conn.close()

            if not client:
                bot.send_message(message.chat.id, f"❌ No existe cliente con ID {client_id}")
                return

            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("👤 Nombre", "📱 Teléfono")
            markup.add("📍 Dirección", "🏪 Tipo de Negocio")
            markup.add("❌ Cancelar")

            bot.send_message(
                message.chat.id,
                f"✏️ <b>Editando: {client['nombre']} (ID: {client_id})</b>\n\n"
                f"👤 Nombre: {client['nombre']}\n"
                f"📱 Teléfono: {client['telefono']}\n"
                f"📍 Dirección: {client['direccion']}\n"
                f"🏪 Tipo: {client['tipo_negocio']}\n\n"
                "¿Qué campo deseas editar?",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_edit_client_field, client_id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID inválido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    ALLOWED_EDIT_FIELDS = {"nombre", "telefono", "direccion", "tipo_negocio"}

    def step_edit_client_field(message, client_id):
        if not is_admin(message):
            return
        try:
            selected = message.text.strip()
            if "Cancelar" in selected:
                bot.send_message(message.chat.id, "❌ Cancelado.", reply_markup=types.ReplyKeyboardRemove())
                return

            field_map = {
                "Nombre": "nombre", "Teléfono": "telefono",
                "Dirección": "direccion", "Tipo de Negocio": "tipo_negocio",
            }
            db_field = None
            for label, col in field_map.items():
                if label in selected:
                    db_field = col
                    break

            if not db_field or db_field not in ALLOWED_EDIT_FIELDS:
                bot.send_message(message.chat.id, "❌ Campo no reconocido.", reply_markup=types.ReplyKeyboardRemove())
                return

            bot.send_message(message.chat.id, f"✍️ Escribe el <b>nuevo valor</b> para {selected}:", reply_markup=types.ReplyKeyboardRemove())
            bot.register_next_step_handler(message, step_edit_client_save, client_id, db_field)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_edit_client_save(message, client_id, db_field):
        if not is_admin(message):
            return
        try:
            if db_field not in ALLOWED_EDIT_FIELDS:
                bot.send_message(message.chat.id, "❌ Campo no permitido.")
                return

            new_value = message.text.strip()
            conn = get_connection()
            try:
                conn.execute(
                    f"UPDATE clientes SET {db_field} = %s, ultima_interaccion = %s WHERE id = %s",
                    (new_value, date.today().isoformat(), client_id)
                )
                conn.commit()
            finally:
                conn.close()

            bot.send_message(message.chat.id, f"✅ <b>Cliente ID {client_id} actualizado</b>\n📝 {db_field} → {new_value}")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")
