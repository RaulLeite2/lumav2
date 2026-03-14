from datetime import datetime, timedelta
import itertools
import re

import discord
from discord.ext import commands

import scripts.db


def tr(lang: str, pt: str, en: str, es: str) -> str:
    return {"pt": pt, "en": en, "es": es}.get(lang, pt)


class Events(commands.Cog):
    DEFAULT_SPAM_THRESHOLD = 6

    def __init__(self, bot):
        self.bot = bot
        self.database = scripts.db.Database(bot.pool)
        self.spam_cooldown: dict[tuple[int, int], list[datetime]] = {}
        self.max_caps_ratio = 0.70
        self.max_emojis = 10
        self.invite_pattern = re.compile(r"discord\.gg/\w+|discord(app)?\.com/invite/\w+", re.IGNORECASE)
        self.link_pattern = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
        self.emoji_pattern = re.compile(r"<a?:\w+:\d+>|[\U0001F600-\U0001F64F]|[\U0001F300-\U0001F5FF]|[\U0001F680-\U0001F6FF]|[\U0001F900-\U0001F9FF]|[\U0001FA70-\U0001FAFF]")

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
        }
        if row is None:
            role_rows = await self.database.fetch(
                "SELECT role_id FROM guild_immune_roles WHERE guild_id = $1 ORDER BY role_id",
                guild_id,
            )
            defaults["immune_role_ids"] = [int(item["role_id"]) for item in role_rows if item and item["role_id"] is not None]
            return defaults

        payload = dict(row)
        defaults.update({key: value for key, value in payload.items() if value is not None})
        role_rows = await self.database.fetch(
            "SELECT role_id FROM guild_immune_roles WHERE guild_id = $1 ORDER BY role_id",
            guild_id,
        )
        defaults["immune_role_ids"] = [int(item["role_id"]) for item in role_rows if item and item["role_id"] is not None]
        return defaults

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

        timestamps = [ts for ts in self.spam_cooldown.get(key, []) if (now - ts).total_seconds() < 5]
        timestamps.append(now)
        self.spam_cooldown[key] = timestamps

        if bool(settings.get("automod_invite_filter")) and self.invite_pattern.search(message.content):
            return await self._handle_violation(
                message,
                settings,
                public_reason=tr(lang, "convites nao sao permitidos aqui.", "server invites are not allowed here.", "las invitaciones no estan permitidas aqui."),
                warn_reason="Invite link detected",
            )

        if bool(settings.get("automod_link_filter")) and self.link_pattern.search(message.content) and not self.invite_pattern.search(message.content):
            return await self._handle_violation(
                message,
                settings,
                public_reason=tr(lang, "links externos estao bloqueados neste servidor.", "external links are blocked in this server.", "los enlaces externos estan bloqueados en este servidor."),
                warn_reason="External link detected",
            )

        threshold = max(3, int(settings.get("automod_spam_threshold") or self.DEFAULT_SPAM_THRESHOLD))
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

        if bool(settings.get("automod_caps_filter")) and len(message.content) > 10:
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

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not await self.bot.is_cog_enabled(member.guild.id, "events"):
            return

        settings = await self._get_guild_settings(member.guild.id)
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
