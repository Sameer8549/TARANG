"""
Database initialisation and async SQLite connection.
Uses aiosqlite for non-blocking DB access.
"""

import aiosqlite
import os
import logging

logger = logging.getLogger("tarang.db")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "tarang.db")


async def get_db() -> aiosqlite.Connection:
    """Dependency: yields a DB connection."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def init_db():
    """Create all tables on startup if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS vessels (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                owner       TEXT,
                phone       TEXT,
                lat         REAL,
                lng         REAL,
                last_seen   TEXT,
                status      TEXT DEFAULT 'active',
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id              TEXT PRIMARY KEY,
                vessel_id       TEXT NOT NULL,
                vessel_name     TEXT,
                lat             REAL NOT NULL,
                lng             REAL NOT NULL,
                alert_type      TEXT NOT NULL,
                severity        TEXT DEFAULT 'medium',
                status          TEXT DEFAULT 'active',
                ai_summary      TEXT,
                ai_responder    TEXT,
                distance_km     REAL,
                weather_risk    TEXT,
                created_at      TEXT DEFAULT (datetime('now')),
                resolved_at     TEXT,
                FOREIGN KEY (vessel_id) REFERENCES vessels(id)
            );

            CREATE TABLE IF NOT EXISTS mesh_hops (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id    TEXT NOT NULL,
                relay_id    TEXT,
                lat         REAL,
                lng         REAL,
                rssi        INTEGER,
                hopped_at   TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (alert_id) REFERENCES alerts(id)
            );

            CREATE TABLE IF NOT EXISTS dispatch_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id    TEXT NOT NULL,
                action      TEXT NOT NULL,
                operator    TEXT DEFAULT 'system',
                note        TEXT,
                logged_at   TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (alert_id) REFERENCES alerts(id)
            );

            CREATE TABLE IF NOT EXISTS weather_cache (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                lat         REAL,
                lng         REAL,
                data        TEXT,
                fetched_at  TEXT DEFAULT (datetime('now'))
            );

            -- Seed demo vessels
            INSERT OR IGNORE INTO vessels (id, name, owner, phone, lat, lng, last_seen, status)
            VALUES
                ('VES-001', 'Mangala Devi',   'Ravi Kumar',    '+919876543210', 12.8890, 74.8420, datetime('now'), 'active'),
                ('VES-002', 'Saraswathi',     'Suresh Naik',   '+919845210987', 12.9200, 74.7980, datetime('now'), 'active'),
                ('VES-003', 'Lakshmi Prasad', 'Gangadhar Rao', '+919731234567', 12.7650, 74.9100, datetime('now'), 'active'),
                ('VES-004', 'Sea Hawk',       'Mohan Das',     '+919632145870', 12.8100, 74.6800, datetime('now'), 'active'),
                ('VES-005', 'Blue Pearl',     'Krishnappa',    '+919741258963', 12.9500, 74.5500, datetime('now'), 'active');
        """)
        await db.commit()
        logger.info("✅ DB schema initialised and demo vessels seeded")
