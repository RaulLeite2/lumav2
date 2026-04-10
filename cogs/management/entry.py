import discord
from discord.ext import commands
from scripts.db import Database

class Entry(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    @staticmethod
    def _render_template(template: str, member: discord.Member) -> str:
        # Convert escaped sequences saved by web forms into real formatting.
        text = str(template or "")
        text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")
        return (
            text.replace("{member}", member.mention)
            .replace("{guild}", member.guild.name)
            .replace("{user}", member.display_name)
            .replace("{username}", member.name)
        )

    @commands.Cog.listener()
    async def on_member_join(self, member, guild=None):
        guild = guild or member.guild if guild else None
        if guild is None:
            return

        db = Database(self.bot.pool)
        row = await db.fetchrow(
            """
            SELECT join_message
            FROM joinexitmessages
            WHERE guild_id = $1
              AND isenabled_join = TRUE
              AND join_message IS NOT NULL
            """,
            member.guild.id,
        )
        if not row:
            return

        message = self._render_template(row["join_message"], member)
        if not message.strip():
            return

        channel = self._resolve_channel(member.guild)
        if channel is None:
            return

        try:
            await channel.send(message)
        except (discord.Forbidden, discord.HTTPException):
            return


async def setup(bot):
    await bot.add_cog(Entry(bot))