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
