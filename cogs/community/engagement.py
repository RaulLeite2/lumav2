import random
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from scripts.db import Database


def tr(lang: str, pt: str, en: str, es: str) -> str:
    return {"pt": pt, "en": en, "es": es}.get(lang, pt)


class Engagement(commands.Cog):
    REP_COOLDOWN_HOURS = 12
    DAILY_MISSION_HOURS = 24

    DAILY_MISSION_POOL = [
        {"key": "messages", "target": 20, "reward": 120},
        {"key": "messages", "target": 35, "reward": 220},
        {"key": "messages", "target": 50, "reward": 340},
    ]

    WEEKLY_MISSION_POOL = [
        {"key": "messages", "target": 160, "reward": 900},
        {"key": "messages", "target": 280, "reward": 1450},
        {"key": "messages", "target": 420, "reward": 2100},
    ]

    ACHIEVEMENT_TEXTS = {
        "first_rep_given": {
            "pt": "Primeira reputacao dada",
            "en": "First reputation given",
            "es": "Primera reputacion dada",
        },
        "helper_5_rep": {
            "pt": "Membro util (5 rep)",
            "en": "Helpful member (5 rep)",
            "es": "Miembro util (5 rep)",
        },
        "first_mission_claim": {
            "pt": "Primeira missao concluida",
            "en": "First mission completed",
            "es": "Primera mision completada",
        },
        "daily_grinder_7": {
            "pt": "Grinder diario (7 missoes)",
            "en": "Daily grinder (7 missions)",
            "es": "Grinder diario (7 misiones)",
        },
        "first_weekly_claim": {
            "pt": "Primeira missao semanal concluida",
            "en": "First weekly mission completed",
            "es": "Primera mision semanal completada",
        },
        "weekly_grinder_4": {
            "pt": "Grinder semanal (4 missoes)",
            "en": "Weekly grinder (4 missions)",
            "es": "Grinder semanal (4 misiones)",
        },
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _db(self) -> Database:
        return Database(self.bot.pool)

    async def _lang(self, interaction: discord.Interaction) -> str:
        return await self.bot.i18n.language_for_interaction(self.bot, interaction)

    async def _send_ephemeral(self, interaction: discord.Interaction, content: str) -> None:
        if not interaction.response.is_done():
            await interaction.response.send_message(content, ephemeral=True)
        else:
            await interaction.followup.send(content, ephemeral=True)

    async def _ensure_cog_enabled(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return True
        if await self.bot.is_cog_enabled(interaction.guild.id, "engagement"):
            return True

        lang = await self._lang(interaction)
        await self._send_ephemeral(
            interaction,
            tr(
                lang,
                "O sistema de comunidade esta desativado neste servidor pelo painel.",
                "The community system is disabled in this server by the dashboard.",
                "El sistema de comunidad esta desactivado en este servidor por el panel.",
            ),
        )
        return False

    async def _ensure_economy_account(self, user_id: int) -> None:
        db = self._db()
        await db.execute(
            """
            INSERT INTO economy (user_id, balance)
            VALUES ($1, 0)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
        )

    async def _unlock_achievement(self, user_id: int, key: str) -> bool:
        db = self._db()
        unlocked_key = await db.fetchval(
            """
            INSERT INTO user_achievements (user_id, achievement_key)
            VALUES ($1, $2)
            ON CONFLICT (user_id, achievement_key) DO NOTHING
            RETURNING achievement_key
            """,
            user_id,
            key,
        )
        return unlocked_key is not None

    async def _total_mission_claims(self, user_id: int) -> int:
        db = self._db()
        total = await db.fetchval(
            """
            SELECT COUNT(*)
            FROM user_daily_missions
            WHERE user_id = $1 AND claimed_at IS NOT NULL
            """,
            user_id,
        )
        return int(total or 0)

    async def _active_mission_row(self, user_id: int):
        db = self._db()
        return await db.fetchrow(
            """
            SELECT mission_key, target_count, progress_count, reward_coins, assigned_at, claimed_at
            FROM user_daily_missions
            WHERE user_id = $1
            """,
            user_id,
        )

    async def _total_weekly_claims(self, user_id: int) -> int:
        db = self._db()
        total = await db.fetchval(
            """
            SELECT COUNT(*)
            FROM user_weekly_missions
            WHERE user_id = $1 AND claimed_at IS NOT NULL
            """,
            user_id,
        )
        return int(total or 0)

    async def _active_weekly_mission_row(self, user_id: int):
        db = self._db()
        return await db.fetchrow(
            """
            SELECT week_key, mission_key, target_count, progress_count, reward_coins, assigned_at, claimed_at
            FROM user_weekly_missions
            WHERE user_id = $1
            """,
            user_id,
        )

    @staticmethod
    def _current_week_key(now: datetime | None = None) -> str:
        current = now or datetime.now(timezone.utc)
        iso = current.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    @staticmethod
    def _next_week_reset(now: datetime | None = None) -> datetime:
        current = now or datetime.now(timezone.utc)
        week_start = current - timedelta(
            days=current.weekday(),
            hours=current.hour,
            minutes=current.minute,
            seconds=current.second,
            microseconds=current.microsecond,
        )
        return week_start + timedelta(days=7)

    @staticmethod
    def _mission_title(lang: str, key: str, target: int) -> str:
        if key == "messages":
            return tr(
                lang,
                f"Envie {target} mensagens no servidor",
                f"Send {target} messages in the server",
                f"Envia {target} mensajes en el servidor",
            )
        return tr(lang, "Missao desconhecida", "Unknown mission", "Mision desconocida")

    @staticmethod
    def _weekly_mission_title(lang: str, key: str, target: int) -> str:
        if key == "messages":
            return tr(
                lang,
                f"Envie {target} mensagens durante a semana",
                f"Send {target} messages during the week",
                f"Envia {target} mensajes durante la semana",
            )
        return tr(lang, "Missao semanal desconhecida", "Unknown weekly mission", "Mision semanal desconocida")

    @staticmethod
    def _seconds_to_hm(seconds: int) -> str:
        safe = max(0, int(seconds))
        hours, rem = divmod(safe, 3600)
        minutes = rem // 60
        return f"{hours}h {minutes}m"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        if not await self.bot.is_cog_enabled(message.guild.id, "engagement"):
            return

        if not message.content or not message.content.strip():
            return

        if self.bot.pool is None:
            return

        db = self._db()
        week_key = self._current_week_key()
        try:
            await db.execute(
                """
                UPDATE user_daily_missions
                SET progress_count = LEAST(progress_count + 1, target_count),
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = $1
                  AND mission_key = 'messages'
                  AND claimed_at IS NULL
                  AND progress_count < target_count
                """,
                message.author.id,
            )

            await db.execute(
                """
                UPDATE user_weekly_missions
                SET progress_count = LEAST(progress_count + 1, target_count),
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = $1
                  AND week_key = $2
                  AND mission_key = 'messages'
                  AND claimed_at IS NULL
                  AND progress_count < target_count
                """,
                message.author.id,
                week_key,
            )
        except Exception as exc:
            print(f"[ENGAGEMENT] Failed to update mission progress for {message.author.id}: {exc}")

    @app_commands.command(name="rep", description="Give +1 reputation to a member")
    async def rep(self, interaction: discord.Interaction, member: discord.Member):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await self._send_ephemeral(
                interaction,
                tr(lang, "Esse comando so funciona em servidor.", "This command only works in a server.", "Este comando solo funciona en servidor."),
            )
            return

        if not await self._ensure_cog_enabled(interaction):
            return

        if member.bot:
            await self._send_ephemeral(
                interaction,
                tr(lang, "Voce nao pode dar reputacao para bots.", "You cannot give reputation to bots.", "No puedes dar reputacion a bots."),
            )
            return

        if member.id == interaction.user.id:
            await self._send_ephemeral(
                interaction,
                tr(lang, "Voce nao pode dar reputacao para si mesmo.", "You cannot give reputation to yourself.", "No puedes darte reputacion a ti mismo."),
            )
            return

        db = self._db()
        now = datetime.now(timezone.utc)
        cooldown = timedelta(hours=self.REP_COOLDOWN_HOURS)

        row = await db.fetchrow("SELECT last_given_at FROM rep_cooldowns WHERE giver_id = $1", interaction.user.id)
        if row and row["last_given_at"] is not None:
            last_given = row["last_given_at"]
            last_given_utc = last_given.replace(tzinfo=timezone.utc) if last_given.tzinfo is None else last_given.astimezone(timezone.utc)
            remaining = (last_given_utc + cooldown) - now
            if remaining.total_seconds() > 0:
                await self._send_ephemeral(
                    interaction,
                    tr(
                        lang,
                        f"Voce ja deu reputacao recentemente. Tente novamente em {self._seconds_to_hm(int(remaining.total_seconds()))}.",
                        f"You already gave reputation recently. Try again in {self._seconds_to_hm(int(remaining.total_seconds()))}.",
                        f"Ya diste reputacion recientemente. Intentalo de nuevo en {self._seconds_to_hm(int(remaining.total_seconds()))}.",
                    ),
                )
                return

        async with self.bot.pool.acquire() as connection:
            async with connection.transaction():
                rep_points = await connection.fetchval(
                    """
                    INSERT INTO user_reputation (user_id, rep_points, updated_at)
                    VALUES ($1, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id)
                    DO UPDATE SET rep_points = user_reputation.rep_points + 1, updated_at = CURRENT_TIMESTAMP
                    RETURNING rep_points
                    """,
                    member.id,
                )

                await connection.execute(
                    """
                    INSERT INTO rep_cooldowns (giver_id, last_given_at)
                    VALUES ($1, CURRENT_TIMESTAMP)
                    ON CONFLICT (giver_id)
                    DO UPDATE SET last_given_at = CURRENT_TIMESTAMP
                    """,
                    interaction.user.id,
                )

        just_unlocked: list[str] = []
        if await self._unlock_achievement(interaction.user.id, "first_rep_given"):
            just_unlocked.append(self.ACHIEVEMENT_TEXTS["first_rep_given"][lang])

        if int(rep_points or 0) >= 5 and await self._unlock_achievement(member.id, "helper_5_rep"):
            just_unlocked.append(self.ACHIEVEMENT_TEXTS["helper_5_rep"][lang])

        message = tr(
            lang,
            f"{interaction.user.mention} deu +1 rep para {member.mention}. Reputacao atual: **{int(rep_points or 0)}**.",
            f"{interaction.user.mention} gave +1 rep to {member.mention}. Current reputation: **{int(rep_points or 0)}**.",
            f"{interaction.user.mention} dio +1 rep a {member.mention}. Reputacion actual: **{int(rep_points or 0)}**.",
        )
        if just_unlocked:
            message += "\n\n" + tr(lang, "Conquista desbloqueada: ", "Achievement unlocked: ", "Logro desbloqueado: ") + ", ".join(just_unlocked)

        await interaction.response.send_message(message)

    @app_commands.command(name="repinfo", description="Show your or another member reputation")
    async def repinfo(self, interaction: discord.Interaction, member: discord.Member | None = None):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await self._send_ephemeral(
                interaction,
                tr(lang, "Esse comando so funciona em servidor.", "This command only works in a server.", "Este comando solo funciona en servidor."),
            )
            return

        if not await self._ensure_cog_enabled(interaction):
            return

        target = member or interaction.user
        db = self._db()
        rep_points = await db.fetchval("SELECT rep_points FROM user_reputation WHERE user_id = $1", target.id)

        await interaction.response.send_message(
            tr(
                lang,
                f"Reputacao de {target.mention}: **{int(rep_points or 0)}**",
                f"{target.mention} reputation: **{int(rep_points or 0)}**",
                f"Reputacion de {target.mention}: **{int(rep_points or 0)}**",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="mission", description="Show or generate your daily mission")
    async def mission(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await self._send_ephemeral(
                interaction,
                tr(lang, "Esse comando so funciona em servidor.", "This command only works in a server.", "Este comando solo funciona en servidor."),
            )
            return

        if not await self._ensure_cog_enabled(interaction):
            return

        db = self._db()
        now = datetime.now(timezone.utc)
        mission_row = await self._active_mission_row(interaction.user.id)

        should_generate = mission_row is None
        if mission_row and mission_row["assigned_at"] is not None:
            assigned_at = mission_row["assigned_at"]
            assigned_utc = assigned_at.replace(tzinfo=timezone.utc) if assigned_at.tzinfo is None else assigned_at.astimezone(timezone.utc)
            should_generate = (now - assigned_utc) >= timedelta(hours=self.DAILY_MISSION_HOURS)

        if should_generate:
            mission = random.choice(self.DAILY_MISSION_POOL)
            mission_row = await db.fetchrow(
                """
                INSERT INTO user_daily_missions (user_id, mission_key, target_count, progress_count, reward_coins, assigned_at, claimed_at, updated_at)
                VALUES ($1, $2, $3, 0, $4, CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    mission_key = EXCLUDED.mission_key,
                    target_count = EXCLUDED.target_count,
                    progress_count = 0,
                    reward_coins = EXCLUDED.reward_coins,
                    assigned_at = CURRENT_TIMESTAMP,
                    claimed_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING mission_key, target_count, progress_count, reward_coins, assigned_at, claimed_at
                """,
                interaction.user.id,
                mission["key"],
                mission["target"],
                mission["reward"],
            )

        key = str(mission_row["mission_key"])
        target = int(mission_row["target_count"])
        progress = int(mission_row["progress_count"])
        reward = int(mission_row["reward_coins"])
        claimed = mission_row["claimed_at"] is not None

        title = tr(lang, "Sua missao diaria", "Your daily mission", "Tu mision diaria")
        description = self._mission_title(lang, key, target)
        status = tr(lang, "Concluida (resgatada)" if claimed else "Em andamento", "Completed (claimed)" if claimed else "In progress", "Completada (reclamada)" if claimed else "En progreso")

        embed = discord.Embed(title=title, description=description, color=discord.Color.teal())
        embed.add_field(name=tr(lang, "Progresso", "Progress", "Progreso"), value=f"{progress}/{target}", inline=True)
        embed.add_field(name=tr(lang, "Recompensa", "Reward", "Recompensa"), value=f"{reward} Lumicoins", inline=True)
        embed.add_field(name=tr(lang, "Status", "Status", "Estado"), value=status, inline=True)
        embed.set_footer(text=tr(lang, "Use /missionclaim para resgatar ao concluir.", "Use /missionclaim to claim when complete.", "Usa /missionclaim para reclamar al completar."))

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="missionclaim", description="Claim your completed daily mission reward")
    async def missionclaim(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await self._send_ephemeral(
                interaction,
                tr(lang, "Esse comando so funciona em servidor.", "This command only works in a server.", "Este comando solo funciona en servidor."),
            )
            return

        if not await self._ensure_cog_enabled(interaction):
            return

        db = self._db()
        mission_row = await self._active_mission_row(interaction.user.id)
        if mission_row is None:
            await self._send_ephemeral(
                interaction,
                tr(lang, "Voce ainda nao tem missao ativa. Use /mission.", "You do not have an active mission yet. Use /mission.", "Aun no tienes una mision activa. Usa /mission."),
            )
            return

        if mission_row["claimed_at"] is not None:
            assigned = mission_row["assigned_at"]
            assigned_utc = assigned.replace(tzinfo=timezone.utc) if assigned.tzinfo is None else assigned.astimezone(timezone.utc)
            next_at = assigned_utc + timedelta(hours=self.DAILY_MISSION_HOURS)
            now = datetime.now(timezone.utc)
            remaining = (next_at - now).total_seconds()
            if remaining > 0:
                await self._send_ephemeral(
                    interaction,
                    tr(
                        lang,
                        f"Voce ja resgatou essa missao. Nova missao em {self._seconds_to_hm(int(remaining))}.",
                        f"You already claimed this mission. New mission in {self._seconds_to_hm(int(remaining))}.",
                        f"Ya reclamaste esta mision. Nueva mision en {self._seconds_to_hm(int(remaining))}.",
                    ),
                )
                return

        target = int(mission_row["target_count"])
        progress = int(mission_row["progress_count"])
        reward = int(mission_row["reward_coins"])

        if progress < target:
            await self._send_ephemeral(
                interaction,
                tr(
                    lang,
                    f"Missao ainda nao concluida: {progress}/{target}.",
                    f"Mission not complete yet: {progress}/{target}.",
                    f"Mision aun no completada: {progress}/{target}.",
                ),
            )
            return

        async with self.bot.pool.acquire() as connection:
            async with connection.transaction():
                claimed = await connection.fetchval(
                    """
                    UPDATE user_daily_missions
                    SET claimed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                      AND claimed_at IS NULL
                      AND progress_count >= target_count
                    RETURNING user_id
                    """,
                    interaction.user.id,
                )

                if claimed is None:
                    await self._send_ephemeral(
                        interaction,
                        tr(lang, "Nao foi possivel resgatar agora. Tente novamente.", "Could not claim now. Try again.", "No se pudo reclamar ahora. Intenta otra vez."),
                    )
                    return

                await connection.execute(
                    """
                    INSERT INTO economy (user_id, balance)
                    VALUES ($1, 0)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    interaction.user.id,
                )

                new_balance = await connection.fetchval(
                    """
                    UPDATE economy
                    SET balance = balance + $1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $2
                    RETURNING balance
                    """,
                    reward,
                    interaction.user.id,
                )

        unlocked_labels: list[str] = []
        if await self._unlock_achievement(interaction.user.id, "first_mission_claim"):
            unlocked_labels.append(self.ACHIEVEMENT_TEXTS["first_mission_claim"][lang])

        total_claims = await self._total_mission_claims(interaction.user.id)
        if total_claims >= 7 and await self._unlock_achievement(interaction.user.id, "daily_grinder_7"):
            unlocked_labels.append(self.ACHIEVEMENT_TEXTS["daily_grinder_7"][lang])

        response = tr(
            lang,
            f"Missao resgatada com sucesso! +{reward} Lumicoins. Saldo atual: **{int(new_balance or 0)}**.",
            f"Mission claimed successfully! +{reward} Lumicoins. Current balance: **{int(new_balance or 0)}**.",
            f"Mision reclamada con exito! +{reward} Lumicoins. Saldo actual: **{int(new_balance or 0)}**.",
        )
        if unlocked_labels:
            response += "\n\n" + tr(lang, "Conquista desbloqueada: ", "Achievement unlocked: ", "Logro desbloqueado: ") + ", ".join(unlocked_labels)

        await interaction.response.send_message(response, ephemeral=True)

    @app_commands.command(name="weeklymission", description="Show or generate your weekly mission")
    async def weeklymission(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await self._send_ephemeral(
                interaction,
                tr(lang, "Esse comando so funciona em servidor.", "This command only works in a server.", "Este comando solo funciona en servidor."),
            )
            return

        if not await self._ensure_cog_enabled(interaction):
            return

        db = self._db()
        now = datetime.now(timezone.utc)
        current_week_key = self._current_week_key(now)
        mission_row = await self._active_weekly_mission_row(interaction.user.id)

        should_generate = mission_row is None or str(mission_row["week_key"]) != current_week_key

        if should_generate:
            mission = random.choice(self.WEEKLY_MISSION_POOL)
            mission_row = await db.fetchrow(
                """
                INSERT INTO user_weekly_missions (user_id, week_key, mission_key, target_count, progress_count, reward_coins, assigned_at, claimed_at, updated_at)
                VALUES ($1, $2, $3, $4, 0, $5, CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    week_key = EXCLUDED.week_key,
                    mission_key = EXCLUDED.mission_key,
                    target_count = EXCLUDED.target_count,
                    progress_count = 0,
                    reward_coins = EXCLUDED.reward_coins,
                    assigned_at = CURRENT_TIMESTAMP,
                    claimed_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING week_key, mission_key, target_count, progress_count, reward_coins, assigned_at, claimed_at
                """,
                interaction.user.id,
                current_week_key,
                mission["key"],
                mission["target"],
                mission["reward"],
            )

        key = str(mission_row["mission_key"])
        target = int(mission_row["target_count"])
        progress = int(mission_row["progress_count"])
        reward = int(mission_row["reward_coins"])
        claimed = mission_row["claimed_at"] is not None

        title = tr(lang, "Sua missao semanal", "Your weekly mission", "Tu mision semanal")
        description = self._weekly_mission_title(lang, key, target)
        status = tr(lang, "Concluida (resgatada)" if claimed else "Em andamento", "Completed (claimed)" if claimed else "In progress", "Completada (reclamada)" if claimed else "En progreso")

        embed = discord.Embed(title=title, description=description, color=discord.Color.gold())
        embed.add_field(name=tr(lang, "Semana", "Week", "Semana"), value=current_week_key, inline=True)
        embed.add_field(name=tr(lang, "Progresso", "Progress", "Progreso"), value=f"{progress}/{target}", inline=True)
        embed.add_field(name=tr(lang, "Recompensa", "Reward", "Recompensa"), value=f"{reward} Lumicoins", inline=True)
        embed.add_field(name=tr(lang, "Status", "Status", "Estado"), value=status, inline=False)
        embed.set_footer(text=tr(lang, "Use /weeklymissionclaim para resgatar ao concluir.", "Use /weeklymissionclaim to claim when complete.", "Usa /weeklymissionclaim para reclamar al completar."))

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="weeklymissionclaim", description="Claim your completed weekly mission reward")
    async def weeklymissionclaim(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await self._send_ephemeral(
                interaction,
                tr(lang, "Esse comando so funciona em servidor.", "This command only works in a server.", "Este comando solo funciona en servidor."),
            )
            return

        if not await self._ensure_cog_enabled(interaction):
            return

        db = self._db()
        now = datetime.now(timezone.utc)
        current_week_key = self._current_week_key(now)

        mission_row = await self._active_weekly_mission_row(interaction.user.id)
        if mission_row is None or str(mission_row["week_key"]) != current_week_key:
            await self._send_ephemeral(
                interaction,
                tr(
                    lang,
                    "Voce ainda nao tem missao semanal ativa. Use /weeklymission.",
                    "You do not have an active weekly mission yet. Use /weeklymission.",
                    "Aun no tienes una mision semanal activa. Usa /weeklymission.",
                ),
            )
            return

        if mission_row["claimed_at"] is not None:
            remaining = int((self._next_week_reset(now) - now).total_seconds())
            await self._send_ephemeral(
                interaction,
                tr(
                    lang,
                    f"Voce ja resgatou essa missao semanal. Nova semana em {self._seconds_to_hm(remaining)}.",
                    f"You already claimed this weekly mission. New week in {self._seconds_to_hm(remaining)}.",
                    f"Ya reclamaste esta mision semanal. Nueva semana en {self._seconds_to_hm(remaining)}.",
                ),
            )
            return

        target = int(mission_row["target_count"])
        progress = int(mission_row["progress_count"])
        reward = int(mission_row["reward_coins"])

        if progress < target:
            await self._send_ephemeral(
                interaction,
                tr(
                    lang,
                    f"Missao semanal ainda nao concluida: {progress}/{target}.",
                    f"Weekly mission not complete yet: {progress}/{target}.",
                    f"Mision semanal aun no completada: {progress}/{target}.",
                ),
            )
            return

        async with self.bot.pool.acquire() as connection:
            async with connection.transaction():
                claimed = await connection.fetchval(
                    """
                    UPDATE user_weekly_missions
                    SET claimed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                      AND week_key = $2
                      AND claimed_at IS NULL
                      AND progress_count >= target_count
                    RETURNING user_id
                    """,
                    interaction.user.id,
                    current_week_key,
                )

                if claimed is None:
                    await self._send_ephemeral(
                        interaction,
                        tr(lang, "Nao foi possivel resgatar agora. Tente novamente.", "Could not claim now. Try again.", "No se pudo reclamar ahora. Intenta otra vez."),
                    )
                    return

                await connection.execute(
                    """
                    INSERT INTO economy (user_id, balance)
                    VALUES ($1, 0)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    interaction.user.id,
                )

                new_balance = await connection.fetchval(
                    """
                    UPDATE economy
                    SET balance = balance + $1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $2
                    RETURNING balance
                    """,
                    reward,
                    interaction.user.id,
                )

        unlocked_labels: list[str] = []
        if await self._unlock_achievement(interaction.user.id, "first_weekly_claim"):
            unlocked_labels.append(self.ACHIEVEMENT_TEXTS["first_weekly_claim"][lang])

        total_claims = await self._total_weekly_claims(interaction.user.id)
        if total_claims >= 4 and await self._unlock_achievement(interaction.user.id, "weekly_grinder_4"):
            unlocked_labels.append(self.ACHIEVEMENT_TEXTS["weekly_grinder_4"][lang])

        response = tr(
            lang,
            f"Missao semanal resgatada com sucesso! +{reward} Lumicoins. Saldo atual: **{int(new_balance or 0)}**.",
            f"Weekly mission claimed successfully! +{reward} Lumicoins. Current balance: **{int(new_balance or 0)}**.",
            f"Mision semanal reclamada con exito! +{reward} Lumicoins. Saldo actual: **{int(new_balance or 0)}**.",
        )
        if unlocked_labels:
            response += "\n\n" + tr(lang, "Conquista desbloqueada: ", "Achievement unlocked: ", "Logro desbloqueado: ") + ", ".join(unlocked_labels)

        await interaction.response.send_message(response, ephemeral=True)

    @app_commands.command(name="achievements", description="Show unlocked achievements")
    async def achievements(self, interaction: discord.Interaction, member: discord.Member | None = None):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await self._send_ephemeral(
                interaction,
                tr(lang, "Esse comando so funciona em servidor.", "This command only works in a server.", "Este comando solo funciona en servidor."),
            )
            return

        if not await self._ensure_cog_enabled(interaction):
            return

        target = member or interaction.user
        db = self._db()
        rows = await db.fetch(
            """
            SELECT achievement_key, unlocked_at
            FROM user_achievements
            WHERE user_id = $1
            ORDER BY unlocked_at ASC
            """,
            target.id,
        )

        unlocked_keys = [str(row["achievement_key"]) for row in rows]
        all_keys = list(self.ACHIEVEMENT_TEXTS.keys())

        lines: list[str] = []
        for key in all_keys:
            label = self.ACHIEVEMENT_TEXTS[key][lang]
            marker = "✅" if key in unlocked_keys else "⬜"
            lines.append(f"{marker} {label}")

        embed = discord.Embed(
            title=tr(lang, f"Conquistas de {target.display_name}", f"{target.display_name}'s achievements", f"Logros de {target.display_name}"),
            description="\n".join(lines),
            color=discord.Color.purple(),
        )
        embed.set_footer(
            text=tr(
                lang,
                f"Desbloqueadas: {len(unlocked_keys)}/{len(all_keys)}",
                f"Unlocked: {len(unlocked_keys)}/{len(all_keys)}",
                f"Desbloqueadas: {len(unlocked_keys)}/{len(all_keys)}",
            )
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    print("[DEBUG] Carregando cog Engagement...")
    await bot.add_cog(Engagement(bot))
    print("[DEBUG] Cog Engagement carregado com sucesso!")
