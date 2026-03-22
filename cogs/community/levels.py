import discord
from discord import app_commands
from discord.ext import commands
import re
import time

import scripts.db as db


def tr(lang: str, pt: str, en: str, es: str) -> str:
    return {"pt": pt, "en": en, "es": es}.get(lang, pt)

class Levels(commands.Cog):
    XP_COOLDOWN_SECONDS = 45
    CONFIG_CACHE_SECONDS = 120

    def __init__(self, bot):
        self.bot = bot
        self.database = db.Database(bot.pool)
        self._xp_cooldown: dict[tuple[int, int], float] = {}
        self._guild_config_cache: dict[int, tuple[float, bool, float]] = {}

    levels = app_commands.Group(name="levels", description="Level system commands")

    async def _lang(self, interaction: discord.Interaction) -> str:
        return await self.bot.i18n.language_for_interaction(self.bot, interaction)

    async def _send_ephemeral(self, interaction: discord.Interaction, message: str) -> None:
        if not interaction.response.is_done():
            await interaction.response.send_message(message, ephemeral=True)
        else:
            await interaction.followup.send(message, ephemeral=True)

    @staticmethod
    def _calculate_xp(content: str) -> int:
        normalized = re.sub(r"\s+", " ", content).strip()
        if len(normalized) < 3:
            return 0

        words = [word for word in normalized.split(" ") if word]
        if not words:
            return 0

        unique_words = len({word.lower() for word in words})
        length_score = min(max(len(normalized) // 20, 4), 14)
        diversity_bonus = min(unique_words // 4, 4)
        punctuation_bonus = 1 if any(ch in normalized for ch in "?!") else 0

        if unique_words <= 1 and len(words) >= 6:
            length_score = max(2, length_score - 2)

        return max(5, min(length_score + diversity_bonus + punctuation_bonus, 22))

    @staticmethod
    def _xp_for_level(level: int) -> int:
        safe_level = max(level, 1)
        return ((safe_level - 1) ** 2) * 100

    @classmethod
    def _level_from_xp(cls, xp: int) -> int:
        if xp <= 0:
            return 1
        return int((xp / 100) ** 0.5) + 1

    async def _get_guild_leveling_config(self, guild_id: int) -> tuple[bool, float]:
        now = time.monotonic()
        cached = self._guild_config_cache.get(guild_id)
        if cached and (now - cached[0]) < self.CONFIG_CACHE_SECONDS:
            return cached[1], cached[2]

        await self.database.execute(
            "INSERT INTO guilds (guild_id) VALUES ($1) ON CONFLICT (guild_id) DO NOTHING",
            guild_id,
        )

        guild_row = await self.database.fetchrow(
            "SELECT leveling_enabled FROM guilds WHERE guild_id = $1",
            guild_id,
        )
        settings_row = await self.database.fetchrow(
            "SELECT xp_multiplier FROM leveling_settings WHERE guild_id = $1",
            guild_id,
        )

        enabled = bool(guild_row["leveling_enabled"]) if guild_row else False
        multiplier = float(settings_row["xp_multiplier"]) if settings_row and settings_row["xp_multiplier"] is not None else 1.0
        multiplier = max(0.1, min(multiplier, 10.0))

        self._guild_config_cache[guild_id] = (now, enabled, multiplier)
        return enabled, multiplier

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        if not await self.bot.is_cog_enabled(message.guild.id, "levels"):
            return

        if not self.bot.pool:
            return

        if not message.content or not message.content.strip():
            return

        user_key = (message.guild.id, message.author.id)
        now = time.monotonic()
        last_xp_at = self._xp_cooldown.get(user_key)
        if last_xp_at and (now - last_xp_at) < self.XP_COOLDOWN_SECONDS:
            return

        try:
            leveling_enabled, xp_multiplier = await self._get_guild_leveling_config(message.guild.id)
            if not leveling_enabled:
                return

            base_xp = self._calculate_xp(message.content)
            if base_xp <= 0:
                return

                        boost_row = await self.database.fetchrow(
                                """
                                SELECT expires_at
                                FROM user_item_effects
                                WHERE user_id = $1
                                    AND effect_key = 'xp_boost'
                                    AND expires_at > CURRENT_TIMESTAMP
                                """,
                                message.author.id,
                        )
                        boost_multiplier = 1.5 if boost_row is not None else 1.0

                        gained_xp = max(1, int(round(base_xp * xp_multiplier * boost_multiplier)))

            await self.database.fetchrow(
                """
                INSERT INTO user_levels (user_id, guild_id, xp, messages_count, last_message_at, updated_at)
                VALUES ($1, $2, $3, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, guild_id)
                DO UPDATE SET
                    xp = user_levels.xp + EXCLUDED.xp,
                    messages_count = user_levels.messages_count + 1,
                    last_message_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING xp
                """,
                message.author.id,
                message.guild.id,
                gained_xp,
            )

            self._xp_cooldown[user_key] = now
        except Exception as exc:
            print(f"[LEVELS] Failed to award XP in guild {message.guild.id}: {exc}")

    @levels.command(name="rank", description="Check your current level and XP")
    async def rank(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await self._send_ephemeral(interaction, tr(lang, "Esse comando so funciona em servidor.", "This command only works in a server.", "Este comando solo funciona en servidor."))
            return

        if not await self.bot.is_cog_enabled(interaction.guild.id, "levels"):
            await self._send_ephemeral(interaction, tr(lang, "O sistema de levels esta desativado neste servidor.", "The leveling system is disabled in this server.", "El sistema de niveles esta desactivado en este servidor."))
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        row = await self.database.fetchrow(
            "SELECT xp, messages_count FROM user_levels WHERE guild_id = $1 AND user_id = $2",
            interaction.guild.id,
            interaction.user.id,
        )
        if row is None:
            await interaction.followup.send(tr(lang, "Voce ainda nao tem XP neste servidor.", "You do not have XP in this server yet.", "Todavia no tienes XP en este servidor."), ephemeral=True)
            return

        total_xp = int(row["xp"])
        current_level = self._level_from_xp(total_xp)
        level_floor = self._xp_for_level(current_level)
        next_level_xp = self._xp_for_level(current_level + 1)
        current_progress = total_xp - level_floor
        needed_progress = max(next_level_xp - level_floor, 1)

        embed = discord.Embed(
            title=tr(lang, "Seu Rank", "Your Rank", "Tu Rango"),
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name=tr(lang, "Nivel", "Level", "Nivel"), value=str(current_level), inline=True)
        embed.add_field(name="XP", value=str(total_xp), inline=True)
        embed.add_field(name=tr(lang, "Mensagens", "Messages", "Mensajes"), value=str(int(row["messages_count"] or 0)), inline=True)
        embed.add_field(
            name=tr(lang, "Progresso", "Progress", "Progreso"),
            value=f"{current_progress}/{needed_progress}",
            inline=False,
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @levels.command(name="leaderboard", description="Show the server leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await self._send_ephemeral(interaction, tr(lang, "Esse comando so funciona em servidor.", "This command only works in a server.", "Este comando solo funciona en servidor."))
            return

        if not await self.bot.is_cog_enabled(interaction.guild.id, "levels"):
            await self._send_ephemeral(interaction, tr(lang, "O sistema de levels esta desativado neste servidor.", "The leveling system is disabled in this server.", "El sistema de niveles esta desactivado en este servidor."))
            return

        await interaction.response.defer(ephemeral=False, thinking=True)

        rows = await self.database.fetch(
            """
            SELECT user_id, xp
            FROM user_levels
            WHERE guild_id = $1
            ORDER BY xp DESC
            LIMIT 10
            """,
            interaction.guild.id,
        )

        if not rows:
            await interaction.followup.send(tr(lang, "Ainda nao ha dados de XP neste servidor.", "There is no XP data in this server yet.", "Aun no hay datos de XP en este servidor."))
            return

        lines: list[str] = []
        for index, row in enumerate(rows, start=1):
            member = interaction.guild.get_member(row["user_id"])
            display_name = member.display_name if member else f"User {row['user_id']}"
            level = self._level_from_xp(int(row["xp"]))
            lines.append(f"{index}. **{display_name}** - XP {row['xp']} (Lv {level})")

        embed = discord.Embed(
            title=tr(lang, "Leaderboard de XP", "XP Leaderboard", "Clasificacion de XP"),
            description="\n".join(lines),
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow(),
        )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    print("[DEBUG] Carregando cog Levels...")
    await bot.add_cog(Levels(bot))
    print("[DEBUG] Cog Levels carregado com sucesso!")
