# -*- coding: utf-8 -*-
"""
JD Trading Oil S.A.S — Handler Registry
Registers all command handler modules with the bot instance.
"""
from handlers import admin, crm, sales, logistics, documents, finance


def register_all(bot):
    """Register all handler modules with the bot instance."""
    admin.register(bot)
    crm.register(bot)
    sales.register(bot)
    logistics.register(bot)
    documents.register(bot)
    finance.register(bot)
