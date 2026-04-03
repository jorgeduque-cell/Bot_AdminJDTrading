# -*- coding: utf-8 -*-
"""
Handlers: Sales & Orders
Commands: /vender, /pedidos, /entregar
Note: Stock validation was intentionally removed (business does not manage stock).
"""
from telebot import types
from datetime import date

from config import PRODUCT_CATALOG
from database import get_connection
from utils import is_admin, safe_split


def register(bot):

    # --------------- /vender ---------------

    @bot.message_handler(commands=["vender"])
    def cmd_sell(message):
        if not is_admin(message):
            return
        try:
            bot.send_message(message.chat.id, "🛒 <b>Nueva Venta</b>\n\nEscribe el <b>ID del cliente</b>:")
            bot.register_next_step_handler(message, step_sell_client_id)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_sell_client_id(message):
        if not is_admin(message):
            return
        try:
            client_id = int(message.text.strip())
            conn = get_connection()
            try:
                client = conn.execute("SELECT * FROM clientes WHERE id = ?", (client_id,)).fetchone()
                if not client:
                    bot.send_message(message.chat.id, "❌ Cliente no encontrado. Verifica el ID.")
                    return

                today = date.today().isoformat()
                conn.execute("UPDATE clientes SET estado = 'Activo', ultima_interaccion = ? WHERE id = ?", (today, client_id))
                conn.commit()
            finally:
                conn.close()

            sale_data = {"cliente_id": client_id, "cliente_nombre": client["nombre"]}

            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("Caja Oleosoberano", "Bidon 18L", "Bidon 20L")

            bot.send_message(
                message.chat.id,
                f"👤 Cliente: <b>{client['nombre']}</b> (activado ✅)\n\nSelecciona el <b>producto</b>:",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_sell_product, sale_data)
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID inválido. Debe ser un número.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_sell_product(message, sale_data):
        if not is_admin(message):
            return
        try:
            product = message.text.strip()
            if product not in PRODUCT_CATALOG:
                bot.send_message(message.chat.id, "❌ Producto no válido. Usa: Caja Oleosoberano, Bidon 18L o Bidon 20L.")
                return

            sale_data["producto"] = product
            bot.send_message(message.chat.id, "📦 Escribe la <b>cantidad</b> de unidades:", reply_markup=types.ReplyKeyboardRemove())
            bot.register_next_step_handler(message, step_sell_quantity, sale_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_sell_quantity(message, sale_data):
        if not is_admin(message):
            return
        try:
            quantity = int(message.text.strip())
            if quantity <= 0:
                bot.send_message(message.chat.id, "❌ La cantidad debe ser mayor a 0.")
                return
            if quantity > 10000:
                bot.send_message(message.chat.id, "❌ Cantidad demasiado alta (máx 10,000). Verifica el dato.")
                return
            sale_data["cantidad"] = quantity

            bot.send_message(message.chat.id, "💲 Escribe el <b>costo de compra unitario</b> de HOY (tu costo):")
            bot.register_next_step_handler(message, step_sell_cost, sale_data)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Cantidad inválida. Debe ser un número entero.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_sell_cost(message, sale_data):
        if not is_admin(message):
            return
        try:
            cost = float(message.text.strip().replace(",", "."))
            if cost <= 0:
                bot.send_message(message.chat.id, "❌ El costo debe ser mayor a $0.")
                return
            sale_data["costo_compra"] = cost
            bot.send_message(message.chat.id, "💰 Escribe el <b>precio de venta unitario</b> de HOY:")
            bot.register_next_step_handler(message, step_sell_price, sale_data)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Valor inválido. Ingresa un número.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_sell_price(message, sale_data):
        if not is_admin(message):
            return
        try:
            price = float(message.text.strip().replace(",", "."))
            if price <= 0:
                bot.send_message(message.chat.id, "❌ El precio debe ser mayor a $0.")
                return
            sale_data["precio_venta"] = price

            product_info = PRODUCT_CATALOG[sale_data["producto"]]
            total_weight = sale_data["cantidad"] * product_info["weight"]
            cargo_type = product_info["cargo_type"]
            total_sale = sale_data["cantidad"] * price
            today = date.today().isoformat()

            conn = get_connection()
            try:
                cursor = conn.execute(
                    """INSERT INTO pedidos (cliente_id, producto, tipo_carga, cantidad, peso_kg, costo_compra, precio_venta, estado, fecha)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendiente', ?)""",
                    (sale_data["cliente_id"], sale_data["producto"], cargo_type,
                     sale_data["cantidad"], total_weight, sale_data["costo_compra"],
                     price, today)
                )
                conn.commit()
                order_id = cursor.lastrowid
            finally:
                conn.close()

            bot.send_message(
                message.chat.id,
                f"✅ <b>Pedido #{order_id} Creado</b>\n\n"
                f"👤 Cliente: {sale_data['cliente_nombre']}\n"
                f"📦 Producto: {sale_data['producto']}\n"
                f"🔢 Cantidad: {sale_data['cantidad']}\n"
                f"⚖️ Peso total: {total_weight:.1f} kg ({cargo_type})\n"
                f"💲 Costo compra: ${sale_data['costo_compra']:,.0f} c/u\n"
                f"💰 Precio venta: ${price:,.0f} c/u\n"
                f"💵 Total venta: <b>${total_sale:,.0f}</b>\n"
                f"📌 Estado: Pendiente"
            )
        except ValueError:
            bot.send_message(message.chat.id, "❌ Valor inválido. Ingresa un número.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /pedidos ---------------

    @bot.message_handler(commands=["pedidos"])
    def cmd_orders(message):
        if not is_admin(message):
            return
        try:
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("⏳ Pendientes", "✅ Entregados", "📋 Todos")
            markup.add("❌ Cancelar")
            bot.send_message(message.chat.id, "📦 <b>PEDIDOS</b>\n\n¿Qué filtro aplicar?", reply_markup=markup)
            bot.register_next_step_handler(message, step_orders_filter)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_orders_filter(message):
        if not is_admin(message):
            return
        try:
            selected = message.text.strip()
            if "Cancelar" in selected:
                bot.send_message(message.chat.id, "❌ Cancelado.", reply_markup=types.ReplyKeyboardRemove())
                return

            conn = get_connection()
            try:
                if "Pendientes" in selected:
                    orders = conn.execute("""
                        SELECT p.*, c.nombre as cliente_nombre FROM pedidos p
                        JOIN clientes c ON p.cliente_id = c.id WHERE p.estado = 'Pendiente' ORDER BY p.fecha DESC
                    """).fetchall()
                    label = "PENDIENTES"
                elif "Entregados" in selected:
                    orders = conn.execute("""
                        SELECT p.*, c.nombre as cliente_nombre FROM pedidos p
                        JOIN clientes c ON p.cliente_id = c.id WHERE p.estado = 'Entregado' ORDER BY p.fecha DESC
                    """).fetchall()
                    label = "ENTREGADOS"
                else:
                    orders = conn.execute("""
                        SELECT p.*, c.nombre as cliente_nombre FROM pedidos p
                        JOIN clientes c ON p.cliente_id = c.id ORDER BY p.fecha DESC
                    """).fetchall()
                    label = "TODOS"
            finally:
                conn.close()

            if not orders:
                bot.send_message(message.chat.id, f"📭 No hay pedidos ({label}).", reply_markup=types.ReplyKeyboardRemove())
                return

            response = f"📦 <b>PEDIDOS — {label}</b> ({len(orders)}):\n\n"
            for o in orders:
                total = o["cantidad"] * o["precio_venta"]
                state_icon = "⏳" if o["estado"] == "Pendiente" else "✅"
                response += f"{state_icon} <b>#{o['id']}</b> — {o['cliente_nombre']}\n"
                response += f"   📦 {o['cantidad']}x {o['producto']} ({o['tipo_carga']})\n"
                response += f"   💰 ${total:,.0f} (${o['precio_venta']:,.0f} c/u)\n"
                response += f"   📅 {o['fecha']} | {o['estado']}\n\n"

            if len(response) > 4000:
                for part in safe_split(response):
                    bot.send_message(message.chat.id, part, reply_markup=types.ReplyKeyboardRemove())
            else:
                bot.send_message(message.chat.id, response, reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /entregar ---------------

    @bot.message_handler(commands=["entregar"])
    def cmd_deliver(message):
        if not is_admin(message):
            return
        try:
            parts = message.text.strip().split()
            if len(parts) < 2:
                bot.send_message(message.chat.id, "❌ Uso: /entregar [ID_Pedido]")
                return

            order_id = int(parts[1])
            conn = get_connection()
            try:
                order = conn.execute("SELECT * FROM pedidos WHERE id = ?", (order_id,)).fetchone()

                if not order:
                    bot.send_message(message.chat.id, "❌ Pedido no encontrado.")
                    return

                if order["estado"] == "Entregado":
                    bot.send_message(message.chat.id, "ℹ️ Este pedido ya fue entregado anteriormente.")
                    return

                today = date.today().isoformat()
                income = order["cantidad"] * order["precio_venta"]

                conn.execute("UPDATE pedidos SET estado = 'Entregado' WHERE id = ?", (order_id,))
                conn.execute(
                    "INSERT INTO finanzas (tipo, concepto, monto, fecha, pedido_id) VALUES ('Ingreso', ?, ?, ?, ?)",
                    (f"Venta pedido #{order_id} — {order['producto']}", income, today, order_id)
                )

                # Auto-deduct from inventory
                try:
                    conn.execute(
                        "UPDATE inventario SET stock_actual = MAX(0, stock_actual - ?), ultima_actualizacion = ? WHERE producto = ?",
                        (order["cantidad"], today, order["producto"])
                    )
                except Exception:
                    pass

                conn.execute("UPDATE clientes SET ultima_interaccion = ? WHERE id = ?", (today, order["cliente_id"]))
                conn.commit()
            finally:
                conn.close()

            bot.send_message(
                message.chat.id,
                f"✅ <b>Pedido #{order_id} ENTREGADO</b>\n\n"
                f"📦 {order['producto']} x{order['cantidad']}\n"
                f"💰 Ingreso registrado: <b>${income:,.0f}</b>"
            )
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID inválido. Uso: /entregar [ID_Pedido]")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")
