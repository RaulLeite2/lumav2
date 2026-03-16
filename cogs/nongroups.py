import time
import random
import discord
from discord import app_commands
from discord.ext import commands

import scripts.db


def tr(lang: str, pt: str, en: str, es: str) -> str:
    return {"pt": pt, "en": en, "es": es}.get(lang, pt)


class NonGroups(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.started_at = time.monotonic()

    async def _lang(self, interaction: discord.Interaction) -> str:
        return await self.bot.i18n.language_for_interaction(self.bot, interaction)

    async def _ensure_cog_enabled(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return True

        if await self.bot.is_cog_enabled(interaction.guild.id, "nongroups"):
            return True

        lang = await self._lang(interaction)
        await interaction.response.send_message(
            tr(
                lang,
                "Os comandos gerais estao desativados neste servidor pelo painel.",
                "General commands are disabled in this server by the dashboard.",
                "Los comandos generales estan desactivados en este servidor por el panel.",
            ),
            ephemeral=True,
        )
        return False

    @app_commands.command(name="ping", description="Verifica se a Luma esta online e a latencia")
    async def ping(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        if not await self._ensure_cog_enabled(interaction):
            return

        latency_ms = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            tr(
                lang,
                f"Pong! Latencia atual: **{latency_ms}ms**.",
                f"Pong! Current latency: **{latency_ms}ms**.",
                f"Pong! Latencia actual: **{latency_ms}ms**.",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="about", description="Mostra informacoes basicas da Luma")
    async def about(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        if not await self._ensure_cog_enabled(interaction):
            return

        uptime_seconds = int(time.monotonic() - self.started_at)
        uptime_minutes = max(1, uptime_seconds // 60)
        guilds = len(self.bot.guilds)

        embed = discord.Embed(
            title=tr(lang, "Sobre a Luma", "About Luma", "Sobre Luma"),
            description=tr(
                lang,
                "Base de comandos gerais sem grupos para respostas rapidas da comunidade.",
                "Base of non-group general commands for quick community responses.",
                "Base de comandos generales sin grupos para respuestas rapidas de la comunidad.",
            ),
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name=tr(lang, "Servidores", "Servers", "Servidores"), value=str(guilds), inline=True)
        embed.add_field(name=tr(lang, "Uptime", "Uptime", "Uptime"), value=f"{uptime_minutes} min", inline=True)
        embed.add_field(
            name=tr(lang, "Latencia", "Latency", "Latencia"),
            value=f"{round(self.bot.latency * 1000)}ms",
            inline=True,
        )
        embed.set_footer(text=tr(lang, "Luma • comandos gerais", "Luma • general commands", "Luma • comandos generales"))

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="dice", description="Rola um dado no formato XdY (ex: 2d6)")
    async def dice(self, interaction: discord.Interaction, roll: str):
        lang = await self._lang(interaction)
        if not await self._ensure_cog_enabled(interaction):
            return

        try:
            count_str, sides_str = roll.lower().split('d')
            count = int(count_str)
            sides = int(sides_str)

            if count < 1 or sides < 2:
                raise ValueError

            rolls = [random.randint(1, sides) for _ in range(count)]
            total = sum(rolls)

            await interaction.response.send_message(
                tr(
                    lang,
                    f"Você rolou: {', '.join(map(str, rolls))} (Total: {total})",
                    f"You rolled: {', '.join(map(str, rolls))} (Total: {total})",
                    f"Has rodado: {', '.join(map(str, rolls))} (Total: {total})",
                ),
                ephemeral=True,
            )
        except ValueError:
            await interaction.response.send_message(
                tr(
                    lang,
                    "Formato inválido! Use XdY (ex: 2d6).",
                    "Invalid format! Use XdY (e.g., 2d6).",
                    "¡Formato inválido! Usa XdY (ej: 2d6).",
                ),
                ephemeral=True,
            )

    @app_commands.command(name="record", description="Verifica a ficha disciplinar de um membro")
    async def record(self, interaction: discord.Interaction, member: discord.Member):
        lang = await self._lang(interaction)
        if not await self._ensure_cog_enabled(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        db = scripts.db.Database(self.bot.pool)
        infractions = await db.fetch(
            """
            SELECT id, action, reason, moderator_id, created_at
            FROM moderation_logs
            WHERE guild_id = $1 AND user_id = $2
            ORDER BY created_at DESC
            LIMIT 10
            """,
            interaction.guild.id,
            member.id,
        )

        warns_row = await db.fetchrow(
            "SELECT warning_count FROM user_warnings WHERE guild_id = $1 AND user_id = $2",
            interaction.guild.id,
            member.id,
        )
        total_warns = warns_row["warning_count"] if warns_row else 0

        action_labels = {
            "ban": ("🔨 Ban", "🔨 Ban", "🔨 Ban"),
            "kick": ("👢 Kick", "👢 Kick", "👢 Kick"),
            "warn": ("⚠️ Aviso", "⚠️ Warning", "⚠️ Advertencia"),
            "mute": ("🔇 Mute", "🔇 Mute", "🔇 Mute"),
            "unban": ("✅ Unban", "✅ Unban", "✅ Unban"),
            "timeout": ("⏱️ Timeout", "⏱️ Timeout", "⏱️ Timeout"),
        }

        embed = discord.Embed(
            title=tr(
                lang,
                f"Ficha disciplinar de {member.display_name}",
                f"Disciplinary record of {member.display_name}",
                f"Ficha disciplinaria de {member.display_name}",
            ),
            color=discord.Color.red() if infractions else discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name=tr(lang, "Total de avisos", "Total warnings", "Total de advertencias"),
            value=str(total_warns),
            inline=True,
        )
        embed.add_field(
            name=tr(lang, "Punições registradas", "Registered punishments", "Sanciones registradas"),
            value=str(len(infractions)),
            inline=True,
        )

        if infractions:
            lines = []
            for row in infractions:
                action = row["action"].lower()
                labels = action_labels.get(action, (f"❓ {action}", f"❓ {action}", f"❓ {action}"))
                label = tr(lang, labels[0], labels[1], labels[2])
                reason = row["reason"] or tr(lang, "Sem motivo", "No reason", "Sin motivo")
                date = row["created_at"].strftime("%d/%m/%Y") if row["created_at"] else "?"
                lines.append(f"`{date}` {label} — {reason[:60]}")
            embed.add_field(
                name=tr(lang, "Histórico recente (últimas 10)", "Recent history (last 10)", "Historial reciente (últimas 10)"),
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.description = tr(
                lang,
                f"{member.display_name} não possui punições registradas neste servidor.",
                f"{member.display_name} has no registered punishments in this server.",
                f"{member.display_name} no tiene sanciones registradas en este servidor.",
            )

        embed.set_footer(text=tr(lang, "Luma • ficha disciplinar", "Luma • disciplinary record", "Luma • ficha disciplinaria"))
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(NonGroups(bot))
