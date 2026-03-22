import time
import random
import json
import os
import urllib.error
import urllib.parse
import urllib.request
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
        self.news_cursor_by_guild: dict[int, int] = {}

    async def _fetch_public_news(self, after_id: int, limit: int) -> dict:
        base_url = os.getenv(
            "LUMA_NEWS_API_URL",
            "http://127.0.0.1:8000/api/public/news/latest",
        )

        params = urllib.parse.urlencode(
            {
                "after_id": max(0, int(after_id)),
                "limit": max(1, min(int(limit), 10)),
            }
        )
        url = f"{base_url}?{params}"

        def _request() -> dict:
            req = urllib.request.Request(url, headers={"User-Agent": "LumaBot/1.0"})
            with urllib.request.urlopen(req, timeout=8) as response:
                body = response.read().decode("utf-8")
            data = json.loads(body)
            return data if isinstance(data, dict) else {}

        return await self.bot.loop.run_in_executor(None, _request)

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

    @app_commands.command(name="news", description="Consulta as ultimas noticias do blog da Luma")
    async def news(self, interaction: discord.Interaction, limit: app_commands.Range[int, 1, 10] = 3):
        lang = await self._lang(interaction)
        if not await self._ensure_cog_enabled(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        guild_key = interaction.guild.id if interaction.guild else interaction.user.id
        last_seen = self.news_cursor_by_guild.get(guild_key, 0)

        try:
            payload = await self._fetch_public_news(after_id=last_seen, limit=int(limit))
        except urllib.error.URLError:
            await interaction.followup.send(
                tr(
                    lang,
                    "Nao consegui acessar o feed de noticias agora. Tente novamente em instantes.",
                    "I could not access the news feed right now. Please try again shortly.",
                    "No pude acceder al feed de noticias ahora. Intenta de nuevo en breve.",
                ),
                ephemeral=True,
            )
            return
        except Exception:
            await interaction.followup.send(
                tr(
                    lang,
                    "Erro ao ler noticias do site.",
                    "Error while reading site news.",
                    "Error al leer noticias del sitio.",
                ),
                ephemeral=True,
            )
            return

        posts = payload.get("posts") if isinstance(payload.get("posts"), list) else []
        newest_id = int(payload.get("newest_id") or 0)
        has_new = bool(payload.get("has_new"))

        if newest_id > last_seen:
            self.news_cursor_by_guild[guild_key] = newest_id

        if not posts:
            await interaction.followup.send(
                tr(
                    lang,
                    "Ainda nao existem noticias publicadas no blog.",
                    "There are no published news posts yet.",
                    "Aun no hay noticias publicadas en el blog.",
                ),
                ephemeral=True,
            )
            return

        top = posts[0]
        embed = discord.Embed(
            title=tr(lang, "Noticias da Luma", "Luma News", "Noticias de Luma"),
            description=tr(
                lang,
                "Tem post novo desde a ultima consulta!" if has_new else "Sem novidades desde a ultima consulta.",
                "There is a new post since your last check!" if has_new else "No new posts since your last check.",
                "Hay una publicacion nueva desde tu ultima consulta!" if has_new else "Sin novedades desde tu ultima consulta.",
            ),
            color=discord.Color.gold() if has_new else discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name=tr(lang, "Ultimo post", "Latest post", "Ultimo post"), value=str(top.get("title") or "-"), inline=False)

        lines = []
        for post in posts[: int(limit)]:
            title = str(post.get("title") or "Sem titulo")
            pid = int(post.get("id") or 0)
            lines.append(f"#{pid} - {title}")
        embed.add_field(name=tr(lang, "Feed", "Feed", "Feed"), value="\n".join(lines), inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

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
