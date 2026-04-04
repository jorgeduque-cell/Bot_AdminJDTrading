# -*- coding: utf-8 -*-
"""
JD Trading Oil S.A.S — Database Module
PostgreSQL (Supabase) initialization, migrations, and connection helpers.
Uses psycopg v3 (modern PostgreSQL adapter).
"""
import psycopg
from psycopg.rows import dict_row
import os
from datetime import date
from config import PRODUCT_CATALOG

DATABASE_URL = os.environ["DATABASE_URL"]  # Required — from Supabase


class PgConnection:
    """Wrapper around psycopg connection that mimics sqlite3 interface.
    Provides conn.execute() shorthand and dict-like row access."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, query, params=None):
        """Execute query and return cursor (supports .fetchone(), .fetchall())."""
        cursor = self._conn.cursor(row_factory=dict_row)
        cursor.execute(query, params)
        return cursor

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_connection():
    """Return a wrapped PostgreSQL connection with dict-like rows."""
    conn = psycopg.connect(DATABASE_URL, autocommit=False)
    return PgConnection(conn)


def init_database():
    """Create all tables if they do not exist."""
    conn = psycopg.connect(DATABASE_URL)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            telefono TEXT,
            direccion TEXT,
            tipo_negocio TEXT,
            estado TEXT DEFAULT 'Prospecto',
            fecha_registro DATE,
            ultima_interaccion DATE,
            latitud DOUBLE PRECISION,
            longitud DOUBLE PRECISION,
            dia_visita TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER NOT NULL REFERENCES clientes(id),
            producto TEXT NOT NULL,
            tipo_carga TEXT,
            cantidad INTEGER NOT NULL,
            peso_kg DOUBLE PRECISION,
            costo_compra DOUBLE PRECISION,
            precio_venta DOUBLE PRECISION,
            estado TEXT DEFAULT 'Pendiente',
            estado_pago TEXT DEFAULT 'Pendiente',
            fecha DATE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS finanzas (
            id SERIAL PRIMARY KEY,
            tipo TEXT NOT NULL,
            concepto TEXT,
            monto DOUBLE PRECISION NOT NULL,
            fecha DATE,
            pedido_id INTEGER REFERENCES pedidos(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventario (
            id SERIAL PRIMARY KEY,
            producto TEXT NOT NULL UNIQUE,
            stock_actual INTEGER DEFAULT 0,
            stock_minimo INTEGER DEFAULT 5,
            ultima_actualizacion DATE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notas_cliente (
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER NOT NULL REFERENCES clientes(id),
            texto TEXT NOT NULL,
            fecha DATE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS precios (
            id SERIAL PRIMARY KEY,
            producto TEXT NOT NULL UNIQUE,
            precio_compra DOUBLE PRECISION NOT NULL DEFAULT 0,
            precio_venta DOUBLE PRECISION NOT NULL DEFAULT 0,
            fecha_actualizacion DATE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metas (
            id SERIAL PRIMARY KEY,
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
                "INSERT INTO precios (producto, precio_compra, precio_venta, fecha_actualizacion) VALUES (%s, 0, 0, %s)",
                (product_name, today)
            )

    # Seed inventory with default products if empty
    cursor.execute("SELECT COUNT(*) FROM inventario")
    if cursor.fetchone()[0] == 0:
        today = date.today().isoformat()
        for product_name in PRODUCT_CATALOG:
            cursor.execute(
                "INSERT INTO inventario (producto, stock_actual, stock_minimo, ultima_actualizacion) VALUES (%s, 0, 5, %s)",
                (product_name, today)
            )

    conn.commit()
    conn.close()
