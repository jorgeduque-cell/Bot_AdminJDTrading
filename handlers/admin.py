# -*- coding: utf-8 -*-
"""
Handlers: Admin & Dashboard
Commands: /start, /cancelar, /eliminar, /editar, /backup
"""
from telebot import types
from datetime import date, datetime
import os

from config import COMPANY_NAME
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
            markup.add("❌ Cancelar")

            bot.send_message(message.chat.id, "✏️ <b>EDITAR REGISTRO</b>\n\n¿Qué deseas editar?", reply_markup=markup)
            bot.register_next_step_handler(message, step_edit_type)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_edit_type(message):
        if not is_admin(message):
            return
        try:
            if "Cancelar" in message.text:
                bot.send_message(message.chat.id, "❌ Cancelado.", reply_markup=types.ReplyKeyboardRemove())
                return

            bot.send_message(message.chat.id, "✍️ Escribe el <b>ID del cliente</b> a editar:", reply_markup=types.ReplyKeyboardRemove())
            bot.register_next_step_handler(message, step_edit_client_id)
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
