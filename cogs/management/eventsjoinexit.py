import discord
from discord.ext import commands

from scripts.db import Database

class EventsJoinExit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _fetch_join_exit_row(self, guild_id: int):
        db = Database(self.bot.pool)
        return await db.fetchrow(
            """
            SELECT join_message, isenabled_join, exit_message, isenabled_exit
            FROM joinexitmessages
            WHERE guild_id = $1
            """,
            guild_id,
        )

    @staticmethod
    def _render_message(template: str, member: discord.Member) -> str:
        return (
            str(template or "")
            .replace("{member}", member.mention)
            .replace("{guild}", member.guild.name)
        )

    @staticmethod
    def _resolve_channel(guild: discord.Guild) -> discord.TextChannel | None:
        bot_member = guild.me
        if bot_member is None:
            return None

        if isinstance(guild.system_channel, discord.TextChannel):
            perms = guild.system_channel.permissions_for(bot_member)
            if perms.send_messages:
                return guild.system_channel

        for channel in guild.text_channels:
            perms = channel.permissions_for(bot_member)
            if perms.send_messages:
                return channel
        return None

    async def _send_configured_message(self, member: discord.Member, *, is_join: bool) -> None:
        row = await self._fetch_join_exit_row(member.guild.id)
        if not row:
            return

        if is_join:
            enabled = bool(row.get("isenabled_join"))
            template = row.get("join_message")
        else:
            enabled = bool(row.get("isenabled_exit"))
            template = row.get("exit_message")

        if not enabled or not template:
            return

        channel = self._resolve_channel(member.guild)
        if channel is None:
            return

        content = self._render_message(str(template), member)
        if not content.strip():
            return

        try:
            await channel.send(content)
        except (discord.Forbidden, discord.HTTPException):
            return
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild is None or member.bot:
            return
        await self._send_configured_message(member, is_join=True)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.guild is None or member.bot:
            return
        await self._send_configured_message(member, is_join=False)


async def setup(bot):
    await bot.add_cog(EventsJoinExit(bot))
