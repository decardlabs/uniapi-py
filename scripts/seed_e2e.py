"""E2E test seed data — creates channels and other fixtures expected by Playwright tests.

Run after the main seed script (which creates root user and options).
Usage:
    SQLITE_PATH=/tmp/uniapi_ci.db python3 scripts/seed_e2e.py
"""
from __future__ import annotations

import asyncio
import json
import os
import time

os.environ.setdefault("SQLITE_PATH", "/tmp/uniapi_ci.db")

from app.database import async_session_factory
from app.models.channel import Channel


async def seed_e2e():
    now_ms = int(time.time() * 1000)
    now_s = int(time.time())

    async with async_session_factory() as d:
        # ── Channel 1: Minimaxchannel (MiniMax, type=27) ────────
        ch1 = await d.get(Channel, 1)
        if not ch1:
            ch1 = Channel(
                id=1,
                name="Minimaxchannel",
                type=27,
                key="sk-minimax-e2e-test-key-placeholder",
                status=1,
                group="default",
                weight=1,
                models="MiniMax-M3",
                model_configs=json.dumps({
                    "MiniMax-M3": {
                        "input_price": 5.0,
                        "output_price": 15.0,
                        "cache_hit_price": 1.0,
                        "max_tokens": 128000,
                    },
                }),
                created_time=now_s,
                created_at=now_ms,
                updated_at=now_ms,
            )
            d.add(ch1)
            print("[SeedE2E] Created Channel 1: Minimaxchannel")

        # ── Channel 2: Minimaxchannel (#2) (MiniMax, type=27) ───
        ch2 = await d.get(Channel, 2)
        if not ch2:
            ch2 = Channel(
                id=2,
                name="Minimaxchannel",
                type=27,
                key="sk-minimax2-e2e-test-key-placeholder",
                status=1,
                group="default",
                weight=1,
                models="MiniMax-M3",
                model_configs=json.dumps({
                    "MiniMax-M3": {
                        "input_price": 5.0,
                        "output_price": 15.0,
                        "cache_hit_price": 1.0,
                        "max_tokens": 128000,
                    },
                }),
                created_time=now_s,
                created_at=now_ms,
                updated_at=now_ms,
            )
            d.add(ch2)
            print("[SeedE2E] Created Channel 2: Minimaxchannel (#2)")

        # ── Channel 3: MainChannel (DeepSeek, type=39) ──────────
        ch3 = await d.get(Channel, 3)
        if not ch3:
            ch3 = Channel(
                id=3,
                name="MainChannel",
                type=39,
                key="sk-deepseek-e2e-test-key-placeholder",
                status=1,
                group="default",
                weight=1,
                models="deepseek-v4-flash",
                model_configs=json.dumps({
                    "deepseek-v4-flash": {
                        "input_price": 1.0,
                        "output_price": 2.0,
                        "cache_hit_price": 0.02,
                        "max_tokens": 384000,
                    },
                }),
                created_time=now_s,
                created_at=now_ms,
                updated_at=now_ms,
            )
            d.add(ch3)
            print("[SeedE2E] Created Channel 3: MainChannel (DeepSeek)")

        await d.commit()

    print("[SeedE2E] E2E test data seeded successfully")


if __name__ == "__main__":
    asyncio.run(seed_e2e())
