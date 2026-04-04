# -*- coding: utf-8 -*-
"""
JD Trading Oil S.A.S — Database Module
SQLite initialization, migrations, and connection helpers.
"""
import sqlite3
import os
from datetime import date
from config import PRODUCT_CATALOG

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "jd_trading.db")
)


def get_connection():
    """Return a new SQLite connection with Row factory, FK enforcement, and WAL mode."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_database():
    """Create all tables if they do not exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT,
            direccion TEXT,
            tipo_negocio TEXT,
            estado TEXT DEFAULT 'Prospecto',
            fecha_registro DATE,
            ultima_interaccion DATE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            producto TEXT NOT NULL,
            tipo_carga TEXT,
            cantidad INTEGER NOT NULL,
            peso_kg REAL,
            costo_compra REAL,
            precio_venta REAL,
            estado TEXT DEFAULT 'Pendiente',
            fecha DATE,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS finanzas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            concepto TEXT,
            monto REAL NOT NULL,
            fecha DATE,
            pedido_id INTEGER,
            FOREIGN KEY (pedido_id) REFERENCES pedidos(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto TEXT NOT NULL UNIQUE,
            stock_actual INTEGER DEFAULT 0,
            stock_minimo INTEGER DEFAULT 5,
            ultima_actualizacion DATE
        )
    """)

    # --- MIGRATIONS (safe to run multiple times) ---
    try:
        cursor.execute("ALTER TABLE finanzas ADD COLUMN pedido_id INTEGER")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE clientes ADD COLUMN latitud REAL")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE clientes ADD COLUMN longitud REAL")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE clientes ADD COLUMN dia_visita TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE pedidos ADD COLUMN estado_pago TEXT DEFAULT 'Pendiente'")
    except sqlite3.OperationalError:
        pass

    # --- NEW TABLES (Feature Sprint) ---

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notas_cliente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            texto TEXT NOT NULL,
            fecha DATE,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS precios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto TEXT NOT NULL UNIQUE,
            precio_compra REAL NOT NULL DEFAULT 0,
            precio_venta REAL NOT NULL DEFAULT 0,
            fecha_actualizacion DATE
        )
    """)

    # Migration: Drop old metas table if it has the old schema (tipo/meta/fecha_inicio/fecha_fin)
    try:
        old_cols = [row[1] for row in cursor.execute("PRAGMA table_info(metas)").fetchall()]
        if "tipo" in old_cols or "fecha_inicio" in old_cols:
            cursor.execute("DROP TABLE metas")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto TEXT NOT NULL,
            meta_unidades INTEGER NOT NULL DEFAULT 0,
            mes TEXT NOT NULL,
            fecha_creacion DATE
        )
    """)

    # Seed prices from catalog if empty
    cursor.execute("SELECT COUNT(*) FROM precios")
    if cursor.fetchone()[0] == 0:
        today = date.today().isoformat()
        for product_name in PRODUCT_CATALOG:
            cursor.execute(
                "INSERT INTO precios (producto, precio_compra, precio_venta, fecha_actualizacion) VALUES (?, 0, 0, ?)",
                (product_name, today)
            )

    # Seed inventory with default products if empty
    cursor.execute("SELECT COUNT(*) FROM inventario")
    if cursor.fetchone()[0] == 0:
        today = date.today().isoformat()
        for product_name in PRODUCT_CATALOG:
            cursor.execute(
                "INSERT INTO inventario (producto, stock_actual, stock_minimo, ultima_actualizacion) VALUES (?, 0, 5, ?)",
                (product_name, today)
            )

    conn.commit()
    conn.close()

