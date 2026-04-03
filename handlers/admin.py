# -*- coding: utf-8 -*-
"""
Handlers: Admin & Dashboard
Commands: /start, /cancelar, /eliminar, /editar, /backup
"""
from telebot import types
from datetime import date, datetime
import os

from config import COMPANY_NAME
from database import get_connection, DB_PATH
from utils import is_admin, safe_split


def register(bot):

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
                today = date.today().isoformat()
                today_sales = conn.execute(
                    "SELECT COALESCE(SUM(cantidad * precio_venta), 0) as t FROM pedidos WHERE fecha = ?", (today,)
                ).fetchone()["t"]
                low_stock = conn.execute(
                    "SELECT producto, stock_actual, stock_minimo FROM inventario WHERE stock_actual <= stock_minimo"
                ).fetchall()
            finally:
                conn.close()

            dashboard = "🏢 <b>JD TRADING OIL S.A.S</b>\n"
            dashboard += f"📅 {date.today().strftime('%d/%m/%Y')}\n"
            dashboard += "━" * 32 + "\n\n"

            dashboard += "📊 <b>PANEL RÁPIDO:</b>\n"
            dashboard += f"  👥 Clientes: {total_clients} (Activos: {active_clients} | Prospectos: {prospects})\n"
            dashboard += f"  📦 Pedidos pendientes: <b>{pending_orders}</b>\n"
            dashboard += f"  💰 Ventas hoy: <b>${today_sales:,.0f}</b>\n"

            if low_stock:
                dashboard += "\n⚠️ <b>ALERTAS DE STOCK:</b>\n"
                for item in low_stock:
                    dashboard += f"  🟡 {item['producto']}: {item['stock_actual']} uds (mín: {item['stock_minimo']})\n"

            dashboard += "\n📋 <b>COMANDOS:</b>\n"
            dashboard += "\n<b>CRM:</b>\n"
            dashboard += "  /nuevo_cliente — Registrar cliente\n"
            dashboard += "  /clientes — Ver cartera\n"
            dashboard += "  /buscar — Buscar cliente\n"
            dashboard += "  /radar — Inteligencia comercial\n"
            dashboard += "\n<b>VENTAS:</b>\n"
            dashboard += "  /vender — Crear pedido\n"
            dashboard += "  /pedidos — Ver pedidos\n"
            dashboard += "  /entregar [ID] — Marcar entregado\n"
            dashboard += "\n<b>LOGÍSTICA:</b>\n"
            dashboard += "  /ruta_pie — Radar de prospección\n"
            dashboard += "  /ruta_camion — Ruta de entregas\n"
            dashboard += "  /inventario — Control de stock\n"
            dashboard += "\n<b>DOCUMENTOS:</b>\n"
            dashboard += "  /remision — Remisión PDF\n"
            dashboard += "  /despacho_jd — Despacho formal\n"
            dashboard += "\n<b>FINANZAS:</b>\n"
            dashboard += "  /gasto — Registrar gasto\n"
            dashboard += "  /caja — Estado de resultados\n"
            dashboard += "\n<b>ADMIN:</b>\n"
            dashboard += "  /editar — Editar registros\n"
            dashboard += "  /eliminar — Eliminar registros\n"
            dashboard += "  /backup — Respaldar BD\n"
            dashboard += "  /cancelar — Abortar acción\n"

            bot.send_message(message.chat.id, dashboard)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

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
            with open(DB_PATH, "rb") as db_file:
                bot.send_document(
                    message.chat.id,
                    db_file,
                    visible_file_name=f"jd_trading_backup_{date.today().isoformat()}.db",
                    caption=f"💾 Respaldo de BD — {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
                            f"Tamaño: {os.path.getsize(DB_PATH) / 1024:.1f} KB"
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
                client = conn.execute("SELECT nombre FROM clientes WHERE id = ?", (record_id,)).fetchone()
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
                    conn.execute("DELETE FROM finanzas WHERE pedido_id IN (SELECT id FROM pedidos WHERE cliente_id = ?)", (record_id,))
                    conn.execute("DELETE FROM pedidos WHERE cliente_id = ?", (record_id,))
                    conn.execute("DELETE FROM clientes WHERE id = ?", (record_id,))
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
                    WHERE p.id = ?
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
                    conn.execute("DELETE FROM finanzas WHERE pedido_id = ?", (record_id,))
                    conn.execute("DELETE FROM pedidos WHERE id = ?", (record_id,))
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
                record = conn.execute("SELECT tipo, concepto, monto FROM finanzas WHERE id = ?", (record_id,)).fetchone()
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
                    conn.execute("DELETE FROM finanzas WHERE id = ?", (record_id,))
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
                client = conn.execute("SELECT * FROM clientes WHERE id = ?", (client_id,)).fetchone()
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
                    f"UPDATE clientes SET {db_field} = ?, ultima_interaccion = ? WHERE id = ?",
                    (new_value, date.today().isoformat(), client_id)
                )
                conn.commit()
            finally:
                conn.close()

            bot.send_message(message.chat.id, f"✅ <b>Cliente ID {client_id} actualizado</b>\n📝 {db_field} → {new_value}")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")
