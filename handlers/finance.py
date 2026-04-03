# -*- coding: utf-8 -*-
"""
Handlers: Finance
Commands: /gasto, /caja, /cuentas_por_cobrar, /margen, /meta
"""
from telebot import types
from datetime import date, timedelta

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
                    "INSERT INTO finanzas (tipo, concepto, monto, fecha) VALUES ('Egreso', ?, ?, ?)",
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
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("📅 Hoy", "📆 Esta Semana")
            markup.add("🗓️ Este Mes", "📊 Histórico Total")

            bot.send_message(
                message.chat.id,
                "💼 <b>ESTADO DE RESULTADOS</b>\n\n¿Qué período deseas consultar?",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_caja_filter)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_caja_filter(message):
        if not is_admin(message):
            return
        try:
            selected = message.text.strip()
            today = date.today()

            if "Hoy" in selected:
                date_filter = today.isoformat()
                period_label = f"HOY ({today.strftime('%d/%m/%Y')})"
            elif "Semana" in selected:
                start_of_week = (today - timedelta(days=today.weekday())).isoformat()
                date_filter = start_of_week
                period_label = f"ESTA SEMANA (desde {start_of_week})"
            elif "Mes" in selected:
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
                        "SELECT COALESCE(SUM(monto), 0) as total FROM finanzas WHERE tipo = 'Ingreso' AND fecha >= ?", (date_filter,)
                    ).fetchone()
                    cogs_row = conn.execute(
                        "SELECT COALESCE(SUM(cantidad * costo_compra), 0) as total FROM pedidos WHERE estado = 'Entregado' AND fecha >= ?", (date_filter,)
                    ).fetchone()
                    expenses_row = conn.execute(
                        "SELECT COALESCE(SUM(monto), 0) as total FROM finanzas WHERE tipo = 'Egreso' AND fecha >= ?", (date_filter,)
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

            bot.send_message(message.chat.id, report, reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error al generar estado de caja: {e}")

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
            start_of_week = (today - timedelta(days=today.weekday())).isoformat()
            end_of_week = (today + timedelta(days=6 - today.weekday())).isoformat()

            conn = get_connection()
            try:
                # Check if there's a current weekly target
                current_meta = conn.execute("""
                    SELECT * FROM metas WHERE tipo = 'semanal' AND fecha_inicio <= ? AND fecha_fin >= ?
                """, (today.isoformat(), today.isoformat())).fetchone()

                # Current week sales
                week_sales = conn.execute("""
                    SELECT COALESCE(SUM(cantidad * precio_venta), 0) as total
                    FROM pedidos WHERE fecha >= ? AND estado IN ('Pendiente', 'Entregado')
                """, (start_of_week,)).fetchone()["total"]

                orders_count = conn.execute("""
                    SELECT COUNT(*) as c FROM pedidos WHERE fecha >= ?
                """, (start_of_week,)).fetchone()["c"]
            finally:
                conn.close()

            if current_meta:
                meta_value = current_meta["meta"]
                progress = (week_sales / meta_value * 100) if meta_value > 0 else 0
                remaining = max(0, meta_value - week_sales)
                days_left = (date.fromisoformat(end_of_week) - today).days

                # Progress bar
                filled = int(progress / 5)
                bar = "█" * min(filled, 20) + "░" * max(0, 20 - filled)

                response = f"🎯 <b>META SEMANAL</b>\n"
                response += "━" * 30 + "\n\n"
                response += f"💰 Meta: <b>${meta_value:,.0f}</b>\n"
                response += f"✅ Vendido: <b>${week_sales:,.0f}</b> ({progress:.1f}%)\n"
                response += f"📦 Pendiente: ${remaining:,.0f}\n"
                response += f"📦 Pedidos esta semana: {orders_count}\n"
                response += f"📅 Quedan {days_left} días\n\n"
                response += f"<code>{bar}</code> {progress:.0f}%\n\n"

                if progress >= 100:
                    response += "🎉 <b>¡META CUMPLIDA!</b> 🏆🔥"
                elif progress >= 75:
                    response += "💪 ¡Casi lo logras! Empuja fuerte estos últimos días."
                elif progress >= 50:
                    response += "🚀 Vas en buen camino. ¡Sigue así!"
                else:
                    response += "⚡ Acelera las ventas. ¡Tú puedes!"

                response += "\n\n💡 Para cambiar la meta: /meta_set [monto]"
            else:
                response = "🎯 <b>META SEMANAL</b>\n\n"
                response += f"📊 Ventas esta semana: <b>${week_sales:,.0f}</b>\n"
                response += f"📦 Pedidos: {orders_count}\n\n"
                response += "⚠️ No tienes meta configurada.\n"
                response += "Usa: /meta_set [monto]\n"
                response += "Ej: <code>/meta_set 2000000</code>"

            bot.send_message(message.chat.id, response, reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    @bot.message_handler(commands=["meta_set"])
    def cmd_target_set(message):
        if not is_admin(message):
            return
        try:
            parts = message.text.strip().split()
            if len(parts) < 2:
                bot.send_message(message.chat.id, "❌ Uso: /meta_set [monto]\nEj: /meta_set 2000000")
                return

            meta_value = float(parts[1].replace(",", ""))
            if meta_value <= 0:
                bot.send_message(message.chat.id, "❌ La meta debe ser mayor a $0.")
                return

            today = date.today()
            start_of_week = (today - timedelta(days=today.weekday())).isoformat()
            end_of_week = (today + timedelta(days=6 - today.weekday())).isoformat()

            conn = get_connection()
            try:
                # Delete any existing weekly target for this week
                conn.execute("DELETE FROM metas WHERE tipo = 'semanal' AND fecha_inicio = ?", (start_of_week,))
                conn.execute(
                    "INSERT INTO metas (tipo, meta, fecha_inicio, fecha_fin) VALUES ('semanal', ?, ?, ?)",
                    (meta_value, start_of_week, end_of_week)
                )
                conn.commit()
            finally:
                conn.close()

            bot.send_message(
                message.chat.id,
                f"✅ <b>Meta semanal configurada</b>\n\n"
                f"🎯 Meta: <b>${meta_value:,.0f}</b>\n"
                f"📅 {start_of_week} al {end_of_week}\n\n"
                "Usa /meta para ver tu progreso."
            )
        except ValueError:
            bot.send_message(message.chat.id, "❌ Monto inválido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")
