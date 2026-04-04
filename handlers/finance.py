# -*- coding: utf-8 -*-
"""
Handlers: Finance
Commands: /gasto, /caja, /cuentas_por_cobrar, /margen, /meta
"""
from telebot import types
from datetime import date, timedelta

from config import PRODUCT_CATALOG
from database import get_connection
from utils import is_admin, sanitize_phone_co


def register(bot):

    # --------------- /gasto ---------------

    @bot.message_handler(commands=["gasto"])
    def cmd_expense(message):
        if not is_admin(message):
            return
        try:
            bot.send_message(message.chat.id, "📝 <b>Registro de Gasto</b>\n\nEscribe el <b>concepto</b> del gasto:")
            bot.register_next_step_handler(message, step_expense_concept)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_expense_concept(message):
        if not is_admin(message):
            return
        try:
            expense_data = {"concepto": message.text.strip()}
            bot.send_message(message.chat.id, "💲 Escribe el <b>monto</b> del gasto:")
            bot.register_next_step_handler(message, step_expense_amount, expense_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_expense_amount(message, expense_data):
        if not is_admin(message):
            return
        try:
            amount = float(message.text.strip().replace(",", "."))
            if amount <= 0:
                bot.send_message(message.chat.id, "❌ El monto debe ser mayor a $0.")
                return
            today = date.today().isoformat()

            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO finanzas (tipo, concepto, monto, fecha) VALUES ('Egreso', %s, %s, %s)",
                    (expense_data["concepto"], amount, today)
                )
                conn.commit()
            finally:
                conn.close()

            bot.send_message(
                message.chat.id,
                f"✅ <b>Gasto registrado</b>\n\n"
                f"📋 Concepto: {expense_data['concepto']}\n"
                f"💸 Monto: <b>${amount:,.0f}</b>"
            )
        except ValueError:
            bot.send_message(message.chat.id, "❌ Monto inválido. Ingresa un número.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /caja ---------------

    @bot.message_handler(commands=["caja"])
    def cmd_cash_report(message):
        if not is_admin(message):
            return
        try:
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.row(
                types.InlineKeyboardButton("📅 Hoy", callback_data="caja:hoy"),
                types.InlineKeyboardButton("📆 Esta Semana", callback_data="caja:semana"),
            )
            markup.row(
                types.InlineKeyboardButton("🗓️ Este Mes", callback_data="caja:mes"),
                types.InlineKeyboardButton("📊 Histórico Total", callback_data="caja:total"),
            )

            bot.send_message(
                message.chat.id,
                "💼 <b>ESTADO DE RESULTADOS</b>\n\n¿Qué período deseas consultar?",
                reply_markup=markup
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("caja:"))
    def handle_caja_callback(call):
        """Handle caja period selection via inline buttons."""
        try:
            bot.answer_callback_query(call.id)
            period = call.data.replace("caja:", "")
            today = date.today()

            if period == "hoy":
                date_filter = today.isoformat()
                period_label = f"HOY ({today.strftime('%d/%m/%Y')})"
            elif period == "semana":
                start_of_week = (today - timedelta(days=today.weekday())).isoformat()
                date_filter = start_of_week
                period_label = f"ESTA SEMANA (desde {start_of_week})"
            elif period == "mes":
                start_of_month = today.replace(day=1).isoformat()
                date_filter = start_of_month
                period_label = f"ESTE MES ({today.strftime('%B %Y')})"
            else:
                date_filter = None
                period_label = "HISTÓRICO TOTAL"

            conn = get_connection()
            try:
                if date_filter:
                    income_row = conn.execute(
                        "SELECT COALESCE(SUM(monto), 0) as total FROM finanzas WHERE tipo = 'Ingreso' AND fecha >= %s", (date_filter,)
                    ).fetchone()
                    cogs_row = conn.execute(
                        "SELECT COALESCE(SUM(cantidad * costo_compra), 0) as total FROM pedidos WHERE estado = 'Entregado' AND fecha >= %s", (date_filter,)
                    ).fetchone()
                    expenses_row = conn.execute(
                        "SELECT COALESCE(SUM(monto), 0) as total FROM finanzas WHERE tipo = 'Egreso' AND fecha >= %s", (date_filter,)
                    ).fetchone()
                else:
                    income_row = conn.execute("SELECT COALESCE(SUM(monto), 0) as total FROM finanzas WHERE tipo = 'Ingreso'").fetchone()
                    cogs_row = conn.execute("SELECT COALESCE(SUM(cantidad * costo_compra), 0) as total FROM pedidos WHERE estado = 'Entregado'").fetchone()
                    expenses_row = conn.execute("SELECT COALESCE(SUM(monto), 0) as total FROM finanzas WHERE tipo = 'Egreso'").fetchone()
            finally:
                conn.close()

            gross_income = income_row["total"]
            cogs = cogs_row["total"]
            expenses = expenses_row["total"]
            net_profit = gross_income - cogs - expenses
            salary = net_profit * 0.50
            investment = net_profit * 0.30
            truck_fund = net_profit * 0.20

            report = f"💼 <b>ESTADO DE RESULTADOS — {period_label}</b>\n"
            report += f"📅 JD Trading Oil S.A.S\n"
            report += "━" * 30 + "\n\n"
            report += f"💰 Ingreso Bruto: <b>${gross_income:,.0f}</b>\n"
            report += f"🛒 Costo Mercancía (PROVEEDOR): <b>${cogs:,.0f}</b>\n"
            report += f"🚚 Gastos Operativos: <b>${expenses:,.0f}</b>\n"
            report += "━" * 30 + "\n"
            report += f"💵 <b>UTILIDAD NETA: ${net_profit:,.0f}</b>\n\n"
            report += "🏦 <b>REPARTO DE UTILIDAD NETA:</b>\n"
            report += f"  👤 50% Salario: ${salary:,.0f}\n"
            report += f"  📈 30% Inversión: ${investment:,.0f}\n"
            report += f"  🚛 20% Fondo Camión: ${truck_fund:,.0f}\n"

            bot.send_message(call.message.chat.id, report)
        except Exception as e:
            bot.send_message(call.message.chat.id, f"⚠️ Error al generar estado de caja: {e}")

    # --------------- /cuentas_por_cobrar ---------------

    @bot.message_handler(commands=["cuentas_por_cobrar"])
    def cmd_receivables(message):
        if not is_admin(message):
            return
        try:
            conn = get_connection()
            try:
                receivables = conn.execute("""
                    SELECT c.id, c.nombre, c.telefono,
                           COUNT(p.id) as num_pedidos,
                           SUM(p.cantidad * p.precio_venta) as total_deuda,
                           MIN(p.fecha) as pedido_mas_antiguo
                    FROM pedidos p JOIN clientes c ON p.cliente_id = c.id
                    WHERE p.estado = 'Entregado' AND (p.estado_pago IS NULL OR p.estado_pago = 'Pendiente')
                    GROUP BY c.id
                    ORDER BY total_deuda DESC
                """).fetchall()
            finally:
                conn.close()

            if not receivables:
                bot.send_message(message.chat.id, "✅ ¡Cartera limpia! No hay cuentas por cobrar.")
                return

            grand_total = sum(row["total_deuda"] for row in receivables)

            response = "💳 <b>CARTERA POR COBRAR</b>\n"
            response += "━" * 30 + "\n"
            response += f"💰 Total cartera: <b>${grand_total:,.0f}</b>\n"
            response += f"👥 Clientes con deuda: <b>{len(receivables)}</b>\n\n"

            for row in receivables:
                days = (date.today() - date.fromisoformat(row["pedido_mas_antiguo"])).days
                urgency = "🔴" if days > 7 else ("🟡" if days > 3 else "🟢")
                phone = sanitize_phone_co(row["telefono"])
                wa_url = f"https://wa.me/{phone}"

                response += f"{urgency} <b>{row['nombre']}</b>\n"
                response += f"   💰 ${row['total_deuda']:,.0f} | {row['num_pedidos']} pedido(s)\n"
                response += f"   📅 Más antiguo: {row['pedido_mas_antiguo']} ({days} días)\n"
                response += f"   📲 <a href='{wa_url}'>WhatsApp</a>\n\n"

            bot.send_message(message.chat.id, response, disable_web_page_preview=True)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /margen ---------------

    @bot.message_handler(commands=["margen"])
    def cmd_margin(message):
        if not is_admin(message):
            return
        try:
            conn = get_connection()
            try:
                # Margin per product
                products = conn.execute("""
                    SELECT producto,
                           SUM(cantidad) as total_uds,
                           AVG(costo_compra) as avg_costo,
                           AVG(precio_venta) as avg_venta,
                           SUM(cantidad * precio_venta) as total_ventas,
                           SUM(cantidad * (precio_venta - costo_compra)) as total_utilidad
                    FROM pedidos WHERE estado = 'Entregado'
                    GROUP BY producto ORDER BY total_utilidad DESC
                """).fetchall()

                # Top clients by profitability
                top_clients = conn.execute("""
                    SELECT c.nombre,
                           SUM(p.cantidad * p.precio_venta) as total_ventas,
                           SUM(p.cantidad * (p.precio_venta - p.costo_compra)) as utilidad
                    FROM pedidos p JOIN clientes c ON p.cliente_id = c.id
                    WHERE p.estado = 'Entregado'
                    GROUP BY c.id ORDER BY utilidad DESC LIMIT 5
                """).fetchall()
            finally:
                conn.close()

            response = "📊 <b>ANÁLISIS DE MARGEN DE RENTABILIDAD</b>\n"
            response += "━" * 34 + "\n\n"

            if products:
                response += "📦 <b>MARGEN POR PRODUCTO:</b>\n\n"
                for p in products:
                    if p["avg_venta"] and p["avg_venta"] > 0:
                        margin_pct = ((p["avg_venta"] - p["avg_costo"]) / p["avg_venta"]) * 100
                        margin_unit = p["avg_venta"] - p["avg_costo"]
                    else:
                        margin_pct = 0
                        margin_unit = 0

                    response += f"  📦 <b>{p['producto']}</b>\n"
                    response += f"     💲 Costo prom: ${p['avg_costo']:,.0f} | Venta prom: ${p['avg_venta']:,.0f}\n"
                    response += f"     📈 Margen: <b>{margin_pct:.1f}%</b> (${margin_unit:,.0f}/ud)\n"
                    response += f"     📊 {p['total_uds']} uds vendidas | Utilidad: ${p['total_utilidad']:,.0f}\n\n"
            else:
                response += "📦 Sin datos de productos entregados aún.\n\n"

            if top_clients:
                response += "🏆 <b>TOP 5 CLIENTES POR RENTABILIDAD:</b>\n\n"
                medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
                for i, c in enumerate(top_clients):
                    pct = (c["utilidad"] / c["total_ventas"] * 100) if c["total_ventas"] else 0
                    response += f"  {medals[i]} {c['nombre']}\n"
                    response += f"     💰 Ventas: ${c['total_ventas']:,.0f} | Utilidad: ${c['utilidad']:,.0f} ({pct:.0f}%)\n\n"

            bot.send_message(message.chat.id, response)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /meta ---------------

    @bot.message_handler(commands=["meta"])
    def cmd_target(message):
        if not is_admin(message):
            return
        try:
            today = date.today()
            current_month = today.strftime("%Y-%m")
            month_label = today.strftime("%B %Y").upper()
            first_day = today.replace(day=1)

            # Calculate week of month (1-4)
            day_of_month = today.day
            week_number = min(4, (day_of_month - 1) // 7 + 1)
            days_in_month = (first_day.replace(month=first_day.month % 12 + 1, day=1) - timedelta(days=1)).day if first_day.month < 12 else 31
            days_left = days_in_month - day_of_month

            conn = get_connection()
            try:
                # Get monthly goals
                goals = conn.execute("""
                    SELECT * FROM metas WHERE mes = %s ORDER BY producto
                """, (current_month,)).fetchall()

                # Get monthly sales per product
                sales = conn.execute("""
                    SELECT producto, COALESCE(SUM(cantidad), 0) as uds_vendidas
                    FROM pedidos
                    WHERE fecha >= %s AND estado IN ('Pendiente', 'Entregado')
                    GROUP BY producto
                """, (first_day.isoformat(),)).fetchall()

                # Get current prices
                prices = conn.execute("SELECT producto, precio_venta FROM precios").fetchall()

                # Total orders this month
                total_orders = conn.execute("""
                    SELECT COUNT(*) as c FROM pedidos WHERE fecha >= %s
                """, (first_day.isoformat(),)).fetchone()["c"]
            finally:
                conn.close()

            sales_map = {s["producto"]: s["uds_vendidas"] for s in sales}
            price_map = {p["producto"]: p["precio_venta"] for p in prices}

            if not goals:
                response = f"🎯 <b>META MENSUAL — {month_label}</b>\n"
                response += "━" * 30 + "\n\n"
                response += "⚠️ No tienes metas configuradas para este mes.\n\n"
                response += "👇 Presiona un producto para configurar su meta:"

                markup = types.InlineKeyboardMarkup(row_width=1)
                for product_name in PRODUCT_CATALOG:
                    sold = sales_map.get(product_name, 0)
                    markup.add(types.InlineKeyboardButton(
                        f"🎯 {product_name} ({sold} vendidas)",
                        callback_data=f"meta_set:{product_name}"
                    ))

                bot.send_message(message.chat.id, response, reply_markup=markup)
                return

            # Build the monthly report
            response = f"🎯 <b>META MENSUAL — {month_label}</b>\n"
            response += "━" * 30 + "\n"
            response += f"📅 Semana {week_number}/4 | Quedan {days_left} días\n"
            response += f"📦 Pedidos del mes: {total_orders}\n\n"

            total_revenue_sold = 0
            total_revenue_goal = 0

            for g in goals:
                product = g["producto"]
                goal_monthly = g["meta_unidades"]
                goal_weekly = goal_monthly / 4
                sold = sales_map.get(product, 0)
                price = price_map.get(product, 0)

                progress = (sold / goal_monthly * 100) if goal_monthly > 0 else 0
                remaining = max(0, goal_monthly - sold)

                # Weekly checkpoint
                expected_by_now = goal_weekly * week_number
                weekly_status = "✅" if sold >= expected_by_now else "⚠️"

                # Revenue calc
                revenue_sold = sold * price
                revenue_goal = goal_monthly * price
                total_revenue_sold += revenue_sold
                total_revenue_goal += revenue_goal

                # Progress bar
                filled = int(progress / 5)
                bar = "█" * min(filled, 20) + "░" * max(0, 20 - filled)

                response += f"📦 <b>{product}</b>\n"
                response += f"   🎯 Meta mensual: <b>{goal_monthly} uds</b> ({goal_weekly:.0f}/semana)\n"
                response += f"   ✅ Vendidas: <b>{sold} uds</b> ({progress:.0f}%)\n"
                response += f"   📊 Faltantes: {remaining} uds\n"
                response += f"   {weekly_status} Sem {week_number}: esperado {expected_by_now:.0f} uds | real {sold}\n"
                if price > 0:
                    response += f"   💰 Facturado: ${revenue_sold:,.0f} / ${revenue_goal:,.0f}\n"
                response += f"   <code>{bar}</code> {progress:.0f}%\n\n"

            # Total summary
            response += "━" * 30 + "\n"
            response += f"💰 <b>FACTURACIÓN ESTIMADA:</b>\n"
            response += f"   Vendido: <b>${total_revenue_sold:,.0f}</b>\n"
            response += f"   Meta: <b>${total_revenue_goal:,.0f}</b>\n\n"

            total_progress = (total_revenue_sold / total_revenue_goal * 100) if total_revenue_goal > 0 else 0
            if total_progress >= 100:
                response += "🎉 <b>¡META CUMPLIDA!</b> 🏆🔥"
            elif total_progress >= 75:
                response += "💪 ¡Casi lo logras! Empuja fuerte."
            elif total_progress >= 50:
                response += "🚀 Vas en buen camino. ¡Sigue así!"
            else:
                response += "⚡ Acelera las ventas. ¡Tú puedes!"

            markup = types.InlineKeyboardMarkup(row_width=1)
            for product_name in PRODUCT_CATALOG:
                markup.add(types.InlineKeyboardButton(
                    f"✏️ Cambiar meta: {product_name}",
                    callback_data=f"meta_set:{product_name}"
                ))

            bot.send_message(message.chat.id, response, reply_markup=markup)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- META SET CALLBACKS ---------------

    @bot.callback_query_handler(func=lambda call: call.data.startswith("meta_set:"))
    def handle_meta_set_callback(call):
        """Handle meta set inline button."""
        try:
            bot.answer_callback_query(call.id)
            product_name = call.data.replace("meta_set:", "")

            today = date.today()
            current_month = today.strftime("%Y-%m")

            conn = get_connection()
            try:
                existing = conn.execute(
                    "SELECT meta_unidades FROM metas WHERE producto = %s AND mes = %s",
                    (product_name, current_month)
                ).fetchone()

                sold = conn.execute("""
                    SELECT COALESCE(SUM(cantidad), 0) as uds
                    FROM pedidos WHERE producto = %s AND fecha >= %s AND estado IN ('Pendiente', 'Entregado')
                """, (product_name, today.replace(day=1).isoformat())).fetchone()["uds"]
            finally:
                conn.close()

            current = existing["meta_unidades"] if existing else 0

            msg = f"🎯 <b>CONFIGURAR META: {product_name}</b>\n\n"
            if current > 0:
                msg += f"📊 Meta actual: <b>{current} uds/mes</b>\n"
            msg += f"✅ Vendidas este mes: <b>{sold} uds</b>\n\n"
            msg += "Escribe la <b>cantidad de unidades</b> como meta mensual:\n"
            msg += "<i>(Ej: 100 para 100 unidades al mes = 25/semana)</i>"

            call.message.from_user = call.from_user
            bot.send_message(call.message.chat.id, msg)
            bot.register_next_step_handler(call.message, step_meta_save, product_name)
        except Exception as e:
            bot.answer_callback_query(call.id, f"⚠️ Error: {e}")

    def step_meta_save(message, product_name):
        if not is_admin(message):
            return
        try:
            units = int(message.text.strip())
            if units <= 0:
                bot.send_message(message.chat.id, "❌ La meta debe ser mayor a 0.")
                return

            today = date.today()
            current_month = today.strftime("%Y-%m")

            conn = get_connection()
            try:
                existing = conn.execute(
                    "SELECT id FROM metas WHERE producto = %s AND mes = %s",
                    (product_name, current_month)
                ).fetchone()

                if existing:
                    conn.execute(
                        "UPDATE metas SET meta_unidades = %s, fecha_creacion = %s WHERE producto = %s AND mes = %s",
                        (units, today.isoformat(), product_name, current_month)
                    )
                else:
                    conn.execute(
                        "INSERT INTO metas (producto, meta_unidades, mes, fecha_creacion) VALUES (%s, %s, %s, %s)",
                        (product_name, units, current_month, today.isoformat())
                    )
                conn.commit()

                price = conn.execute("SELECT precio_venta FROM precios WHERE producto = %s", (product_name,)).fetchone()
            finally:
                conn.close()

            weekly = units / 4
            revenue = units * (price["precio_venta"] if price else 0)

            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("🎯 Ver Metas Completas", callback_data="cmd_meta"))

            bot.send_message(
                message.chat.id,
                f"✅ <b>Meta configurada</b>\n\n"
                f"📦 {product_name}\n"
                f"🎯 Meta mensual: <b>{units} uds</b>\n"
                f"📅 Semanal: <b>{weekly:.0f} uds/semana</b>\n"
                f"💰 Facturación estimada: <b>${revenue:,.0f}</b>\n\n"
                f"📊 Semana 1: {weekly:.0f} uds\n"
                f"📊 Semana 2: {weekly*2:.0f} uds\n"
                f"📊 Semana 3: {weekly*3:.0f} uds\n"
                f"📊 Semana 4: {units} uds ← META 🏁",
                reply_markup=markup
            )
        except ValueError:
            bot.send_message(message.chat.id, "❌ Escribe un número válido. Ej: 100")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /meta_set (command fallback) ---------------

    @bot.message_handler(commands=["meta_set"])
    def cmd_target_set(message):
        if not is_admin(message):
            return
        try:
            # Show product selection buttons
            markup = types.InlineKeyboardMarkup(row_width=1)
            for product_name in PRODUCT_CATALOG:
                markup.add(types.InlineKeyboardButton(
                    f"🎯 {product_name}",
                    callback_data=f"meta_set:{product_name}"
                ))

            bot.send_message(
                message.chat.id,
                "🎯 <b>CONFIGURAR META MENSUAL</b>\n\n"
                "Selecciona el producto:",
                reply_markup=markup
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")
