from __future__ import annotations

import asyncpg


class StatsService:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def increment_command(self, guild_id: int, command_name: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO command_usage_stats (guild_id, command_name, used_count)
                VALUES ($1, $2, 1)
                ON CONFLICT (guild_id, command_name)
                DO UPDATE SET used_count = command_usage_stats.used_count + 1, updated_at = CURRENT_TIMESTAMP
                """,
                guild_id,
                command_name,
            )

    async def increment_metric(self, guild_id: int, metric_name: str, amount: int = 1) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO metric_counters (guild_id, metric_name, metric_value)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id, metric_name)
                DO UPDATE SET metric_value = metric_counters.metric_value + $3, updated_at = CURRENT_TIMESTAMP
                """,
                guild_id,
                metric_name,
                amount,
            )

    async def get_guild_overview(self, guild_id: int) -> dict:
        async with self.pool.acquire() as conn:
            commands_total = await conn.fetchval(
                "SELECT COALESCE(SUM(used_count), 0) FROM command_usage_stats WHERE guild_id = $1",
                guild_id,
            )

            metrics_rows = await conn.fetch(
                "SELECT metric_name, metric_value FROM metric_counters WHERE guild_id = $1",
                guild_id,
            )

            top_commands = await conn.fetch(
                """
                SELECT command_name, used_count
                FROM command_usage_stats
                WHERE guild_id = $1
                ORDER BY used_count DESC
                LIMIT 10
                """,
                guild_id,
            )

        metrics = {row["metric_name"]: row["metric_value"] for row in metrics_rows}

        return {
            "commands_total": commands_total or 0,
            "metrics": metrics,
            "top_commands": top_commands,
        }
