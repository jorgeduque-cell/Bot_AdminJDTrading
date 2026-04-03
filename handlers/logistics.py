# -*- coding: utf-8 -*-
"""
Handlers: Logistics — Routing & Inventory
Commands: /ruta_pie, /ruta_camion, /inventario
"""
from telebot import types
from datetime import date

from config import (
    PRODUCT_CATALOG, GOOGLE_API_KEY, TARGET_BUSINESS_TYPES,
    SEARCH_RADIUS_OPTIONS, DEFAULT_SEARCH_RADIUS, TRANSMILENIO_STATIONS,
    MINUTES_PER_STOP, MAX_DISCOVERY_STOPS, COMPANY_ADDRESS, COMPANY_CITY
)
from database import get_connection
from utils import (
    is_admin, geocode_address, search_nearby_places,
    haversine_distance, is_blacklisted, build_google_maps_links
)


def register(bot):

    # --------------- /inventario ---------------

    @bot.message_handler(commands=["inventario"])
    def cmd_inventory(message):
        if not is_admin(message):
            return
        try:
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("📊 Ver Stock")
            markup.add("➕ Ingresar Mercancía")
            markup.add("⚙️ Ajustar Stock Mínimo")
            markup.add("❌ Cancelar")

            bot.send_message(message.chat.id, "📦 <b>CONTROL DE INVENTARIO</b>\n\n¿Qué deseas hacer?", reply_markup=markup)
            bot.register_next_step_handler(message, step_inventory_action)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_inventory_action(message):
        if not is_admin(message):
            return
        try:
            selected = message.text.strip()
            if "Cancelar" in selected:
                bot.send_message(message.chat.id, "❌ Cancelado.", reply_markup=types.ReplyKeyboardRemove())
                return

            if "Ver Stock" in selected:
                conn = get_connection()
                try:
                    items = conn.execute("SELECT * FROM inventario ORDER BY producto").fetchall()
                finally:
                    conn.close()

                response = "📦 <b>INVENTARIO EN BODEGA</b>\n" + "━" * 30 + "\n\n"
                for item in items:
                    alert = "🟡 BAJO" if item["stock_actual"] <= item["stock_minimo"] else "🟢 OK"
                    if item["stock_actual"] == 0:
                        alert = "🔴 AGOTADO"
                    response += f"📦 <b>{item['producto']}</b>\n"
                    response += f"   Stock: <b>{item['stock_actual']}</b> uds | Mín: {item['stock_minimo']} | {alert}\n"
                    response += f"   📅 Últ. mov: {item['ultima_actualizacion'] or 'N/A'}\n\n"

                bot.send_message(message.chat.id, response, reply_markup=types.ReplyKeyboardRemove())

            elif "Ingresar" in selected:
                markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                for product_name in PRODUCT_CATALOG:
                    markup.add(product_name)
                bot.send_message(message.chat.id, "➕ <b>INGRESO DE MERCANCÍA</b>\n\nSelecciona el producto:", reply_markup=markup)
                bot.register_next_step_handler(message, step_inventory_add_product)

            elif "Ajustar" in selected:
                markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                for product_name in PRODUCT_CATALOG:
                    markup.add(product_name)
                bot.send_message(message.chat.id, "⚙️ <b>AJUSTAR STOCK MÍNIMO</b>\n\nSelecciona el producto:", reply_markup=markup)
                bot.register_next_step_handler(message, step_inventory_min_product)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_inventory_add_product(message):
        if not is_admin(message):
            return
        try:
            product = message.text.strip()
            if product not in PRODUCT_CATALOG:
                bot.send_message(message.chat.id, "❌ Producto no válido.", reply_markup=types.ReplyKeyboardRemove())
                return
            bot.send_message(message.chat.id, f"➕ ¿Cuántas unidades de <b>{product}</b> ingresan a bodega?", reply_markup=types.ReplyKeyboardRemove())
            bot.register_next_step_handler(message, step_inventory_add_qty, product)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_inventory_add_qty(message, product):
        if not is_admin(message):
            return
        try:
            qty = int(message.text.strip())
            if qty <= 0:
                bot.send_message(message.chat.id, "❌ La cantidad debe ser mayor a 0.")
                return

            today = date.today().isoformat()
            conn = get_connection()
            try:
                conn.execute(
                    "UPDATE inventario SET stock_actual = stock_actual + ?, ultima_actualizacion = ? WHERE producto = ?",
                    (qty, today, product)
                )
                conn.commit()
                new_stock = conn.execute("SELECT stock_actual FROM inventario WHERE producto = ?", (product,)).fetchone()["stock_actual"]
            finally:
                conn.close()

            bot.send_message(
                message.chat.id,
                f"✅ <b>Mercancía ingresada</b>\n\n📦 {product}: +{qty} unidades\n📊 Stock actual: <b>{new_stock}</b> uds"
            )
        except ValueError:
            bot.send_message(message.chat.id, "❌ Cantidad inválida.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_inventory_min_product(message):
        if not is_admin(message):
            return
        try:
            product = message.text.strip()
            if product not in PRODUCT_CATALOG:
                bot.send_message(message.chat.id, "❌ Producto no válido.", reply_markup=types.ReplyKeyboardRemove())
                return
            bot.send_message(message.chat.id, f"⚙️ ¿Cuál es el nuevo <b>stock mínimo</b> para {product}?\n(Alerta cuando baje de este número)", reply_markup=types.ReplyKeyboardRemove())
            bot.register_next_step_handler(message, step_inventory_min_save, product)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_inventory_min_save(message, product):
        if not is_admin(message):
            return
        try:
            min_qty = int(message.text.strip())
            conn = get_connection()
            try:
                conn.execute("UPDATE inventario SET stock_minimo = ? WHERE producto = ?", (min_qty, product))
                conn.commit()
            finally:
                conn.close()
            bot.send_message(message.chat.id, f"✅ Stock mínimo de <b>{product}</b> actualizado a <b>{min_qty}</b> uds.")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Número inválido.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /ruta_pie ---------------

    @bot.message_handler(commands=["ruta_pie"])
    def cmd_route_walking(message):
        if not is_admin(message):
            return
        try:
            if not GOOGLE_API_KEY:
                bot.send_message(message.chat.id, "❌ <b>GOOGLE_API_KEY no configurada.</b>")
                return
            bot.send_message(
                message.chat.id,
                "📱 <b>RADAR DE PROSPECCIÓN TERRITORIAL</b>\n\n"
                "🔍 El bot escaneará Google Maps para encontrar\nnegocios reales cerca de tu ubicación.\n\n"
                "📍 Escribe tu <b>punto de partida</b>\n(Ej: Calle 170 con Carrera 9, Bogota):"
            )
            bot.register_next_step_handler(message, step_discovery_origin)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_discovery_origin(message):
        if not is_admin(message):
            return
        try:
            route_data = {"origin_text": message.text.strip()}
            bot.send_message(message.chat.id, "🔍 Geocodificando tu ubicación...")
            lat, lng = geocode_address(route_data["origin_text"])
            if lat is None:
                bot.send_message(message.chat.id, "❌ No pude encontrar esa dirección. Inténtalo con más detalle.")
                return
            route_data["lat"] = lat
            route_data["lng"] = lng

            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            markup.add("🎯 Todos los Targets VIP")
            for key, info in TARGET_BUSINESS_TYPES.items():
                markup.add(f"{info['emoji']} {info['label']}")

            bot.send_message(
                message.chat.id,
                f"✅ Ubicación: {lat:.4f}, {lng:.4f}\n\n🎯 <b>¿Qué tipo de negocio vas a atacar hoy?</b>",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_discovery_target, route_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error al geocodificar: {e}")

    def step_discovery_target(message, route_data):
        if not is_admin(message):
            return
        try:
            selected = message.text.strip()
            if "Todos" in selected:
                route_data["target_keys"] = list(TARGET_BUSINESS_TYPES.keys())
                route_data["target_label"] = "Todos los Targets VIP"
            else:
                for key, info in TARGET_BUSINESS_TYPES.items():
                    if info["label"] in selected:
                        route_data["target_keys"] = [key]
                        route_data["target_label"] = info["label"]
                        break
                else:
                    route_data["target_keys"] = list(TARGET_BUSINESS_TYPES.keys())
                    route_data["target_label"] = "Todos"

            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            for label in SEARCH_RADIUS_OPTIONS:
                markup.add(label)

            bot.send_message(
                message.chat.id,
                "📍 <b>¿Qué radio de búsqueda?</b>\n\nDefine qué tan lejos del punto de partida\ndebe buscar negocios el radar:",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_discovery_radius, route_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_discovery_radius(message, route_data):
        if not is_admin(message):
            return
        try:
            selected = message.text.strip()
            radius = SEARCH_RADIUS_OPTIONS.get(selected, DEFAULT_SEARCH_RADIUS)
            route_data["radius"] = radius

            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            for station_name in TRANSMILENIO_STATIONS:
                markup.add(f"🚏 {station_name}")
            markup.add("📍 Escribir destino manual")

            bot.send_message(
                message.chat.id,
                "🚏 <b>¿A qué estación de TransMilenio regresas?</b>\n(Punto final de tu jornada)",
                reply_markup=markup
            )
            bot.register_next_step_handler(message, step_discovery_destination, route_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_discovery_destination(message, route_data):
        if not is_admin(message):
            return
        try:
            selected = message.text.strip()
            if "Escribir destino" in selected:
                bot.send_message(message.chat.id, "📍 Escribe la <b>dirección de destino final</b>:", reply_markup=types.ReplyKeyboardRemove())
                bot.register_next_step_handler(message, step_discovery_manual_dest, route_data)
                return

            station_name = selected.replace("🚏 ", "").strip()
            if station_name in TRANSMILENIO_STATIONS:
                route_data["destination"] = TRANSMILENIO_STATIONS[station_name]
                route_data["dest_label"] = f"🚏 {station_name}"
            else:
                route_data["destination"] = station_name + ", Bogota"
                route_data["dest_label"] = station_name

            execute_discovery_search(bot, message, route_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    def step_discovery_manual_dest(message, route_data):
        if not is_admin(message):
            return
        try:
            route_data["destination"] = message.text.strip()
            route_data["dest_label"] = message.text.strip()
            execute_discovery_search(bot, message, route_data)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    # --------------- /ruta_camion ---------------

    @bot.message_handler(commands=["ruta_camion"])
    def cmd_route_truck(message):
        if not is_admin(message):
            return
        try:
            conn = get_connection()
            try:
                pending_orders = conn.execute("""
                    SELECT c.nombre, c.direccion FROM pedidos p
                    JOIN clientes c ON p.cliente_id = c.id
                    WHERE p.estado = 'Pendiente' AND c.direccion IS NOT NULL GROUP BY c.id
                """).fetchall()
            finally:
                conn.close()

            if not pending_orders:
                bot.send_message(message.chat.id, "🚚 No hay pedidos pendientes con dirección.")
                return

            bot.send_message(
                message.chat.id,
                f"🚚 <b>RUTA DE ENTREGAS (CAMIÓN)</b>\n\n"
                f"📦 Hay <b>{len(pending_orders)}</b> clientes con pedidos pendientes.\n\n"
                f"📍 Escribe el <b>punto de partida</b>\n(Ej: {COMPANY_ADDRESS}, {COMPANY_CITY}):"
            )
            bot.register_next_step_handler(message, step_route_truck_origin, pending_orders)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error al generar ruta: {e}")

    def step_route_truck_origin(message, pending_orders):
        if not is_admin(message):
            return
        try:
            origin = message.text.strip()
            addresses = [row["direccion"] for row in pending_orders if row["direccion"]]
            links = build_google_maps_links(origin, addresses[:-1], addresses[-1], "driving")

            response = f"🚚 <b>RUTA DE ENTREGAS (CAMIÓN)</b>\n📍 Origen: {origin}\n" + "━" * 28 + "\n\n"
            response += "📦 <b>Entregas:</b>\n"
            for i, row in enumerate(pending_orders, 1):
                response += f"  {i}. {row['nombre']} — {row['direccion']}\n"
            response += "\n"
            for label, url in links:
                response += f"🗺️ <a href='{url}'>{label}</a>\n"
            response += f"\n📌 Total de entregas: {len(addresses)}"

            bot.send_message(message.chat.id, response, disable_web_page_preview=True)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error al generar ruta: {e}")


# =========================================================================
# HELPERS (module-level)
# =========================================================================

def execute_discovery_search(bot, message, route_data):
    """Search Google Places for real businesses and build the prospecting route."""
    try:
        bot.send_message(message.chat.id, "🔍 <b>Escaneando el terreno...</b>\nBuscando negocios reales en Google Maps...", reply_markup=types.ReplyKeyboardRemove())

        lat, lng, radius = route_data["lat"], route_data["lng"], route_data["radius"]
        all_places = []
        seen_ids = set()

        for target_key in route_data["target_keys"]:
            info = TARGET_BUSINESS_TYPES[target_key]
            for keyword in info["search_keywords"]:
                results = search_nearby_places(lat, lng, keyword, radius)
                for place in results:
                    pid = place.get("place_id", "")
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)
                    name = place.get("name", "")
                    if is_blacklisted(name):
                        continue
                    ploc = place.get("geometry", {}).get("location", {})
                    plat, plng = ploc.get("lat", 0), ploc.get("lng", 0)
                    distance = haversine_distance(lat, lng, plat, plng)
                    all_places.append({
                        "name": name, "address": place.get("vicinity", ""),
                        "lat": plat, "lng": plng, "distance": distance,
                        "rating": place.get("rating", 0),
                        "total_ratings": place.get("user_ratings_total", 0),
                        "open_now": place.get("opening_hours", {}).get("open_now", None),
                        "target_type": target_key, "emoji": info["emoji"],
                    })

        if not all_places:
            bot.send_message(message.chat.id, f"📍 No se encontraron negocios de tipo <b>{route_data['target_label']}</b> en un radio de {radius}m.")
            return

        all_places.sort(key=lambda p: p["distance"])
        route_places = all_places[:MAX_DISCOVERY_STOPS]
        remaining = len(all_places) - len(route_places)
        addresses = [p["address"] + ", Bogota" for p in route_places]

        total_time = len(route_places) * MINUTES_PER_STOP
        hours, mins = total_time // 60, total_time % 60

        links = build_google_maps_links(route_data["origin_text"], addresses, route_data["destination"], "walking")

        response = "📱 <b>RADAR DE PROSPECCIÓN TERRITORIAL</b>\n" + "━" * 34 + "\n"
        response += f"📍 Zona: {route_data['origin_text']}\n🎯 Target: {route_data['target_label']}\n"
        response += f"📌 Radio: {radius}m\n🚏 Regreso: {route_data['dest_label']}\n"
        response += f"⏱️ Tiempo estimado: ~{hours}h {mins}min\n"
        response += f"🔍 Negocios encontrados: <b>{len(all_places)}</b>\n📊 En ruta: <b>{len(route_places)}</b>\n"
        response += "━" * 34 + "\n\n📋 <b>NEGOCIOS DESCUBIERTOS (por cercanía):</b>\n\n"

        for i, place in enumerate(route_places, 1):
            dist_label = f"{place['distance']:.0f}m" if place["distance"] < 1000 else f"{place['distance'] / 1000:.1f}km"
            open_icon = "🟢" if place["open_now"] else ("🔴" if place["open_now"] is False else "⚪")
            response += f"{place['emoji']} <b>{i}. {place['name']}</b>\n"
            response += f"   📍 {place['address']}\n   📎 {dist_label} {open_icon}"
            if place["rating"]:
                response += f" ⭐ {place['rating']}"
            if place["total_ratings"]:
                response += f" ({place['total_ratings']} reseñas)"
            response += "\n\n"

        if len(route_data["target_keys"]) == 1:
            target_key = route_data["target_keys"][0]
            pitch = TARGET_BUSINESS_TYPES[target_key]["pitch"]
            response += f"💡 <b>Pitch de venta:</b>\n{pitch}\n\n"

        response += "🗺️ <b>NAVEGACIÓN:</b>\n"
        for label, url in links:
            response += f"  📌 <a href='{url}'>{label}</a>\n"
        if remaining > 0:
            response += f"\n⚠️ Hay <b>{remaining}</b> negocios más fuera de esta ruta."
        response += "\n\n🔥 <i>Busca chimeneas con humo, motos de domiciliarios,</i>"
        response += "\n<i>y dueños que te paguen en efectivo el viernes.</i>"

        bot.send_message(message.chat.id, response, disable_web_page_preview=True)
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Error en búsqueda: {e}")
