# -*- coding: utf-8 -*-
"""
Handlers: Finance
Commands: /gasto, /caja
"""
from telebot import types
from datetime import date, timedelta

from database import get_connection
from utils import is_admin


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
