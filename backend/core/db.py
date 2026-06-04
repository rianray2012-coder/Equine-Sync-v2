"""Shared Mongo client + database handle (Phase 3G).

Single source of truth for the application's database connection so the core
modules (auth, analytics, helpers, lifespan) and ``server.py`` all share one
client instead of constructing their own.

Reads ``MONGO_URL`` / ``DB_NAME`` at import time. ``server.py`` loads ``.env``
and validates config BEFORE importing this module, so ``os.environ`` is fully
populated here.
"""
import os

from motor.motor_asyncio import AsyncIOMotorClient

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]
