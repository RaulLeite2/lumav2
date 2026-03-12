from __future__ import annotations

import asyncpg


class AICooldownService:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_usage_snapshot(self, guild_id: int, user_id: int) -> dict:
        async with self.pool.acquire() as conn:
            user_last_minute = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM ai_usage_events
                WHERE guild_id = $1
                  AND user_id = $2
                  AND created_at >= (CURRENT_TIMESTAMP - INTERVAL '1 minute')
                """,
                guild_id,
                user_id,
            )

            guild_last_day = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM ai_usage_events
                WHERE guild_id = $1
                  AND created_at >= (CURRENT_TIMESTAMP - INTERVAL '1 day')
                """,
                guild_id,
            )

        return {
            "user_last_minute": int(user_last_minute or 0),
            "guild_last_day": int(guild_last_day or 0),
        }

    async def register_usage(self, guild_id: int, user_id: int, used_cached_response: bool) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO ai_usage_events (guild_id, user_id, used_cached_response)
                VALUES ($1, $2, $3)
                """,
                guild_id,
                user_id,
                used_cached_response,
            )
