from __future__ import annotations

import discord
import asyncpg
import json


class AuditLogger:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def log(
        self,
        guild: discord.Guild,
        action_name: str,
        executor: discord.abc.User | None,
        target: discord.abc.User | None = None,
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        if guild is None:
            return

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_logs (guild_id, action_name, executor_id, target_id, reason, metadata)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                """,
                guild.id,
                action_name,
                executor.id if executor else None,
                target.id if target else None,
                reason,
                json.dumps(metadata or {}),
            )

            log_channel_id = await conn.fetchval(
                "SELECT log_channel_id FROM guilds WHERE guild_id = $1",
                guild.id,
            )

        if not log_channel_id:
            return

        log_channel = guild.get_channel(log_channel_id)
        if not isinstance(log_channel, discord.TextChannel):
            return

        embed = discord.Embed(
            title="🧾 Auditoria do Bot",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Ação", value=action_name, inline=False)
        embed.add_field(name="Executor", value=f"{executor.mention if executor else 'Desconhecido'}", inline=True)
        embed.add_field(name="Alvo", value=f"{target.mention if target else 'N/A'}", inline=True)
        embed.add_field(name="Motivo", value=reason or "Não informado", inline=False)
        if metadata:
            pretty_meta = "\n".join(f"• {k}: {v}" for k, v in metadata.items())
            embed.add_field(name="Metadados", value=pretty_meta[:1024], inline=False)

        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            return
