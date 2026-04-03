# -*- coding: utf-8 -*-
"""
JD Trading Oil S.A.S — Utility Functions
Security, text splitting, Google Maps API helpers, and geo calculations.
"""
import re
import math
import json
import urllib.request
from urllib.parse import quote, urlencode

from config import ADMIN_ID, GOOGLE_API_KEY, BLACKLIST_KEYWORDS, MAX_WAYPOINTS, logger


# =========================================================================
# SECURITY
# =========================================================================

def is_admin(message):
    """Validate that the sender is the authorized admin."""
    if message.from_user.id != ADMIN_ID:
        logger.warning(
            "UNAUTHORIZED ACCESS ATTEMPT — User: %s (ID: %s) tried command: %s",
            message.from_user.username or "unknown",
            message.from_user.id,
            message.text or "N/A"
        )
        return False
    return True


# =========================================================================
# TEXT HELPERS
# =========================================================================

def safe_split(text, max_len=4000):
    """Split text for Telegram without breaking HTML tags."""
    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        idx = text[:max_len].rfind("\n\n")
        if idx == -1:
            idx = text[:max_len].rfind("\n")
        if idx == -1:
            idx = max_len
        parts.append(text[:idx])
        text = text[idx:].lstrip("\n")
    return parts


def sanitize_phone_co(raw_phone):
    """Sanitize a Colombian phone number for WhatsApp links."""
    phone = re.sub(r"[^0-9]", "", (raw_phone or "").strip())
    if phone.startswith("57") and len(phone) > 10:
        pass  # Already has country code
    elif len(phone) == 10:
        phone = "57" + phone
    elif len(phone) == 7:
        phone = "571" + phone  # Bogota landline
    return phone


# =========================================================================
# GOOGLE MAPS API
# =========================================================================

def google_api_get(base_url, params):
    """Make a GET request to a Google API and return parsed JSON."""
    query = urlencode(params)
    url = f"{base_url}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "JDTradingBot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def geocode_address(address):
    """Convert an address string to (lat, lng) using Google Geocoding API."""
    data = google_api_get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        {"address": address, "region": "co", "key": GOOGLE_API_KEY}
    )
    if data.get("status") == "OK" and data.get("results"):
        loc = data["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    return None, None


def search_nearby_places(lat, lng, keyword, radius=1500):
    """Search for businesses near coordinates using Google Places Nearby Search."""
    data = google_api_get(
        "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
        {
            "location": f"{lat},{lng}",
            "radius": radius,
            "keyword": keyword,
            "language": "es",
            "key": GOOGLE_API_KEY,
        }
    )
    if data.get("status") in ("OK", "ZERO_RESULTS"):
        return data.get("results", [])
    return []


def haversine_distance(lat1, lng1, lat2, lng2):
    """Calculate distance in meters between two coordinates."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def is_blacklisted(name):
    """Check if a business name matches the anti-target blacklist."""
    lower_name = name.lower()
    return any(kw in lower_name for kw in BLACKLIST_KEYWORDS)


# =========================================================================
# ROUTE BUILDING
# =========================================================================

def build_google_maps_url(origin, waypoints, destination, travel_mode):
    """Build a single Google Maps direction URL. Accepts strings or (lat,lng) tuples."""
    def _encode(point):
        if isinstance(point, (list, tuple)) and len(point) == 2:
            return f"{point[0]},{point[1]}"
        return quote(str(point), safe=",")

    url = f"https://www.google.com/maps/dir/?api=1&travelmode={travel_mode}"
    url += f"&origin={_encode(origin)}"

    if waypoints:
        encoded_wps = "|".join([_encode(w) for w in waypoints])
        url += f"&waypoints={encoded_wps}"

    url += f"&destination={_encode(destination)}"
    return url


def build_walking_route(origin, stops, destination, stop_names=None):
    """
    Build Google Maps walking route URLs with clear segment labels.

    Args:
        origin: Starting point (str or (lat,lng))
        stops: List of waypoints ((lat,lng) tuples or address strings)
        destination: End point (str or (lat,lng))
        stop_names: Optional list of names for each stop (for labels)

    Returns:
        List of (label, url) tuples
    """
    if not stops:
        url = build_google_maps_url(origin, [], destination, "walking")
        return [("🗺️ Ruta directa al destino", url)]

    links = []

    if len(stops) <= MAX_WAYPOINTS:
        url = build_google_maps_url(origin, stops, destination, "walking")
        total = len(stops)
        links.append((f"🗺️ Ruta completa ({total} paradas)", url))
    else:
        # Split into segments with clear chaining
        chunks = [stops[i:i + MAX_WAYPOINTS] for i in range(0, len(stops), MAX_WAYPOINTS)]
        current_origin = origin
        accumulated = 0

        for idx, chunk in enumerate(chunks):
            is_last = (idx == len(chunks) - 1)

            if is_last:
                chunk_dest = destination
                dest_label = "→ DESTINO FINAL"
            else:
                chunk_dest = chunk[-1]
                chunk = chunk[:-1]
                dest_label = f"→ Parada #{accumulated + len(chunk) + 1}"

            url = build_google_maps_url(current_origin, chunk, chunk_dest, "walking")
            start_num = accumulated + 1
            end_num = accumulated + len(chunk) + (1 if not is_last else 0)
            label = f"🗺️ Tramo {idx + 1}: Paradas {start_num}-{end_num} {dest_label}"
            links.append((label, url))

            accumulated += len(chunk) + (1 if not is_last else 0)
            if not is_last:
                current_origin = chunk_dest

    return links


def build_google_maps_links(origin, addresses, destination, travel_mode):
    """Build Google Maps URLs for driving routes (legacy, used by /ruta_camion)."""
    if not addresses and not destination:
        return []

    all_stops = list(addresses)
    links = []

    if len(all_stops) <= MAX_WAYPOINTS:
        url = build_google_maps_url(origin, all_stops, destination, travel_mode)
        links.append(("Ruta", url))
    else:
        chunks = [all_stops[i:i + MAX_WAYPOINTS] for i in range(0, len(all_stops), MAX_WAYPOINTS)]
        for idx, chunk in enumerate(chunks):
            if idx == len(chunks) - 1:
                url = build_google_maps_url(origin, chunk, destination, travel_mode)
            else:
                last_stop = chunk.pop()
                url = build_google_maps_url(origin, chunk, last_stop, travel_mode)
                origin = last_stop
            links.append((f"Ruta {idx + 1}", url))

    return links

