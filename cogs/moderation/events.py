from datetime import datetime, timedelta
import itertools
import re

import discord
from discord import app_commands
from discord.ext import commands

import scripts.db


def tr(lang: str, pt: str, en: str, es: str) -> str:
    return {"pt": pt, "en": en, "es": es}.get(lang, pt)


class Events(commands.Cog):
    DEFAULT_SPAM_THRESHOLD = 6
    DEFAULT_RAID_SETTINGS = {
        "enabled": False,
        "join_threshold": 7,
        "window_seconds": 15,
        "min_account_age_days": 7,
        "auto_lock_minutes": 10,
        "action": "kick",
        "mode": "lockdown",
        "recovery_cooldown_minutes": 10,
        "notify_channel_id": None,
    }

    def __init__(self, bot):
        self.bot = bot
        self.database = scripts.db.Database(bot.pool)
        self.spam_cooldown: dict[tuple[int, int], list[datetime]] = {}
        self.max_caps_ratio = 0.70
        self.max_emojis = 10
        self.invite_pattern = re.compile(r"discord\.gg/\w+|discord(app)?\.com/invite/\w+", re.IGNORECASE)
        self.link_pattern = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
        self.emoji_pattern = re.compile(r"<a?:\w+:\d+>|[\U0001F600-\U0001F64F]|[\U0001F300-\U0001F5FF]|[\U0001F680-\U0001F6FF]|[\U0001F900-\U0001F9FF]|[\U0001FA70-\U0001FAFF]")
        self.raid_joins_window: dict[int, list[datetime]] = {}
        self.raid_lock_until: dict[int, datetime] = {}
        self.raid_preventive_until: dict[int, datetime] = {}
        self.raid_last_join_at: dict[int, datetime] = {}

    raid = app_commands.Group(name="raid", description="Comandos de anti-raid")

    async def _guild_lang(self, guild: discord.Guild | None) -> str:
        if guild is None:
            return "pt"
        return await self.bot.i18n.get_guild_language(self.bot.pool, guild.id)

    async def _get_guild_settings(self, guild_id: int) -> dict[str, object]:
        row = await self.database.fetchrow(
            """
            SELECT
                smart_antiflood,
                auto_moderation,
                quant_warnings,
                acao,
                automod_invite_filter,
                automod_link_filter,
                automod_caps_filter,
                automod_spam_threshold,
                automod_quarantine_role_id,
                warn_dm_user,
                logs_enabled,
                log_channel_id,
                log_join_leave,
                log_message_delete
            FROM guilds
            WHERE guild_id = $1
            """,
            guild_id,
        )

        defaults: dict[str, object] = {
            "smart_antiflood": False,
            "auto_moderation": False,
            "quant_warnings": 3,
            "acao": "kick",
            "automod_invite_filter": True,
            "automod_link_filter": True,
            "automod_caps_filter": False,
            "automod_spam_threshold": self.DEFAULT_SPAM_THRESHOLD,
            "automod_quarantine_role_id": None,
            "warn_dm_user": True,
            "logs_enabled": True,
            "log_channel_id": None,
            "log_join_leave": False,
            "log_message_delete": True,
            "immune_role_ids": [],
            "welcome_enabled": False,
            "welcome_channel_id": None,
            "welcome_title": "Bem-vindo(a), {member}!",
            "welcome_description": "Aproveite sua estadia em **{guild}**.",
            "welcome_color": "#57cc99",
            "leave_enabled": False,
            "leave_channel_id": None,
            "leave_title": "Ate logo, {member}.",
            "leave_description": "{member} saiu de **{guild}**.",
            "leave_color": "#ef476f",
        }
        if row is None:
            role_rows = await self.database.fetch(
                "SELECT role_id FROM guild_immune_roles WHERE guild_id = $1 ORDER BY role_id",
                guild_id,
            )
            defaults["immune_role_ids"] = [int(item["role_id"]) for item in role_rows if item and item["role_id"] is not None]
            entry_exit_row = await self._fetch_entry_exit_settings(guild_id)
            if entry_exit_row:
                defaults.update({key: value for key, value in dict(entry_exit_row).items() if value is not None})
            return defaults

        payload = dict(row)
        defaults.update({key: value for key, value in payload.items() if value is not None})
        role_rows = await self.database.fetch(
            "SELECT role_id FROM guild_immune_roles WHERE guild_id = $1 ORDER BY role_id",
            guild_id,
        )
        defaults["immune_role_ids"] = [int(item["role_id"]) for item in role_rows if item and item["role_id"] is not None]
        entry_exit_row = await self._fetch_entry_exit_settings(guild_id)
        if entry_exit_row:
            defaults.update({key: value for key, value in dict(entry_exit_row).items() if value is not None})
        return defaults

    async def _fetch_entry_exit_settings(self, guild_id: int):
        try:
            return await self.database.fetchrow(
                """
                SELECT
                    welcome_enabled,
                    welcome_channel_id,
                    welcome_title,
                    welcome_description,
                    welcome_color,
                    leave_enabled,
                    leave_channel_id,
                    leave_title,
                    leave_description,
                    leave_color
                FROM guild_entry_exit_embeds
                WHERE guild_id = $1
                """,
                guild_id,
            )
        except Exception:
            return None

    async def _get_raid_settings(self, guild_id: int) -> dict[str, object]:
        defaults = dict(self.DEFAULT_RAID_SETTINGS)
        try:
            row = await self.database.fetchrow(
                """
                SELECT enabled, join_threshold, window_seconds, min_account_age_days, auto_lock_minutes, action, mode, recovery_cooldown_minutes, notify_channel_id
                FROM guild_raid_settings
                WHERE guild_id = $1
                """,
                guild_id,
            )
        except Exception:
            try:
                row = await self.database.fetchrow(
                    """
                    SELECT enabled, join_threshold, window_seconds, min_account_age_days, auto_lock_minutes, action, notify_channel_id
                    FROM guild_raid_settings
                    WHERE guild_id = $1
                    """,
                    guild_id,
                )
            except Exception:
                return defaults

        if row is None:
            return defaults

        payload = dict(row)
        defaults.update({key: value for key, value in payload.items() if value is not None})
        action = str(defaults.get("action") or "kick").lower()
        defaults["action"] = action if action in {"kick", "ban"} else "kick"
        mode = str(defaults.get("mode") or "lockdown").lower()
        defaults["mode"] = mode if mode in {"preventive", "lockdown", "recovery"} else "lockdown"
        return defaults

    async def _save_raid_settings(self, guild_id: int, settings: dict[str, object]) -> None:
        await self.database.execute(
            """
            INSERT INTO guild_raid_settings (
                guild_id, enabled, join_threshold, window_seconds, min_account_age_days, auto_lock_minutes, action, mode, recovery_cooldown_minutes, notify_channel_id, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, CURRENT_TIMESTAMP)
            ON CONFLICT (guild_id)
            DO UPDATE SET
                enabled = EXCLUDED.enabled,
                join_threshold = EXCLUDED.join_threshold,
                window_seconds = EXCLUDED.window_seconds,
                min_account_age_days = EXCLUDED.min_account_age_days,
                auto_lock_minutes = EXCLUDED.auto_lock_minutes,
                action = EXCLUDED.action,
                mode = EXCLUDED.mode,
                recovery_cooldown_minutes = EXCLUDED.recovery_cooldown_minutes,
                notify_channel_id = EXCLUDED.notify_channel_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            guild_id,
            bool(settings.get("enabled")),
            int(settings.get("join_threshold") or 7),
            int(settings.get("window_seconds") or 15),
            int(settings.get("min_account_age_days") or 7),
            int(settings.get("auto_lock_minutes") or 10),
            str(settings.get("action") or "kick"),
            str(settings.get("mode") or "lockdown"),
            int(settings.get("recovery_cooldown_minutes") or 10),
            settings.get("notify_channel_id"),
        )

    async def _resolve_raid_notify_channel(self, guild: discord.Guild, settings: dict[str, object]) -> discord.TextChannel | None:
        notify_id = settings.get("notify_channel_id")
        if notify_id:
            channel = guild.get_channel(int(notify_id))
            if isinstance(channel, discord.TextChannel):
                return channel

        guild_settings = await self._get_guild_settings(guild.id)
        return await self._get_log_channel(guild, guild_settings)

    async def _notify_raid_alert(self, guild: discord.Guild, settings: dict[str, object], *, join_count: int, lock_until: datetime) -> None:
        channel = await self._resolve_raid_notify_channel(guild, settings)
        if channel is None:
            return

        lang = await self._guild_lang(guild)
        embed = discord.Embed(
            title=tr(lang, "Alerta de raid detectado", "Raid alert detected", "Alerta de raid detectado"),
            description=tr(
                lang,
                "Um pico de entradas foi detectado. O modo de bloqueio temporario foi ativado.",
                "A join spike was detected. Temporary lock mode has been activated.",
                "Se detecto un pico de entradas. Se activo el modo de bloqueo temporal.",
            ),
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name=tr(lang, "Entradas na janela", "Joins in window", "Entradas en la ventana"), value=str(join_count), inline=True)
        embed.add_field(name=tr(lang, "Janela (s)", "Window (s)", "Ventana (s)"), value=str(int(settings.get("window_seconds") or 15)), inline=True)
        embed.add_field(name=tr(lang, "Bloqueio ate", "Lock until", "Bloqueo hasta"), value=discord.utils.format_dt(lock_until, style="R"), inline=True)

        try:
            await channel.send(embed=embed)
        except Exception:
            return

    async def _apply_raid_action(self, member: discord.Member, settings: dict[str, object]) -> bool:
        action = str(settings.get("action") or "kick").lower()
        reason = "Luma anti-raid temporary lock"

        try:
            if action == "ban":
                await member.guild.ban(member, reason=reason, delete_message_days=0)
            else:
                await member.guild.kick(member, reason=reason)
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False

    async def _check_raid_guard(self, member: discord.Member) -> bool:
        settings = await self._get_raid_settings(member.guild.id)
        if not bool(settings.get("enabled")):
            return False

        now = datetime.utcnow()
        self.raid_last_join_at[member.guild.id] = now
        window_seconds = max(5, int(settings.get("window_seconds") or 15))
        threshold = max(3, int(settings.get("join_threshold") or 7))
        min_age_days = max(0, int(settings.get("min_account_age_days") or 7))
        auto_lock_minutes = max(1, int(settings.get("auto_lock_minutes") or 10))
        recovery_minutes = max(1, int(settings.get("recovery_cooldown_minutes") or 10))
        mode = str(settings.get("mode") or "lockdown").lower()

        timestamps = [ts for ts in self.raid_joins_window.get(member.guild.id, []) if (now - ts).total_seconds() <= window_seconds]
        timestamps.append(now)
        self.raid_joins_window[member.guild.id] = timestamps

        preventive_until = self.raid_preventive_until.get(member.guild.id)
        if preventive_until is not None and now >= preventive_until:
            self.raid_preventive_until.pop(member.guild.id, None)
            preventive_until = None

        lock_until = self.raid_lock_until.get(member.guild.id)
        if lock_until is not None and now >= lock_until:
            self.raid_lock_until.pop(member.guild.id, None)
            lock_until = None

        if mode == "recovery" and lock_until is not None:
            last_join = self.raid_last_join_at.get(member.guild.id)
            if last_join and (now - last_join).total_seconds() >= recovery_minutes * 60:
                self.raid_lock_until.pop(member.guild.id, None)
                lock_until = None

        if lock_until is None and len(timestamps) >= threshold:
            incident_lock_until = now + timedelta(minutes=auto_lock_minutes)
            await self.database.execute(
                """
                INSERT INTO raid_incidents (guild_id, window_seconds, join_count, action, lock_until, notes)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                member.guild.id,
                window_seconds,
                len(timestamps),
                str(settings.get("action") or "kick"),
                incident_lock_until,
                f"mode={mode}",
            )

            if mode == "preventive":
                self.raid_preventive_until[member.guild.id] = incident_lock_until
                await self._notify_raid_alert(member.guild, settings, join_count=len(timestamps), lock_until=incident_lock_until)
            else:
                lock_until = incident_lock_until
                self.raid_lock_until[member.guild.id] = lock_until
                await self._notify_raid_alert(member.guild, settings, join_count=len(timestamps), lock_until=lock_until)

        if lock_until is None:
            return False

        created_at = member.created_at
        created_utc = created_at.replace(tzinfo=None) if created_at.tzinfo else created_at
        account_age_days = max(0, int((now - created_utc).total_seconds() // 86400))

        if account_age_days >= min_age_days:
            return False

        return await self._apply_raid_action(member, settings)

    def _is_preventive_mode_active(self, guild_id: int) -> bool:
        until = self.raid_preventive_until.get(guild_id)
        if until is None:
            return False
        if datetime.utcnow() >= until:
            self.raid_preventive_until.pop(guild_id, None)
            return False
        return True

    @staticmethod
    def _resolve_embed_color(raw_color: object, fallback: discord.Color) -> discord.Color:
        if isinstance(raw_color, str):
            normalized = raw_color.strip().lstrip("#")
            if len(normalized) in {3, 6}:
                try:
                    if len(normalized) == 3:
                        normalized = "".join(ch * 2 for ch in normalized)
                    return discord.Color(int(normalized, 16))
                except ValueError:
                    return fallback
        return fallback

    @staticmethod
    def _render_template(raw_text: object, *, member: discord.Member) -> str:
        template = str(raw_text or "")
        return template.replace("{member}", member.mention).replace("{guild}", member.guild.name)

    async def _send_entry_exit_embed(self, member: discord.Member, settings: dict[str, object], *, is_join: bool) -> None:
        if is_join:
            enabled = bool(settings.get("welcome_enabled"))
            channel_id = settings.get("welcome_channel_id")
            title_raw = settings.get("welcome_title")
            description_raw = settings.get("welcome_description")
            color = self._resolve_embed_color(settings.get("welcome_color"), discord.Color.green())
        else:
            enabled = bool(settings.get("leave_enabled"))
            channel_id = settings.get("leave_channel_id")
            title_raw = settings.get("leave_title")
            description_raw = settings.get("leave_description")
            color = self._resolve_embed_color(settings.get("leave_color"), discord.Color.orange())

        if not enabled or not channel_id:
            return

        try:
            channel = member.guild.get_channel(int(channel_id))
        except (TypeError, ValueError):
            return

        if not isinstance(channel, discord.TextChannel):
            return

        title = self._render_template(title_raw, member=member)[:256]
        description = self._render_template(description_raw, member=member)[:4096]
        if not title and not description:
            return

        embed = discord.Embed(
            title=title or None,
            description=description or None,
            color=color,
            timestamp=discord.utils.utcnow(),
        )

        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            return

    @staticmethod
    def _is_member_immune(member: discord.Member, settings: dict[str, object]) -> bool:
        if member.guild_permissions.administrator:
            return True
        if member.guild_permissions.manage_guild or member.guild_permissions.manage_messages or member.guild_permissions.ban_members or member.guild_permissions.kick_members:
            return True

        immune_ids = settings.get("immune_role_ids") or []
        member_role_ids = {role.id for role in member.roles}
        return any(int(role_id) in member_role_ids for role_id in immune_ids)

    async def _get_log_channel(self, guild: discord.Guild, settings: dict[str, object]) -> discord.TextChannel | None:
        if not bool(settings.get("logs_enabled")):
            return None

        channel_id = settings.get("log_channel_id")
        if not channel_id:
            return None

        channel = guild.get_channel(int(channel_id))
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _log_event(self, guild: discord.Guild, title: str, description: str, *, color: discord.Color, enabled: bool) -> None:
        if not enabled:
            return

        settings = await self._get_guild_settings(guild.id)
        log_channel = await self._get_log_channel(guild, settings)
        if log_channel is None:
            return

        embed = discord.Embed(title=title, description=description[:4096], color=color, timestamp=discord.utils.utcnow())
        try:
            await log_channel.send(embed=embed)
        except Exception:
            return

    async def _delete_message(self, message: discord.Message) -> None:
        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            return

    async def _apply_quarantine_role(self, message: discord.Message, settings: dict[str, object]) -> None:
        role_id = settings.get("automod_quarantine_role_id")
        if not role_id or not isinstance(message.author, discord.Member):
            return

        role = message.guild.get_role(int(role_id))
        if role is None:
            return

        try:
            await message.author.add_roles(role, reason="Luma AutoMod quarantine")
        except (discord.Forbidden, discord.HTTPException):
            return

    async def _issue_warning(self, message: discord.Message, settings: dict[str, object], *, reason: str) -> None:
        if not bool(settings.get("auto_moderation")):
            return

        warning_row = await self.database.fetchrow(
            """
            INSERT INTO user_warnings (guild_id, user_id, warning_count)
            VALUES ($1, $2, 1)
            ON CONFLICT (guild_id, user_id)
            DO UPDATE SET warning_count = user_warnings.warning_count + 1, warned_at = CURRENT_TIMESTAMP
            RETURNING warning_count
            """,
            message.guild.id,
            message.author.id,
        )

        warning_count = int(warning_row["warning_count"]) if warning_row else 1
        escalation_rows = await self.database.fetch(
            "SELECT threshold, action FROM guild_warning_escalations WHERE guild_id = $1 ORDER BY threshold ASC",
            message.guild.id,
        )
        escalation_steps = [
            {"threshold": int(item["threshold"]), "action": str(item["action"]).lower()}
            for item in escalation_rows
            if item and item["threshold"] is not None and item["action"] is not None
        ]
        if not escalation_steps:
            escalation_steps = [{"threshold": int(settings.get("quant_warnings") or 3), "action": str(settings.get("acao") or "kick").lower()}]

        warning_limit = max(step["threshold"] for step in escalation_steps)
        lang = await self._guild_lang(message.guild)

        embed = discord.Embed(
            title=tr(lang, "AutoMod aplicou um aviso", "AutoMod issued a warning", "AutoMod aplico una advertencia"),
            description=tr(
                lang,
                f"{message.author.mention}, sua mensagem foi sinalizada: {reason}",
                f"{message.author.mention}, your message was flagged: {reason}",
                f"{message.author.mention}, tu mensaje fue marcado: {reason}",
            ),
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name=tr(lang, "Avisos", "Warnings", "Advertencias"), value=f"{warning_count}/{warning_limit}", inline=True)
        await message.channel.send(embed=embed, delete_after=12)

        if bool(settings.get("warn_dm_user")):
            try:
                dm_embed = discord.Embed(
                    title=tr(lang, "Aviso automatico", "Automatic warning", "Advertencia automatica"),
                    description=tr(
                        lang,
                        f"Voce recebeu um aviso em **{message.guild.name}**. Motivo: {reason}",
                        f"You received a warning in **{message.guild.name}**. Reason: {reason}",
                        f"Recibiste una advertencia en **{message.guild.name}**. Motivo: {reason}",
                    ),
                    color=discord.Color.orange(),
                    timestamp=discord.utils.utcnow(),
                )
                await message.author.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        matching_step = next((step for step in escalation_steps if warning_count == int(step["threshold"])), None)
        if matching_step is None:
            return

        action = str(matching_step["action"])
        try:
            if action == "kick":
                await message.guild.kick(message.author, reason="Automod warn limit")
                action_text = tr(lang, "expulso(a)", "kicked", "expulsado(a)")
                color = discord.Color.orange()
            elif action == "ban":
                await message.guild.ban(message.author, reason="Automod warn limit", delete_message_days=0)
                action_text = tr(lang, "banido(a)", "banned", "baneado(a)")
                color = discord.Color.red()
            elif action in {"mute", "timeout"}:
                await message.author.timeout(discord.utils.utcnow() + timedelta(hours=1), reason="Automod warn limit")
                action_text = tr(lang, "silenciado(a)", "timed out", "silenciado(a)")
                color = discord.Color.yellow()
            else:
                return

            escalation_embed = discord.Embed(
                title=tr(lang, "Limite de avisos atingido", "Warning limit reached", "Limite de avisos alcanzado"),
                description=tr(
                    lang,
                    f"{message.author.mention} foi {action_text} por atingir o limite de avisos.",
                    f"{message.author.mention} was {action_text} for reaching the warning limit.",
                    f"{message.author.mention} fue {action_text} por alcanzar el limite de advertencias.",
                ),
                color=color,
                timestamp=discord.utils.utcnow(),
            )
            await message.channel.send(embed=escalation_embed)
        except (discord.Forbidden, discord.HTTPException):
            return

    async def _handle_violation(self, message: discord.Message, settings: dict[str, object], *, public_reason: str, warn_reason: str) -> bool:
        await self._delete_message(message)
        await self._apply_quarantine_role(message, settings)
        await self._issue_warning(message, settings, reason=warn_reason)
        await message.channel.send(f"{message.author.mention}, {public_reason}", delete_after=10)
        return True

    async def _handle_spam_messages(self, message: discord.Message, settings: dict[str, object]) -> bool:
        if not bool(settings.get("smart_antiflood")):
            return False

        lang = await self._guild_lang(message.guild)
        now = datetime.utcnow()
        key = (message.guild.id, message.author.id)
        preventive = self._is_preventive_mode_active(message.guild.id)

        timestamps = [ts for ts in self.spam_cooldown.get(key, []) if (now - ts).total_seconds() < 5]
        timestamps.append(now)
        self.spam_cooldown[key] = timestamps

        invite_filter_on = bool(settings.get("automod_invite_filter")) or preventive
        link_filter_on = bool(settings.get("automod_link_filter")) or preventive

        if invite_filter_on and self.invite_pattern.search(message.content):
            return await self._handle_violation(
                message,
                settings,
                public_reason=tr(lang, "convites nao sao permitidos aqui.", "server invites are not allowed here.", "las invitaciones no estan permitidas aqui."),
                warn_reason="Invite link detected",
            )

        if link_filter_on and self.link_pattern.search(message.content) and not self.invite_pattern.search(message.content):
            return await self._handle_violation(
                message,
                settings,
                public_reason=tr(lang, "links externos estao bloqueados neste servidor.", "external links are blocked in this server.", "los enlaces externos estan bloqueados en este servidor."),
                warn_reason="External link detected",
            )

        threshold = max(3, int(settings.get("automod_spam_threshold") or self.DEFAULT_SPAM_THRESHOLD))
        if preventive:
            threshold = max(3, threshold - 2)
        if len(timestamps) >= threshold:
            return await self._handle_violation(
                message,
                settings,
                public_reason=tr(lang, "voce esta enviando mensagens rapido demais. Espera um pouco.", "you are sending messages too fast. Slow down for a moment.", "estas enviando mensajes demasiado rapido. Espera un momento."),
                warn_reason="Spam threshold exceeded",
            )

        return False

    async def _handle_message_quality(self, message: discord.Message, settings: dict[str, object]) -> bool:
        if not bool(settings.get("smart_antiflood")):
            return False

        lang = await self._guild_lang(message.guild)
        preventive = self._is_preventive_mode_active(message.guild.id)

        if (bool(settings.get("automod_caps_filter")) or preventive) and len(message.content) > 10:
            caps_count = sum(1 for char in message.content if char.isupper())
            caps_ratio = caps_count / max(len(message.content), 1)
            if caps_ratio > self.max_caps_ratio:
                return await self._handle_violation(
                    message,
                    settings,
                    public_reason=tr(lang, "usa menos maiusculas para ficar mais facil de ler.", "please use less uppercase text so it is easier to read.", "usa menos mayusculas para que sea mas facil de leer."),
                    warn_reason="Excessive caps detected",
                )

        if len(message.content) > 5:
            max_repeat = max((len(list(group)) for _, group in itertools.groupby(message.content)), default=0)
            if max_repeat > 10:
                return await self._handle_violation(
                    message,
                    settings,
                    public_reason=tr(lang, "vamos evitar repeticoes exageradas.", "let's avoid excessive repetitions.", "evitemos repeticiones excesivas."),
                    warn_reason="Repeated characters detected",
                )

        emojis = self.emoji_pattern.findall(message.content)
        if len(emojis) > self.max_emojis:
            return await self._handle_violation(
                message,
                settings,
                public_reason=tr(lang, "muitos emojis de uma vez. Vamos dosar um pouco.", "too many emojis at once. Let's tone it down a bit.", "demasiados emojis de una vez. Vamos a bajarlo un poco."),
                warn_reason="Too many emojis detected",
            )

        mention_count = len(message.mentions) + len(message.role_mentions)
        if mention_count > 5:
            return await self._handle_violation(
                message,
                settings,
                public_reason=tr(lang, "evite mencionar muitas pessoas ao mesmo tempo.", "please avoid mentioning too many people at once.", "por favor evita mencionar a demasiadas personas al mismo tiempo."),
                warn_reason="Mass mention detected",
            )

        return False

    @commands.Cog.listener()
    async def on_ready(self):
        print("[DEBUG Events Cog] on_ready called")
        print(f"[EVENTS] Online: {self.bot.user}")

    @raid.command(name="status", description="Mostra o status atual do anti-raid")
    async def raid_status(self, interaction: discord.Interaction):
        lang = await self._guild_lang(interaction.guild)
        if interaction.guild is None:
            await interaction.response.send_message(
                tr(lang, "Esse comando so funciona em servidor.", "This command only works in a server.", "Este comando solo funciona en servidor."),
                ephemeral=True,
            )
            return

        settings = await self._get_raid_settings(interaction.guild.id)
        now = datetime.utcnow()
        lock_until = self.raid_lock_until.get(interaction.guild.id)
        active_lock = lock_until is not None and now < lock_until

        embed = discord.Embed(
            title=tr(lang, "Status do anti-raid", "Anti-raid status", "Estado del anti-raid"),
            color=discord.Color.orange() if active_lock else discord.Color.green(),
        )
        embed.add_field(name=tr(lang, "Ativado", "Enabled", "Activado"), value=str(bool(settings.get("enabled"))), inline=True)
        embed.add_field(name=tr(lang, "Threshold", "Threshold", "Umbral"), value=str(int(settings.get("join_threshold") or 7)), inline=True)
        embed.add_field(name=tr(lang, "Janela", "Window", "Ventana"), value=f"{int(settings.get('window_seconds') or 15)}s", inline=True)
        embed.add_field(name=tr(lang, "Idade minima", "Minimum age", "Edad minima"), value=f"{int(settings.get('min_account_age_days') or 7)}d", inline=True)
        embed.add_field(name=tr(lang, "Lock", "Lock", "Bloqueo"), value=f"{int(settings.get('auto_lock_minutes') or 10)}m", inline=True)
        embed.add_field(name=tr(lang, "Acao", "Action", "Accion"), value=str(settings.get("action") or "kick"), inline=True)
        embed.add_field(name=tr(lang, "Modo", "Mode", "Modo"), value=str(settings.get("mode") or "lockdown"), inline=True)

        if active_lock and lock_until is not None:
            embed.add_field(name=tr(lang, "Modo raid ativo", "Raid mode active", "Modo raid activo"), value=discord.utils.format_dt(lock_until, style="R"), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @raid.command(name="config", description="Configura o anti-raid inteligente")
    @app_commands.choices(action=[
        app_commands.Choice(name="kick", value="kick"),
        app_commands.Choice(name="ban", value="ban"),
    ])
    @app_commands.choices(mode=[
        app_commands.Choice(name="preventive", value="preventive"),
        app_commands.Choice(name="lockdown", value="lockdown"),
        app_commands.Choice(name="recovery", value="recovery"),
    ])
    async def raid_config(
        self,
        interaction: discord.Interaction,
        enabled: bool,
        join_threshold: app_commands.Range[int, 3, 50] = 7,
        window_seconds: app_commands.Range[int, 5, 120] = 15,
        min_account_age_days: app_commands.Range[int, 0, 60] = 7,
        auto_lock_minutes: app_commands.Range[int, 1, 120] = 10,
        action: app_commands.Choice[str] | None = None,
        mode: app_commands.Choice[str] | None = None,
        recovery_cooldown_minutes: app_commands.Range[int, 1, 120] = 10,
        notify_channel: discord.TextChannel | None = None,
    ):
        lang = await self._guild_lang(interaction.guild)
        if interaction.guild is None:
            await interaction.response.send_message(
                tr(lang, "Esse comando so funciona em servidor.", "This command only works in a server.", "Este comando solo funciona en servidor."),
                ephemeral=True,
            )
            return

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                tr(lang, "Voce precisa de Manage Server para configurar o anti-raid.", "You need Manage Server to configure anti-raid.", "Necesitas Manage Server para configurar anti-raid."),
                ephemeral=True,
            )
            return

        payload = {
            "enabled": bool(enabled),
            "join_threshold": int(join_threshold),
            "window_seconds": int(window_seconds),
            "min_account_age_days": int(min_account_age_days),
            "auto_lock_minutes": int(auto_lock_minutes),
            "action": str(action.value).lower() if action else "kick",
            "mode": str(mode.value).lower() if mode else "lockdown",
            "recovery_cooldown_minutes": int(recovery_cooldown_minutes),
            "notify_channel_id": notify_channel.id if notify_channel else None,
        }
        await self._save_raid_settings(interaction.guild.id, payload)

        await interaction.response.send_message(
            tr(
                lang,
                f"Anti-raid atualizado. enabled={payload['enabled']} mode={payload['mode']} threshold={payload['join_threshold']} window={payload['window_seconds']}s age={payload['min_account_age_days']}d lock={payload['auto_lock_minutes']}m recovery={payload['recovery_cooldown_minutes']}m action={payload['action']}",
                f"Anti-raid updated. enabled={payload['enabled']} mode={payload['mode']} threshold={payload['join_threshold']} window={payload['window_seconds']}s age={payload['min_account_age_days']}d lock={payload['auto_lock_minutes']}m recovery={payload['recovery_cooldown_minutes']}m action={payload['action']}",
                f"Anti-raid actualizado. enabled={payload['enabled']} mode={payload['mode']} threshold={payload['join_threshold']} window={payload['window_seconds']}s age={payload['min_account_age_days']}d lock={payload['auto_lock_minutes']}m recovery={payload['recovery_cooldown_minutes']}m action={payload['action']}",
            ),
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not await self.bot.is_cog_enabled(member.guild.id, "events"):
            return

        blocked = await self._check_raid_guard(member)
        if blocked:
            return

        settings = await self._get_guild_settings(member.guild.id)
        await self._send_entry_exit_embed(member, settings, is_join=True)
        lang = await self._guild_lang(member.guild)
        await self._log_event(
            member.guild,
            tr(lang, "Membro entrou", "Member joined", "Miembro entro"),
            tr(lang, f"{member.mention} entrou no servidor.", f"{member.mention} joined the server.", f"{member.mention} se unio al servidor."),
            color=discord.Color.green(),
            enabled=bool(settings.get("log_join_leave")),
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if not await self.bot.is_cog_enabled(member.guild.id, "events"):
            return

        settings = await self._get_guild_settings(member.guild.id)
        await self._send_entry_exit_embed(member, settings, is_join=False)
        lang = await self._guild_lang(member.guild)
        await self._log_event(
            member.guild,
            tr(lang, "Membro saiu", "Member left", "Miembro salio"),
            tr(lang, f"{member} saiu do servidor.", f"{member} left the server.", f"{member} salio del servidor."),
            color=discord.Color.orange(),
            enabled=bool(settings.get("log_join_leave")),
        )

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return

        if not await self.bot.is_cog_enabled(message.guild.id, "events"):
            return

        settings = await self._get_guild_settings(message.guild.id)
        if not bool(settings.get("log_message_delete")):
            return

        lang = await self._guild_lang(message.guild)
        content = message.content or tr(lang, "Sem conteudo de texto.", "No text content.", "Sin contenido de texto.")
        description = tr(
            lang,
            f"Mensagem apagada de {message.author.mention} em {message.channel.mention}\n\n{content}",
            f"Deleted message from {message.author.mention} in {message.channel.mention}\n\n{content}",
            f"Mensaje eliminado de {message.author.mention} en {message.channel.mention}\n\n{content}",
        )
        await self._log_event(
            message.guild,
            tr(lang, "Mensagem apagada", "Message deleted", "Mensaje eliminado"),
            description,
            color=discord.Color.red(),
            enabled=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        if not await self.bot.is_cog_enabled(message.guild.id, "events"):
            await self.bot.process_commands(message)
            return

        settings = await self._get_guild_settings(message.guild.id)
        if isinstance(message.author, discord.Member) and self._is_member_immune(message.author, settings):
            await self.bot.process_commands(message)
            return

        violation_detected = await self._handle_spam_messages(message, settings)
        if not violation_detected:
            violation_detected = await self._handle_message_quality(message, settings)

        if violation_detected:
            return

        await self.bot.process_commands(message)


async def setup(bot):
    print("[DEBUG] Carregando cog Events...")
    await bot.add_cog(Events(bot))
    print("[DEBUG] Cog Events carregado com sucesso!")
