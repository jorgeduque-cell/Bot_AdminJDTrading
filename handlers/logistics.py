# -*- coding: utf-8 -*-
"""
Handlers: Logistics — Routing & Inventory
Commands: /ruta_pie, /ruta_camion, /ruta_semanal, /inventario
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
    haversine_distance, is_blacklisted, build_google_maps_links,
    build_walking_route
)

WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
WEEKDAY_EMOJIS = {"Lunes": "1️⃣", "Martes": "2️⃣", "Miércoles": "3️⃣", "Jueves": "4️⃣", "Viernes": "5️⃣", "Sábado": "6️⃣"}
DAY_INDEX_MAP = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles", "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado"}


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
                    "UPDATE inventario SET stock_actual = stock_actual + %s, ultima_actualizacion = %s WHERE producto = %s",
                    (qty, today, product)
                )
                conn.commit()
                new_stock = conn.execute("SELECT stock_actual FROM inventario WHERE producto = %s", (product,)).fetchone()["stock_actual"]
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
                conn.execute("UPDATE inventario SET stock_minimo = %s WHERE producto = %s", (min_qty, product))
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

    # --------------- /ruta_semanal ---------------

    @bot.message_handler(commands=["ruta_semanal"])
    def cmd_weekly_route(message):
        if not is_admin(message):
            return
        try:
            import datetime
            today_name = DAY_INDEX_MAP.get(datetime.datetime.now().strftime("%A"), None)

            # Show summary of clients per day
            conn = get_connection()
            try:
                summary = ""
                for day in WEEKDAYS:
                    count = conn.execute(
                        "SELECT COUNT(*) as c FROM clientes WHERE dia_visita = %s AND latitud IS NOT NULL", (day,)
                    ).fetchone()["c"]
                    today_mark = " ← HOY" if day == today_name else ""
                    summary += f"  {WEEKDAY_EMOJIS[day]} {day}: <b>{count}</b> clientes{today_mark}\n"

                no_day = conn.execute(
                    "SELECT COUNT(*) as c FROM clientes WHERE dia_visita IS NULL AND estado = 'Activo'"
                ).fetchone()["c"]
                summary += f"  ❓ Sin asignar: {no_day} clientes activos\n"
            finally:
                conn.close()

            separator = "━" * 30

            markup = types.InlineKeyboardMarkup(row_width=2)
            if today_name and today_name in WEEKDAYS:
                markup.add(types.InlineKeyboardButton(f"📍 Ruta de HOY ({today_name})", callback_data=f"ruta_dia:{today_name}"))
            for day in WEEKDAYS:
                markup.add(types.InlineKeyboardButton(f"{WEEKDAY_EMOJIS[day]} {day}", callback_data=f"ruta_dia:{day}"))

            bot.send_message(
                message.chat.id,
                f"📅 <b>RUTAS SEMANALES FIJAS</b>\n{separator}\n\n{summary}\n¿Qué día deseas ver?",
                reply_markup=markup
            )
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("ruta_dia:"))
    def handle_ruta_dia_callback(call):
        """Handle weekly route day selection via inline buttons."""
        try:
            bot.answer_callback_query(call.id)
            chosen_day = call.data.replace("ruta_dia:", "")
            chat_id = call.message.chat.id

            conn = get_connection()
            try:
                clients = conn.execute("""
                    SELECT id, nombre, direccion, telefono, tipo_negocio, latitud, longitud
                    FROM clientes
                    WHERE dia_visita = %s AND latitud IS NOT NULL AND longitud IS NOT NULL
                    ORDER BY nombre
                """, (chosen_day,)).fetchall()
            finally:
                conn.close()

            if not clients:
                bot.send_message(
                    chat_id,
                    f"📭 No hay clientes geolocalizados asignados al <b>{chosen_day}</b>.\n\n"
                    "Usa /asignar_dia para asignar clientes a un día."
                )
                return

            # Nearest-neighbor sort for optimal walking path
            ordered = []
            remaining = list(clients)
            # Start from warehouse
            current_lat, current_lng = geocode_address(f"{COMPANY_ADDRESS}, {COMPANY_CITY}")
            if current_lat is None:
                current_lat, current_lng = 4.7110, -74.0721  # Bogota fallback

            while remaining:
                best_idx = 0
                best_dist = haversine_distance(current_lat, current_lng, remaining[0]["latitud"], remaining[0]["longitud"])
                for i in range(1, len(remaining)):
                    d = haversine_distance(current_lat, current_lng, remaining[i]["latitud"], remaining[i]["longitud"])
                    if d < best_dist:
                        best_dist = d
                        best_idx = i
                c = remaining.pop(best_idx)
                ordered.append({"client": c, "walk_distance": best_dist})
                current_lat, current_lng = c["latitud"], c["longitud"]

            # Build route
            total_walk = sum(item["walk_distance"] for item in ordered) / 1000
            stop_coords = [(item["client"]["latitud"], item["client"]["longitud"]) for item in ordered]
            links = build_walking_route(
                f"{COMPANY_ADDRESS}, {COMPANY_CITY}",
                stop_coords,
                f"{COMPANY_ADDRESS}, {COMPANY_CITY}"
            )

            # Build message
            response = f"📅 <b>RUTA DEL {chosen_day.upper()}</b>\n"
            response += "━" * 30 + "\n\n"
            response += f"👥 <b>{len(ordered)}</b> clientes | 🚶 ~{total_walk:.1f} km\n\n"

            response += f"🟢 <b>SALIDA:</b> {COMPANY_ADDRESS}\n"
            response += "     │\n"

            for i, item in enumerate(ordered, 1):
                c = item["client"]
                walk = item["walk_distance"]
                walk_label = f"{walk:.0f}m" if walk < 1000 else f"{walk/1000:.1f}km"

                response += f"     ↓ 🚶 {walk_label}\n"
                response += f"📍 <b>{i}. {c['nombre']}</b>\n"
                response += f"     {c['direccion']}\n"
                response += f"     📱 {c['telefono'] or 'Sin tel.'} | 🏪 {c['tipo_negocio'] or ''}\n"
                if i < len(ordered):
                    response += "     │\n"

            response += "     │\n"
            response += "     ↓ 🚶 regreso\n"
            response += f"🔴 <b>REGRESO:</b> {COMPANY_ADDRESS}\n\n"

            response += "━" * 30 + "\n"
            response += "📲 <b>ABRIR EN GOOGLE MAPS:</b>\n\n"
            for label, url in links:
                response += f"  <a href='{url}'>{label}</a>\n"

            bot.send_message(chat_id, response, disable_web_page_preview=True)
        except Exception as e:
            bot.send_message(call.message.chat.id, f"⚠️ Error: {e}")


# =========================================================================
# HELPERS (module-level)
# =========================================================================

def execute_discovery_search(bot, message, route_data):
    """Search Google Places for real businesses and build a logical walking route."""
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
                        "name": name,
                        "address": place.get("vicinity", ""),
                        "lat": plat,
                        "lng": plng,
                        "distance_from_origin": distance,
                        "rating": place.get("rating", 0),
                        "total_ratings": place.get("user_ratings_total", 0),
                        "open_now": place.get("opening_hours", {}).get("open_now", None),
                        "target_type": target_key,
                        "emoji": info["emoji"],
                    })

        if not all_places:
            bot.send_message(message.chat.id, f"📍 No se encontraron negocios de tipo <b>{route_data['target_label']}</b> en un radio de {radius}m.")
            return

        # ============================================================
        # NEAREST-NEIGHBOR SORTING (creates a logical walking path)
        # Instead of sorting by distance to origin (star pattern),
        # we greedily pick the closest unvisited place from current pos.
        # ============================================================
        candidates = list(all_places)
        ordered_route = []
        current_lat, current_lng = lat, lng

        while candidates and len(ordered_route) < MAX_DISCOVERY_STOPS:
            # Find nearest unvisited place from current position
            best_idx = 0
            best_dist = haversine_distance(current_lat, current_lng, candidates[0]["lat"], candidates[0]["lng"])
            for i in range(1, len(candidates)):
                d = haversine_distance(current_lat, current_lng, candidates[i]["lat"], candidates[i]["lng"])
                if d < best_dist:
                    best_dist = d
                    best_idx = i

            chosen = candidates.pop(best_idx)
            chosen["walk_distance"] = best_dist  # distance from previous stop
            ordered_route.append(chosen)
            current_lat, current_lng = chosen["lat"], chosen["lng"]

        remaining = len(all_places) - len(ordered_route)

        # Calculate total walking distance (sum of all segments)
        total_walk_m = sum(p["walk_distance"] for p in ordered_route)
        total_walk_km = total_walk_m / 1000
        total_time = len(ordered_route) * MINUTES_PER_STOP + int(total_walk_m / 80)  # ~80m/min walking
        hours, mins = total_time // 60, total_time % 60

        # Build Google Maps links using exact coordinates
        from utils import build_walking_route
        stop_coords = [(p["lat"], p["lng"]) for p in ordered_route]
        links = build_walking_route(
            route_data["origin_text"],
            stop_coords,
            route_data["destination"]
        )

        # ============================================================
        # BUILD THE OUTPUT MESSAGE
        # ============================================================
        response = "📱 <b>RADAR DE PROSPECCIÓN TERRITORIAL</b>\n"
        response += "━" * 34 + "\n\n"

        # ---- RESUMEN ----
        response += f"📍 <b>Zona:</b> {route_data['origin_text']}\n"
        response += f"🎯 <b>Target:</b> {route_data['target_label']}\n"
        response += f"📌 <b>Radio:</b> {radius}m\n"
        response += f"🔍 <b>Encontrados:</b> {len(all_places)} negocios\n"
        response += f"📊 <b>En ruta:</b> {len(ordered_route)} paradas\n"
        response += f"🚶 <b>Distancia total:</b> ~{total_walk_km:.1f} km\n"
        response += f"⏱️ <b>Tiempo estimado:</b> ~{hours}h {mins}min\n\n"

        # ---- FLUJO VISUAL DE LA RUTA ----
        response += "🗺️ <b>RECORRIDO PASO A PASO:</b>\n"
        response += "━" * 34 + "\n\n"

        # START
        response += f"🟢 <b>INICIO:</b> {route_data['origin_text']}\n"
        response += "     │\n"

        # STOPS (in walking order)
        for i, place in enumerate(ordered_route, 1):
            walk_label = f"{place['walk_distance']:.0f}m" if place["walk_distance"] < 1000 else f"{place['walk_distance'] / 1000:.1f}km"
            open_icon = "🟢" if place["open_now"] else ("🔴" if place["open_now"] is False else "⚪")

            response += f"     ↓ 🚶 {walk_label}\n"
            response += f"📍 <b>{i}. {place['name']}</b> {place['emoji']}\n"
            response += f"     {place['address']}\n"
            response += f"     {open_icon}"
            if place["rating"]:
                response += f" ⭐ {place['rating']}"
            if place["total_ratings"]:
                response += f" ({place['total_ratings']} reseñas)"
            response += "\n"

            if i < len(ordered_route):
                response += "     │\n"

        # END
        response += "     │\n"
        response += "     ↓ 🚶 caminar a estación\n"
        response += f"🔴 <b>FIN:</b> {route_data['dest_label']}\n\n"

        # ---- PITCH ----
        if len(route_data["target_keys"]) == 1:
            target_key = route_data["target_keys"][0]
            pitch = TARGET_BUSINESS_TYPES[target_key]["pitch"]
            response += f"💡 <b>Pitch de venta:</b>\n{pitch}\n\n"

        # ---- LINKS DE NAVEGACIÓN ----
        response += "━" * 34 + "\n"
        response += "📲 <b>ABRIR EN GOOGLE MAPS:</b>\n\n"
        for label, url in links:
            response += f"  <a href='{url}'>{label}</a>\n"

        if remaining > 0:
            response += f"\n⚠️ Hay <b>{remaining}</b> negocios más fuera de esta ruta."

        response += "\n\n🔥 <i>Busca chimeneas con humo, motos de domiciliarios,</i>"
        response += "\n<i>y dueños que te paguen en efectivo el viernes.</i>"

        bot.send_message(message.chat.id, response, disable_web_page_preview=True)
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Error en búsqueda: {e}")

