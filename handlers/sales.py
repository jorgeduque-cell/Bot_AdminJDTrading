# -*- coding: utf-8 -*-
"""
Handlers: Sales & Orders
Commands: /vender, /pedidos, /entregar, /cobrar, /repetir
Note: Stock validation was intentionally removed (business does not manage stock).
"""
from telebot import types
from datetime import date

from config import PRODUCT_CATALOG
from database import get_connection
from utils import is_admin, safe_split, sanitize_phone_co


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
                client = conn.execute("SELECT * FROM clientes WHERE id = %s", (client_id,)).fetchone()
                if not client:
                    bot.send_message(message.chat.id, "❌ Cliente no encontrado. Verifica el ID.")
                    return

                today = date.today().isoformat()
                conn.execute("UPDATE clientes SET estado = 'Activo', ultima_interaccion = %s WHERE id = %s", (today, client_id))
                conn.commit()
            finally:
                conn.close()

            sale_data = {
                "cliente_id": client_id,
                "cliente_nombre": client["nombre"],
                "items": []  # Multi-product list
            }

            bot.send_message(
                message.chat.id,
                f"👤 Cliente: <b>{client['nombre']}</b> (activado ✅)"
            )
            _ask_product(bot, message, sale_data)
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID inválido. Debe ser un número.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # Store sale_data in a chat-level dict for callback access
    _pending_sales = {}

    def _ask_product(bot, message, sale_data):
        """Prompt user to select a product."""
        chat_id = message.chat.id
        _pending_sales[chat_id] = sale_data  # Always store for callbacks

        item_num = len(sale_data["items"]) + 1
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        for p in PRODUCT_CATALOG:
            markup.add(p)

        bot.send_message(
            chat_id,
            f"📦 <b>Producto #{item_num}</b>\nSelecciona el producto:",
            reply_markup=markup
        )
        bot.register_next_step_handler(message, step_sell_product)

    def step_sell_product(message):
        if not is_admin(message):
            return
        try:
            sale_data = _pending_sales.get(message.chat.id)
            if not sale_data:
                bot.send_message(message.chat.id, "⚠️ No hay venta en curso. Usa /vender.")
                return

            product = message.text.strip()
            if product not in PRODUCT_CATALOG:
                bot.send_message(message.chat.id, "❌ Producto no válido.", reply_markup=types.ReplyKeyboardRemove())
                return

            # Fetch current prices from DB
            conn = get_connection()
            try:
                db_price = conn.execute("SELECT precio_compra, precio_venta FROM precios WHERE producto = %s", (product,)).fetchone()
            finally:
                conn.close()

            current_item = {"producto": product, "db_cost": 0, "db_price": 0}
            sale_data["_current_item"] = current_item

            if db_price and db_price["precio_venta"] > 0:
                current_item["db_cost"] = db_price["precio_compra"]
                current_item["db_price"] = db_price["precio_venta"]

                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton(
                        f"✅ Usar: ${db_price['precio_compra']:,.0f} / ${db_price['precio_venta']:,.0f}",
                        callback_data="sell_useprice"
                    ),
                    types.InlineKeyboardButton("💲 Otro precio", callback_data="sell_newprice")
                )
                bot.send_message(
                    message.chat.id,
                    f"📦 <b>{product}</b>\n\n"
                    f"💰 Precio registrado:\n"
                    f"  • Compra: <b>${db_price['precio_compra']:,.0f}</b>\n"
                    f"  • Venta: <b>${db_price['precio_venta']:,.0f}</b>\n\n"
                    f"¿Usar este precio o ingresar uno nuevo?",
                    reply_markup=markup
                )
            else:
                bot.send_message(
                    message.chat.id,
                    f"📦 <b>{product}</b>\n⚠️ No tiene precio registrado.\n\n"
                    f"💲 Escribe el <b>costo de compra unitario</b>:",
                    reply_markup=types.ReplyKeyboardRemove()
                )
                bot.register_next_step_handler(message, step_sell_new_cost)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data == "sell_useprice")
    def handle_use_existing_price(call):
        """User chose to use existing price from DB."""
        try:
            bot.answer_callback_query(call.id)
            chat_id = call.message.chat.id
            sale_data = _pending_sales.get(chat_id)
            if not sale_data:
                bot.send_message(chat_id, "⚠️ No hay venta en curso.")
                return

            call.message.from_user = call.from_user
            bot.send_message(chat_id, "📦 Escribe la <b>cantidad</b> de unidades:")
            bot.register_next_step_handler(call.message, step_sell_quantity)
        except Exception as e:
            bot.answer_callback_query(call.id, f"⚠️ Error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data == "sell_newprice")
    def handle_new_price(call):
        """User chose to enter a new price."""
        try:
            bot.answer_callback_query(call.id)
            chat_id = call.message.chat.id
            sale_data = _pending_sales.get(chat_id)
            if not sale_data:
                bot.send_message(chat_id, "⚠️ No hay venta en curso.")
                return

            call.message.from_user = call.from_user
            bot.send_message(chat_id, "💲 Escribe el <b>nuevo costo de compra unitario</b>:")
            bot.register_next_step_handler(call.message, step_sell_new_cost)
        except Exception as e:
            bot.answer_callback_query(call.id, f"⚠️ Error: {e}")

    def step_sell_new_cost(message):
        if not is_admin(message):
            return
        try:
            sale_data = _pending_sales.get(message.chat.id)
            if not sale_data:
                return

            cost = float(message.text.strip().replace(",", "."))
            if cost <= 0:
                bot.send_message(message.chat.id, "❌ El costo debe ser mayor a $0.")
                return
            sale_data["_current_item"]["db_cost"] = cost
            bot.send_message(message.chat.id, "💰 Escribe el <b>precio de venta unitario</b>:")
            bot.register_next_step_handler(message, step_sell_new_price)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Valor inválido. Ingresa un número.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_sell_new_price(message):
        if not is_admin(message):
            return
        try:
            sale_data = _pending_sales.get(message.chat.id)
            if not sale_data:
                return

            price = float(message.text.strip().replace(",", "."))
            if price <= 0:
                bot.send_message(message.chat.id, "❌ El precio debe ser mayor a $0.")
                return
            sale_data["_current_item"]["db_price"] = price

            # Update the precios table with new price
            product_name = sale_data["_current_item"]["producto"]
            cost = sale_data["_current_item"]["db_cost"]
            today = date.today().isoformat()

            conn = get_connection()
            try:
                conn.execute(
                    "UPDATE precios SET precio_compra = %s, precio_venta = %s, fecha_actualizacion = %s WHERE producto = %s",
                    (cost, price, today, product_name)
                )
                conn.commit()
            finally:
                conn.close()

            bot.send_message(
                message.chat.id,
                f"✅ Precio actualizado: <b>{product_name}</b>\n"
                f"  Compra: ${cost:,.0f} | Venta: ${price:,.0f}\n\n"
                f"📦 Escribe la <b>cantidad</b> de unidades:"
            )
            bot.register_next_step_handler(message, step_sell_quantity)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Valor inválido. Ingresa un número.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_sell_quantity(message):
        if not is_admin(message):
            return
        try:
            sale_data = _pending_sales.get(message.chat.id)
            if not sale_data:
                return

            quantity = int(message.text.strip())
            if quantity <= 0:
                bot.send_message(message.chat.id, "❌ La cantidad debe ser mayor a 0.")
                return
            if quantity > 10000:
                bot.send_message(message.chat.id, "❌ Cantidad demasiado alta (máx 10,000).")
                return

            item = sale_data["_current_item"]
            item["cantidad"] = quantity
            product_info = PRODUCT_CATALOG[item["producto"]]
            item["peso_kg"] = quantity * product_info["weight"]
            item["tipo_carga"] = product_info["cargo_type"]
            item["costo_compra"] = item["db_cost"]
            item["precio_venta"] = item["db_price"]

            sale_data["items"].append(item)
            sale_data.pop("_current_item", None)

            # Show current cart and ask if add more
            cart_text = _build_cart_summary(sale_data)
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("➕ Agregar otro producto", callback_data="cart_add"),
                types.InlineKeyboardButton("✅ Finalizar pedido", callback_data="cart_done"),
            )

            bot.send_message(message.chat.id, cart_text, reply_markup=markup)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Cantidad inválida. Debe ser un número entero.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def _build_cart_summary(sale_data):
        """Build a text summary of all items in the cart."""
        text = f"🛒 <b>CARRITO — {sale_data['cliente_nombre']}</b>\n"
        text += "━" * 30 + "\n"
        grand_total = 0
        for i, item in enumerate(sale_data["items"], 1):
            subtotal = item["cantidad"] * item["precio_venta"]
            grand_total += subtotal
            text += f"\n📦 <b>{i}.</b> {item['producto']}\n"
            text += f"   {item['cantidad']} uds × ${item['precio_venta']:,.0f} = <b>${subtotal:,.0f}</b>\n"
        text += "\n" + "━" * 30 + "\n"
        text += f"💰 <b>TOTAL: ${grand_total:,.0f}</b>"
        return text

    @bot.callback_query_handler(func=lambda call: call.data in ("cart_add", "cart_done"))
    def handle_cart_action(call):
        """Handle cart actions — add more products or finalize."""
        try:
            bot.answer_callback_query(call.id)
            chat_id = call.message.chat.id
            call.message.from_user = call.from_user

            sale_data = _pending_sales.get(chat_id)
            if not sale_data:
                bot.send_message(chat_id, "⚠️ No hay venta en curso. Usa /vender para iniciar.")
                return

            if call.data == "cart_add":
                _ask_product(bot, call.message, sale_data)
            elif call.data == "cart_done":
                _finalize_sale(bot, call.message, sale_data)
                _pending_sales.pop(chat_id, None)
        except Exception as e:
            bot.answer_callback_query(call.id, f"⚠️ Error: {e}")

    def _finalize_sale(bot, message, sale_data):
        """Create all orders in the database."""
        try:
            today = date.today().isoformat()
            order_ids = []

            conn = get_connection()
            try:
                for item in sale_data["items"]:
                    cursor = conn.execute(
                        """INSERT INTO pedidos (cliente_id, producto, tipo_carga, cantidad, peso_kg, costo_compra, precio_venta, estado, fecha)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pendiente', %s) RETURNING id""",
                        (sale_data["cliente_id"], item["producto"], item["tipo_carga"],
                         item["cantidad"], item["peso_kg"], item["costo_compra"],
                         item["precio_venta"], today)
                    )
                    order_ids.append(cursor.fetchone()["id"])
                conn.commit()
            finally:
                conn.close()

            # Build confirmation
            text = f"✅ <b>PEDIDO CREADO</b>\n"
            text += "━" * 30 + "\n"
            text += f"👤 Cliente: {sale_data['cliente_nombre']}\n"
            text += f"📋 Pedidos: {', '.join(f'#{oid}' for oid in order_ids)}\n\n"

            grand_total = 0
            grand_weight = 0
            for i, item in enumerate(sale_data["items"]):
                subtotal = item["cantidad"] * item["precio_venta"]
                grand_total += subtotal
                grand_weight += item["peso_kg"]
                text += f"📦 <b>{item['producto']}</b>\n"
                text += f"   {item['cantidad']} uds × ${item['precio_venta']:,.0f} = ${subtotal:,.0f}\n"
                text += f"   ⚖️ {item['peso_kg']:.1f} kg | Costo: ${item['costo_compra']:,.0f}/u\n\n"

            text += "━" * 30 + "\n"
            text += f"💵 <b>Total: ${grand_total:,.0f}</b>\n"
            text += f"⚖️ Peso total: {grand_weight:.1f} kg\n"
            text += f"📌 Estado: Pendiente"

            # Post-sale action buttons
            markup = types.InlineKeyboardMarkup(row_width=1)
            for oid in order_ids:
                markup.add(types.InlineKeyboardButton(f"📄 Remisión Pedido #{oid}", callback_data=f"qrem_{oid}_{sale_data['cliente_id']}"))

            bot.send_message(message.chat.id, text, reply_markup=markup)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error al crear pedido: {e}")

    # ── Quick Remision from sale ──

    @bot.callback_query_handler(func=lambda call: call.data.startswith("qrem_"))
    def handle_quick_remision(call):
        """Generate remision PDF directly after sale — then offer WhatsApp."""
        try:
            bot.answer_callback_query(call.id, "⏳ Generando remisión...")
            parts = call.data.split("_")
            order_id = int(parts[1])
            client_id = int(parts[2])

            conn = get_connection()
            try:
                order = conn.execute("""
                    SELECT p.*, c.nombre as cliente_nombre, c.direccion as cliente_dir,
                           c.telefono as cliente_tel
                    FROM pedidos p JOIN clientes c ON p.cliente_id = c.id
                    WHERE p.id = %s
                """, (order_id,)).fetchone()
            finally:
                conn.close()

            if not order:
                bot.send_message(call.message.chat.id, f"❌ Pedido #{order_id} no encontrado.")
                return

            # Trigger remision generation via command simulation
            call.message.from_user = call.from_user
            call.message.text = f"/remision {order_id}"
            bot.process_new_messages([call.message])

            # After remision, offer WhatsApp button
            phone = sanitize_phone_co(order["cliente_tel"]) if order["cliente_tel"] else None
            if phone:
                total = order["cantidad"] * order["precio_venta"]
                wa_msg = (
                    f"Buenos días {order['cliente_nombre']}, "
                    f"le envío la remisión de su pedido #{order_id} "
                    f"por ${total:,.0f}. "
                    f"¡Gracias por su compra! — JD Trading Oil S.A.S"
                )
                import urllib.parse
                wa_url = f"https://wa.me/{phone}?text={urllib.parse.quote(wa_msg)}"

                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("📲 Enviar por WhatsApp", url=wa_url))

                bot.send_message(
                    call.message.chat.id,
                    f"📲 <b>Enviar remisión a {order['cliente_nombre']}</b>\n\n"
                    f"1️⃣ Abre WhatsApp con el botón\n"
                    f"2️⃣ Reenvía el PDF que acabas de recibir",
                    reply_markup=markup
                )
        except Exception as e:
            bot.send_message(call.message.chat.id, f"⚠️ Error: {e}")

    # --------------- /pedidos ---------------

    @bot.message_handler(commands=["pedidos"])
    def cmd_orders(message):
        if not is_admin(message):
            return
        try:
            markup = types.InlineKeyboardMarkup(row_width=3)
            markup.row(
                types.InlineKeyboardButton("⏳ Pendientes", callback_data="orders_filter:Pendiente"),
                types.InlineKeyboardButton("✅ Entregados", callback_data="orders_filter:Entregado"),
                types.InlineKeyboardButton("📋 Todos", callback_data="orders_filter:Todos"),
            )
            bot.send_message(message.chat.id, "📦 <b>PEDIDOS</b>\n\n¿Qué filtro aplicar?", reply_markup=markup)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("orders_filter:"))
    def handle_orders_filter(call):
        """Handle order filter inline buttons."""
        try:
            bot.answer_callback_query(call.id)
            filter_type = call.data.replace("orders_filter:", "")

            conn = get_connection()
            try:
                if filter_type == "Todos":
                    orders = conn.execute("""
                        SELECT p.*, c.nombre as cliente_nombre FROM pedidos p
                        JOIN clientes c ON p.cliente_id = c.id ORDER BY p.fecha DESC
                    """).fetchall()
                    label = "TODOS"
                else:
                    orders = conn.execute("""
                        SELECT p.*, c.nombre as cliente_nombre FROM pedidos p
                        JOIN clientes c ON p.cliente_id = c.id WHERE p.estado = %s ORDER BY p.fecha DESC
                    """, (filter_type,)).fetchall()
                    label = filter_type.upper() + "S"
            finally:
                conn.close()

            if not orders:
                bot.send_message(call.message.chat.id, f"📭 No hay pedidos ({label}).")
                return

            response = f"📦 <b>PEDIDOS — {label}</b> ({len(orders)}):\n\n"
            markup = types.InlineKeyboardMarkup(row_width=2)

            for o in orders:
                total = o["cantidad"] * o["precio_venta"]
                state_icon = "⏳" if o["estado"] == "Pendiente" else "✅"
                pay_icon = ""
                if o["estado"] == "Entregado":
                    try:
                        pay_icon = " 🟢" if o["estado_pago"] == "Pagado" else " 🔴"
                    except (IndexError, KeyError):
                        pay_icon = " 🔴"
                response += f"{state_icon} <b>#{o['id']}</b> — {o['cliente_nombre']}\n"
                response += f"   📦 {o['cantidad']}x {o['producto']}\n"
                response += f"   💰 ${total:,.0f} | {o['estado']}{pay_icon}\n\n"

                # Action buttons for pending orders
                if o["estado"] == "Pendiente":
                    markup.add(
                        types.InlineKeyboardButton(f"✅ Entregar #{o['id']}", callback_data=f"deliver:{o['id']}")
                    )

            if len(response) > 4000:
                for part in safe_split(response):
                    bot.send_message(call.message.chat.id, part)
                bot.send_message(call.message.chat.id, "👇 Acciones:", reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, response, reply_markup=markup)
        except Exception as e:
            bot.send_message(call.message.chat.id, f"⚠️ Error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("deliver:"))
    def handle_deliver_callback(call):
        """Handle inline deliver button."""
        try:
            bot.answer_callback_query(call.id)
            order_id = call.data.replace("deliver:", "")
            call.message.from_user = call.from_user
            call.message.text = f"/entregar {order_id}"
            bot.process_new_messages([call.message])
        except Exception as e:
            bot.answer_callback_query(call.id, f"⚠️ Error: {e}")

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
                order = conn.execute("SELECT * FROM pedidos WHERE id = %s", (order_id,)).fetchone()

                if not order:
                    bot.send_message(message.chat.id, "❌ Pedido no encontrado.")
                    return

                if order["estado"] == "Entregado":
                    bot.send_message(message.chat.id, "ℹ️ Este pedido ya fue entregado anteriormente.")
                    return

                today = date.today().isoformat()
                income = order["cantidad"] * order["precio_venta"]

                conn.execute("UPDATE pedidos SET estado = 'Entregado' WHERE id = %s", (order_id,))
                conn.execute(
                    "INSERT INTO finanzas (tipo, concepto, monto, fecha, pedido_id) VALUES ('Ingreso', %s, %s, %s, %s)",
                    (f"Venta pedido #{order_id} — {order['producto']}", income, today, order_id)
                )

                # Auto-deduct from inventory
                try:
                    conn.execute(
                        "UPDATE inventario SET stock_actual = GREATEST(0, stock_actual - %s), ultima_actualizacion = %s WHERE producto = %s",
                        (order["cantidad"], today, order["producto"])
                    )
                except Exception:
                    pass

                conn.execute("UPDATE clientes SET ultima_interaccion = %s WHERE id = %s", (today, order["cliente_id"]))
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

    # --------------- /cobrar ---------------

    @bot.message_handler(commands=["cobrar"])
    def cmd_collect(message):
        if not is_admin(message):
            return
        try:
            conn = get_connection()
            try:
                unpaid = conn.execute("""
                    SELECT p.id, p.producto, p.cantidad, p.precio_venta, p.fecha,
                           c.nombre, c.telefono,
                           (p.cantidad * p.precio_venta) as total
                    FROM pedidos p JOIN clientes c ON p.cliente_id = c.id
                    WHERE p.estado = 'Entregado' AND (p.estado_pago IS NULL OR p.estado_pago = 'Pendiente')
                    ORDER BY p.fecha ASC
                """).fetchall()
            finally:
                conn.close()

            if not unpaid:
                bot.send_message(message.chat.id, "✅ ¡No hay cobros pendientes! Todos tus clientes están al día.")
                return

            total_pending = sum(row["total"] for row in unpaid)

            response = f"💳 <b>COBROS PENDIENTES</b>\n"
            response += "━" * 30 + "\n"
            response += f"💰 Total por cobrar: <b>${total_pending:,.0f}</b>\n"
            response += f"📦 Pedidos sin pagar: <b>{len(unpaid)}</b>\n\n"

            markup = types.InlineKeyboardMarkup(row_width=2)

            for row in unpaid:
                phone = sanitize_phone_co(row["telefono"])
                dt = row["fecha"]
                if isinstance(dt, str):
                    dt = date.fromisoformat(dt)
                days_ago = (date.today() - dt).days
                urgency = "🔴" if days_ago > 7 else ("🟡" if days_ago > 3 else "🟢")

                wa_msg = f"Buenos días {row['nombre']}, le recuerdo que tiene pendiente el pedido #{row['id']} por ${row['total']:,.0f} ({row['cantidad']}x {row['producto']}). ¿Cuándo podemos coordinar el pago?"
                wa_url = f"https://wa.me/{phone}?text={wa_msg.replace(' ', '%20').replace('#', '%23')}"

                response += f"{urgency} <b>#{row['id']}</b> — {row['nombre']}\n"
                response += f"   📦 {row['cantidad']}x {row['producto']} | ${row['total']:,.0f}\n"
                response += f"   📅 {row['fecha']} ({days_ago} días)\n\n"

                # Two buttons per order: WhatsApp + Mark Paid
                markup.row(
                    types.InlineKeyboardButton(f"📲 Cobrar #{row['id']}", url=wa_url),
                    types.InlineKeyboardButton(f"✅ Pagado #{row['id']}", callback_data=f"pay:{row['id']}"),
                )

            bot.send_message(message.chat.id, response, reply_markup=markup, disable_web_page_preview=True)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- PAY INLINE CALLBACK ---------------

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pay:"))
    def handle_pay_callback(call):
        """Handle inline pay button."""
        try:
            order_id = int(call.data.replace("pay:", ""))
            conn = get_connection()
            try:
                order = conn.execute("""
                    SELECT p.*, c.nombre FROM pedidos p JOIN clientes c ON p.cliente_id = c.id WHERE p.id = %s
                """, (order_id,)).fetchone()

                if not order:
                    bot.answer_callback_query(call.id, "❌ Pedido no encontrado.")
                    return

                if order["estado_pago"] == "Pagado":
                    bot.answer_callback_query(call.id, "ℹ️ Ya está pagado.")
                    return

                conn.execute("UPDATE pedidos SET estado_pago = 'Pagado' WHERE id = %s", (order_id,))
                conn.commit()
            finally:
                conn.close()

            total = order["cantidad"] * order["precio_venta"]
            bot.answer_callback_query(call.id, f"✅ Pedido #{order_id} marcado como PAGADO")
            bot.send_message(
                call.message.chat.id,
                f"✅ <b>Pago registrado</b>\n\n"
                f"📦 Pedido #{order_id} — {order['nombre']}\n"
                f"💰 ${total:,.0f} — <b>PAGADO ✅</b>"
            )
        except Exception as e:
            bot.answer_callback_query(call.id, f"⚠️ Error: {e}")

    # --------------- /pagar ---------------

    @bot.message_handler(commands=["pagar"])
    def cmd_pay(message):
        if not is_admin(message):
            return
        try:
            parts = message.text.strip().split()
            if len(parts) < 2:
                bot.send_message(message.chat.id, "❌ Uso: /pagar [ID_Pedido]")
                return

            order_id = int(parts[1])
            conn = get_connection()
            try:
                order = conn.execute("""
                    SELECT p.*, c.nombre FROM pedidos p JOIN clientes c ON p.cliente_id = c.id WHERE p.id = %s
                """, (order_id,)).fetchone()

                if not order:
                    bot.send_message(message.chat.id, "❌ Pedido no encontrado.")
                    return

                if order["estado_pago"] == "Pagado":
                    bot.send_message(message.chat.id, "ℹ️ Este pedido ya está marcado como pagado.")
                    return

                conn.execute("UPDATE pedidos SET estado_pago = 'Pagado' WHERE id = %s", (order_id,))
                conn.commit()
            finally:
                conn.close()

            total = order["cantidad"] * order["precio_venta"]
            bot.send_message(
                message.chat.id,
                f"✅ <b>Pago registrado</b>\n\n"
                f"📦 Pedido #{order_id} — {order['nombre']}\n"
                f"💰 ${total:,.0f} — <b>PAGADO ✅</b>"
            )
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID inválido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /repetir ---------------

    @bot.message_handler(commands=["repetir"])
    def cmd_repeat(message):
        if not is_admin(message):
            return
        try:
            parts = message.text.strip().split()
            if len(parts) < 2:
                bot.send_message(message.chat.id, "❌ Uso: /repetir [ID_Cliente]")
                return

            client_id = int(parts[1])
            conn = get_connection()
            try:
                client = conn.execute("SELECT nombre FROM clientes WHERE id = %s", (client_id,)).fetchone()
                if not client:
                    bot.send_message(message.chat.id, "❌ Cliente no encontrado.")
                    return

                last_order = conn.execute("""
                    SELECT producto, cantidad, costo_compra, precio_venta, tipo_carga, peso_kg
                    FROM pedidos WHERE cliente_id = %s ORDER BY id DESC LIMIT 1
                """, (client_id,)).fetchone()
            finally:
                conn.close()

            if not last_order:
                bot.send_message(message.chat.id, f"❌ {client['nombre']} no tiene pedidos anteriores.")
                return

            total = last_order["cantidad"] * last_order["precio_venta"]

            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("✅ Sí, repetir pedido", "❌ No, cancelar")

            bot.send_message(
                message.chat.id,
                f"🔄 <b>REPETIR ÚLTIMO PEDIDO</b>\n\n"
                f"👤 Cliente: <b>{client['nombre']}</b>\n"
                f"📦 {last_order['cantidad']}x {last_order['producto']}\n"
                f"💲 Costo: ${last_order['costo_compra']:,.0f} c/u\n"
                f"💰 Venta: ${last_order['precio_venta']:,.0f} c/u\n"
                f"💵 Total: <b>${total:,.0f}</b>\n\n"
                "¿Confirmar?",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_repeat_confirm, client_id, client["nombre"], last_order)
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID inválido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_repeat_confirm(message, client_id, client_name, last_order):
        if not is_admin(message):
            return
        try:
            if "Sí" not in message.text:
                bot.send_message(message.chat.id, "❌ Cancelado.", reply_markup=types.ReplyKeyboardRemove())
                return

            today = date.today().isoformat()
            conn = get_connection()
            try:
                cursor = conn.execute(
                    """INSERT INTO pedidos (cliente_id, producto, tipo_carga, cantidad, peso_kg, costo_compra, precio_venta, estado, fecha)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pendiente', %s) RETURNING id""",
                    (client_id, last_order["producto"], last_order["tipo_carga"],
                     last_order["cantidad"], last_order["peso_kg"],
                     last_order["costo_compra"], last_order["precio_venta"], today)
                )
                conn.execute("UPDATE clientes SET estado = 'Activo', ultima_interaccion = %s WHERE id = %s", (today, client_id))
                conn.commit()
                order_id = cursor.fetchone()["id"] if cursor.description else 0
            finally:
                conn.close()

            total = last_order["cantidad"] * last_order["precio_venta"]
            bot.send_message(
                message.chat.id,
                f"✅ <b>Pedido #{order_id} creado (recompra)</b>\n\n"
                f"👤 {client_name}\n"
                f"📦 {last_order['cantidad']}x {last_order['producto']}\n"
                f"💵 Total: <b>${total:,.0f}</b>",
                reply_markup=types.ReplyKeyboardRemove()
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")
