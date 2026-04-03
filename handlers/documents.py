# -*- coding: utf-8 -*-
"""
Handlers: Document Generation (PDFs)
Commands: /remision, /despacho_jd
"""
import io
from telebot import types
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER

from config import (
    COMPANY_NAME, COMPANY_ADDRESS, COMPANY_CITY,
    COMPANY_PHONE, COMPANY_EMAIL, OWNER_NAME, OWNER_CC
)
from database import get_connection
from utils import is_admin


def register(bot):

    # --------------- /remision ---------------

    @bot.message_handler(commands=["remision"])
    def cmd_remission(message):
        if not is_admin(message):
            return
        try:
            parts = message.text.strip().split()
            if len(parts) < 2:
                bot.send_message(message.chat.id, "❌ Uso: /remision [ID_Pedido]")
                return

            order_id = int(parts[1])
            conn = get_connection()
            try:
                order = conn.execute("""
                    SELECT p.*, c.nombre as cliente_nombre, c.direccion as cliente_dir, c.telefono as cliente_tel
                    FROM pedidos p JOIN clientes c ON p.cliente_id = c.id WHERE p.id = ?
                """, (order_id,)).fetchone()
            finally:
                conn.close()

            if not order:
                bot.send_message(message.chat.id, "❌ Pedido no encontrado.")
                return

            total = order["cantidad"] * order["precio_venta"]

            buffer = io.BytesIO()
            page_w, page_h = 140 * mm, 216 * mm
            doc = SimpleDocTemplate(buffer, pagesize=(page_w, page_h),
                                    leftMargin=10*mm, rightMargin=10*mm, topMargin=10*mm, bottomMargin=10*mm)

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle("RemTitle", parent=styles["Title"], fontSize=14, alignment=TA_CENTER)
            normal_style = ParagraphStyle("RemNormal", parent=styles["Normal"], fontSize=9)

            elements = []
            elements.append(Paragraph(f"REMISIÓN {COMPANY_NAME}", title_style))
            elements.append(Spacer(1, 5 * mm))

            data = [
                ["Remisión No.", str(order_id), "Fecha", order["fecha"]],
                ["Cliente", order["cliente_nombre"], "Dirección", order["cliente_dir"] or ""],
                ["Teléfono", order["cliente_tel"] or "", "", ""],
            ]
            t = Table(data, colWidths=[25*mm, 35*mm, 25*mm, 35*mm])
            t.setStyle(TableStyle([
                ("GRID", (0,0), (-1,-1), 0.5, colors.black),
                ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
                ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 8),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("BACKGROUND", (0,0), (0,-1), colors.Color(0.9,0.9,0.9)),
                ("BACKGROUND", (2,0), (2,-1), colors.Color(0.9,0.9,0.9)),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 5 * mm))

            detail_data = [
                ["Producto", "Cantidad", "Precio Unit.", "Total"],
                [order["producto"], str(order["cantidad"]), f"${order['precio_venta']:,.0f}", f"${total:,.0f}"],
            ]
            dt = Table(detail_data, colWidths=[40*mm, 25*mm, 25*mm, 30*mm])
            dt.setStyle(TableStyle([
                ("GRID", (0,0), (-1,-1), 0.5, colors.black),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 9),
                ("ALIGN", (1,0), (-1,-1), "CENTER"),
                ("BACKGROUND", (0,0), (-1,0), colors.Color(0.85,0.85,0.85)),
            ]))
            elements.append(dt)
            elements.append(Spacer(1, 8 * mm))
            elements.append(Paragraph(f"<b>TOTAL A PAGAR: ${total:,.0f}</b>", normal_style))

            doc.build(elements)
            buffer.seek(0)

            bot.send_document(
                message.chat.id, buffer,
                visible_file_name=f"Remision_{order_id}_JDTrading.pdf",
                caption=f"📄 Remisión #{order_id} — {order['cliente_nombre']} — Total: ${total:,.0f}"
            )
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID inválido. Uso: /remision [ID_Pedido]")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error al generar remisión: {e}")

    # --------------- /despacho_jd ---------------

    @bot.message_handler(commands=["despacho_jd"])
    def cmd_dispatch(message):
        if not is_admin(message):
            return
        try:
            dispatch_data = {"items": []}
            bot.send_message(
                message.chat.id,
                "🚛 <b>DESPACHO DE MERCANCÍA — VENCO OIL SAS</b>\n\n"
                "Este formato se usa para retirar mercancía de tu proveedor.\n\n"
                "📦 <b>Paso 1:</b> Ingresa la mercancía\n"
                "Escribe la <b>descripción del producto</b>:\n"
                "(Ej: Hidrogenados Oleosoberano)"
            )
            bot.register_next_step_handler(message, step_desp_item_desc, dispatch_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_desp_item_desc(message, dispatch_data):
        if not is_admin(message):
            return
        try:
            current_item = {"descripcion": message.text.strip()}
            bot.send_message(message.chat.id, "📋 <b>Presentación</b> (Ej: Caja, Bidón 18L):")
            bot.register_next_step_handler(message, step_desp_item_pres, dispatch_data, current_item)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_desp_item_pres(message, dispatch_data, current_item):
        if not is_admin(message):
            return
        try:
            current_item["presentacion"] = message.text.strip()
            bot.send_message(message.chat.id, "🔢 <b>Cantidad</b> de unidades:")
            bot.register_next_step_handler(message, step_desp_item_qty, dispatch_data, current_item)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_desp_item_qty(message, dispatch_data, current_item):
        if not is_admin(message):
            return
        try:
            current_item["cantidad"] = int(message.text.strip())
            bot.send_message(message.chat.id, "⚖️ <b>Peso por unidad</b> en kg (Ej: 15):")
            bot.register_next_step_handler(message, step_desp_item_weight, dispatch_data, current_item)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Número inválido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_desp_item_weight(message, dispatch_data, current_item):
        if not is_admin(message):
            return
        try:
            current_item["peso_ud"] = float(message.text.strip().replace(",", "."))
            current_item["peso_total"] = current_item["cantidad"] * current_item["peso_ud"]
            dispatch_data["items"].append(current_item)

            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("➕ Agregar otro producto", "✅ Continuar con transporte")

            items_list = ""
            for i, item in enumerate(dispatch_data["items"], 1):
                items_list += f"  {i}. {item['descripcion']} | {item['presentacion']} | {item['cantidad']} uds | {item['peso_total']:.0f} kg\n"

            bot.send_message(
                message.chat.id,
                f"✅ Producto agregado.\n\n📦 <b>Mercancía actual:</b>\n{items_list}\n¿Agregar otro producto o continuar?",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_desp_more_items, dispatch_data)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Peso inválido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_desp_more_items(message, dispatch_data):
        if not is_admin(message):
            return
        try:
            if "Agregar" in message.text:
                bot.send_message(message.chat.id, "📦 Escribe la <b>descripción del siguiente producto</b>:", reply_markup=types.ReplyKeyboardRemove())
                bot.register_next_step_handler(message, step_desp_item_desc, dispatch_data)
            else:
                bot.send_message(message.chat.id, "🚛 <b>INFORMACIÓN DEL TRANSPORTE</b>\n\n1️⃣ Escribe la <b>Empresa Transportadora</b>:", reply_markup=types.ReplyKeyboardRemove())
                bot.register_next_step_handler(message, step_desp_transport_company, dispatch_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_desp_transport_company(message, dispatch_data):
        if not is_admin(message):
            return
        try:
            dispatch_data["empresa"] = message.text.strip()
            bot.send_message(message.chat.id, "2️⃣ <b>Nombre del Conductor</b>:")
            bot.register_next_step_handler(message, step_desp_transport_driver, dispatch_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_desp_transport_driver(message, dispatch_data):
        if not is_admin(message):
            return
        try:
            dispatch_data["conductor"] = message.text.strip()
            bot.send_message(message.chat.id, "3️⃣ <b>Cédula (CC) del Conductor</b>:")
            bot.register_next_step_handler(message, step_desp_transport_cc, dispatch_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_desp_transport_cc(message, dispatch_data):
        if not is_admin(message):
            return
        try:
            dispatch_data["cc"] = message.text.strip()
            bot.send_message(message.chat.id, "4️⃣ <b>Placa del Vehículo</b>:")
            bot.register_next_step_handler(message, step_desp_transport_plate, dispatch_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_desp_transport_plate(message, dispatch_data):
        if not is_admin(message):
            return
        try:
            dispatch_data["placa"] = message.text.strip()
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("Furgón", "Turbo", "Camión", "Camioneta")
            bot.send_message(message.chat.id, "5️⃣ <b>Tipo de Vehículo</b>:", reply_markup=markup)
            bot.register_next_step_handler(message, step_desp_transport_type, dispatch_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_desp_transport_type(message, dispatch_data):
        if not is_admin(message):
            return
        try:
            dispatch_data["tipo_vehiculo"] = message.text.strip()
            bot.send_message(message.chat.id, "6️⃣ <b>Teléfono del Conductor</b>:", reply_markup=types.ReplyKeyboardRemove())
            bot.register_next_step_handler(message, step_desp_transport_phone, dispatch_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_desp_transport_phone(message, dispatch_data):
        if not is_admin(message):
            return
        try:
            dispatch_data["telefono_conductor"] = message.text.strip()
            generate_venco_dispatch_pdf(bot, message, dispatch_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")


# =========================================================================
# PDF GENERATION (module-level)
# =========================================================================

def generate_venco_dispatch_pdf(bot, message, dispatch_data):
    """Generate PDF matching the exact Venco Oil dispatch format."""
    try:
        now = datetime.now()
        today_str = now.strftime("%d/%m/%Y")
        time_str = now.strftime("%H:%M")
        dispatch_id = now.strftime("%Y%m%d%H%M")

        grand_qty = sum(item["cantidad"] for item in dispatch_data["items"])
        grand_weight = sum(item["peso_total"] for item in dispatch_data["items"])

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                leftMargin=15*mm, rightMargin=15*mm, topMargin=12*mm, bottomMargin=12*mm)

        styles = getSampleStyleSheet()
        venco_green = colors.Color(0.15, 0.45, 0.15)
        venco_green_bg = colors.Color(0.85, 0.95, 0.85)
        venco_green_header = colors.Color(0.2, 0.5, 0.2)

        title_style = ParagraphStyle("VencoTitle", parent=styles["Title"], fontSize=16, alignment=TA_CENTER, spaceAfter=1*mm, fontName="Helvetica-Bold")
        company_style = ParagraphStyle("VencoCompany", parent=styles["Normal"], fontSize=14, alignment=TA_CENTER, fontName="Helvetica-Bold", spaceAfter=0)
        company_sub = ParagraphStyle("VencoSub", parent=styles["Normal"], fontSize=9, alignment=TA_CENTER, textColor=colors.gray, fontName="Helvetica-Oblique")
        section_style = ParagraphStyle("VencoSection", parent=styles["Normal"], fontSize=9, spaceBefore=4*mm, spaceAfter=1*mm, fontName="Helvetica-Bold", textColor=colors.white, backColor=venco_green_header, leftIndent=2*mm, borderPadding=2)
        obs_style = ParagraphStyle("ObsStyle", parent=styles["Normal"], fontSize=8, leading=11)
        legal_style = ParagraphStyle("LegalStyle", parent=styles["Normal"], fontSize=7, leading=10, spaceBefore=3*mm, textColor=colors.Color(0.3,0.3,0.3), fontName="Helvetica-Oblique")

        full_width = letter[0] - 30 * mm
        half_width = full_width / 2

        green_grid = TableStyle([
            ("GRID", (0,0), (-1,-1), 0.5, venco_green),
            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0), (-1,-1), 3*mm),
            ("TOPPADDING", (0,0), (-1,-1), 2*mm),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2*mm),
        ])

        elements = []

        # HEADER
        elements.append(Paragraph("<b>VENCO OIL SAS</b>", company_style))
        elements.append(Paragraph("Distribuidora de Aceites Vegetales", company_sub))
        elements.append(Paragraph("NIT: _______________", ParagraphStyle("nit", parent=styles["Normal"], fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
        elements.append(Spacer(1, 4*mm))

        # TITLE
        elements.append(Paragraph("<b>DESPACHO DE MERCANCIA</b>", title_style))
        elements.append(Paragraph("(Remision de Salida de Mercancia)", ParagraphStyle("subrem", parent=styles["Normal"], fontSize=9, alignment=TA_CENTER, textColor=colors.gray)))
        elements.append(Spacer(1, 3*mm))

        # TABLE 1: Document Info
        t1 = Table([[f"No. de Remision: {dispatch_id}", f"Fecha: {today_str}"], ["Pedido No.: _______________", f"Hora: {time_str}"]], colWidths=[half_width, half_width])
        t1.setStyle(green_grid)
        elements.append(t1)
        elements.append(Spacer(1, 2*mm))

        # TABLE 2: Sender
        elements.append(Paragraph("  DATOS DEL REMITENTE (VENCO OIL SAS)", section_style))
        t2 = Table([
            ["Razon Social:   VENCO OIL SAS", "NIT:"],
            [f"Direccion:   {COMPANY_ADDRESS}", f"Ciudad:   {COMPANY_CITY}"],
            [f"Telefono:   {COMPANY_PHONE}", f"Correo:   {COMPANY_EMAIL}"],
        ], colWidths=[half_width, half_width])
        t2.setStyle(green_grid)
        elements.append(t2)
        elements.append(Spacer(1, 2*mm))

        # TABLE 3: Recipient
        elements.append(Paragraph("  DATOS DEL DESTINATARIO (CLIENTE)", section_style))
        t3 = Table([
            [f"Razon Social / Nombre:   {OWNER_NAME}", f"NIT / CC:   {OWNER_CC}"],
            ["Direccion de Entrega:", f"Ciudad:   {COMPANY_CITY}"],
            ["Telefono:", "Correo:"],
            ["Contacto:", "Cargo:"],
        ], colWidths=[half_width, half_width])
        t3.setStyle(green_grid)
        elements.append(t3)
        elements.append(Spacer(1, 2*mm))

        # TABLE 4: Merchandise
        elements.append(Paragraph("  DETALLE DE MERCANCIA DESPACHADA", section_style))
        t4_header = ["Item", "Descripcion del Producto", "Presentacion", "Cantidad", "Peso kg", "Lote"]
        t4_data = [t4_header]
        for idx, item in enumerate(dispatch_data["items"], 1):
            t4_data.append([str(idx), item["descripcion"], item["presentacion"], str(item["cantidad"]), str(item["peso_ud"]), ""])
        while len(t4_data) < 9:
            t4_data.append(["", "", "", "", "", ""])

        col_widths_t4 = [full_width*0.06, full_width*0.34, full_width*0.16, full_width*0.14, full_width*0.15, full_width*0.15]
        t4 = Table(t4_data, colWidths=col_widths_t4)
        t4.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), 0.5, venco_green),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("ALIGN", (0,0), (0,-1), "CENTER"),
            ("ALIGN", (3,0), (5,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("BACKGROUND", (0,0), (-1,0), venco_green_bg),
            ("LEFTPADDING", (0,0), (-1,-1), 2*mm),
            ("TOPPADDING", (0,0), (-1,-1), 2*mm),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2*mm),
        ]))
        elements.append(t4)
        elements.append(Spacer(1, 3*mm))

        # TOTALS
        t_totals = Table([[f"TOTAL UNIDADES:   {grand_qty}", f"TOTAL PESO (kg):   {grand_weight:.0f}"]], colWidths=[half_width, half_width])
        t_totals.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("ALIGN", (0,0), (-1,-1), "RIGHT"),
            ("RIGHTPADDING", (0,0), (-1,-1), 10*mm),
        ]))
        elements.append(t_totals)
        elements.append(Spacer(1, 4*mm))

        # TABLE 5: Transport
        elements.append(Paragraph("  INFORMACION DEL TRANSPORTE", section_style))
        t5 = Table([
            [f"Empresa Transportadora:   {dispatch_data['empresa']}", "NIT:"],
            [f"Nombre del Conductor:   {dispatch_data['conductor']}", f"CC:   {dispatch_data['cc']}"],
            [f"Placa Vehiculo:   {dispatch_data['placa']}", f"Tipo Vehiculo:   {dispatch_data['tipo_vehiculo']}"],
            [f"Telefono Conductor:   {dispatch_data['telefono_conductor']}", "No. Guia Transporte:"],
        ], colWidths=[half_width, half_width])
        t5.setStyle(green_grid)
        elements.append(t5)
        elements.append(Spacer(1, 3*mm))

        # Observations
        elements.append(Paragraph("  OBSERVACIONES", section_style))
        obs_box = Table([[""]], colWidths=[full_width], rowHeights=[20*mm])
        obs_box.setStyle(TableStyle([("BOX", (0,0), (-1,-1), 0.5, venco_green)]))
        elements.append(obs_box)
        elements.append(Spacer(1, 4*mm))

        # Signatures
        sig_left = Paragraph(f"<b>{OWNER_NAME}</b><br/><br/><b>Elaborado por VENCO OIL SAS</b><br/><i>Nombre y Firma</i><br/>CC: {OWNER_CC}", obs_style)
        sig_right = Paragraph("<b>Recibido a satisfaccion</b><br/><br/><i>Nombre y Firma</i><br/>CC: _______________________", obs_style)
        t_sig = Table([[sig_left, sig_right]], colWidths=[half_width, half_width], rowHeights=[22*mm])
        t_sig.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 4*mm),
            ("TOPPADDING", (0,0), (-1,-1), 2*mm),
            ("LINEBELOW", (0,0), (0,0), 0.5, colors.black),
            ("LINEBELOW", (1,0), (1,0), 0.5, colors.black),
        ]))
        elements.append(t_sig)
        elements.append(Spacer(1, 3*mm))

        # Legal
        elements.append(Paragraph(
            "<i>Declaro que he recibido la mercancia descrita en el presente documento en buenas "
            "condiciones fisicas y de empaque. Acepto los terminos y condiciones de entrega "
            "establecidos por VENCO OIL SAS.</i>", legal_style
        ))

        doc.build(elements)
        buffer.seek(0)

        bot.send_document(message.chat.id, buffer,
                          visible_file_name=f"Despacho_VencoOil_{dispatch_id}.pdf",
                          caption=f"📦 Despacho Venco Oil — {grand_qty} unidades / {grand_weight:.0f} kg")
        bot.send_message(message.chat.id, "✅ Documento de despacho generado exitosamente.")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Error al generar despacho: {e}")
