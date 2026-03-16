from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

import scripts.db

Database = scripts.db.Database


TEXTS = {
    "guild_only": {
        "pt": "Ops! Este comando so funciona dentro de servidores.",
        "en": "Oops! This command only works inside servers.",
        "es": "Ups! Este comando solo funciona dentro de servidores.",
    },
    "mail_disabled": {
        "pt": "O modmail esta desativado neste servidor pelo painel.",
        "en": "Modmail is disabled in this server by the dashboard.",
        "es": "El modmail esta desactivado en este servidor por el panel.",
    },
    "modmail_not_configured": {
        "pt": "Ainda nao existe ModMail configurado aqui. Peca para um admin usar /setup.",
        "en": "ModMail is not configured yet here. Ask an admin to run /setup.",
        "es": "Aun no hay ModMail configurado aqui. Pide a un admin que use /setup.",
    },
    "invalid_modmail_channel": {
        "pt": "Este comando so funciona em canais de ModMail, combinado?",
        "en": "This command only works in ModMail channels, alright?",
        "es": "Este comando solo funciona en canales de ModMail, vale?",
    },
    "user_not_found": {
        "pt": "Nao consegui identificar o usuario deste ModMail agora.",
        "en": "I could not identify the user for this ModMail right now.",
        "es": "No pude identificar al usuario de este ModMail ahora mismo.",
    },
    "sent_ok": {
        "pt": "Prontinho! Mensagem enviada para a equipe de moderacao.",
        "en": "All set! Message sent to the moderation team.",
        "es": "Listo! Mensaje enviado al equipo de moderacion.",
    },
    "reply_ok": {
        "pt": "Resposta enviada para {user} com sucesso.",
        "en": "Reply sent to {user} successfully.",
        "es": "Respuesta enviada a {user} correctamente.",
    },
    "close_confirm": {
        "pt": "Quer mesmo fechar o ModMail de {user}?",
        "en": "Do you really want to close {user}'s ModMail?",
        "es": "De verdad quieres cerrar el ModMail de {user}?",
    },
    "close_done": {
        "pt": "ModMail fechado com sucesso. Tudo certinho por aqui.",
        "en": "ModMail closed successfully. Everything is tidy now.",
        "es": "ModMail cerrado correctamente. Todo quedo en orden.",
    },
    "close_cancel": {
        "pt": "Fechamento cancelado. O ModMail continua aberto.",
        "en": "Close cancelled. The ModMail stays open.",
        "es": "Cierre cancelado. El ModMail sigue abierto.",
    },
    "auto_closed": {
        "pt": "ModMail fechado automaticamente por inatividade.",
        "en": "ModMail closed automatically due to inactivity.",
        "es": "ModMail cerrado automaticamente por inactividad.",
    },
    "dm_forbidden": {
        "pt": "Nao consegui enviar DM para o usuario (talvez esteja bloqueada).",
        "en": "I could not send DM to the user (it may be blocked).",
        "es": "No pude enviar DM al usuario (puede que este bloqueado).",
    },
    "appeal_exists": {
        "pt": "Ja existe uma apelacao aberta para voce. Continue por la, combinado?",
        "en": "There is already an open appeal for you. Please continue there.",
        "es": "Ya existe una apelacion abierta para ti. Continuala alli.",
    },
    "appeal_created": {
        "pt": "Sua apelacao foi enviada com sucesso. A equipe vai analisar assim que possivel.",
        "en": "Your appeal was sent successfully. The team will review it as soon as possible.",
        "es": "Tu apelacion fue enviada correctamente. El equipo la revisara lo antes posible.",
    },
    "appeal_channel_label": {
        "pt": "Canal da apelacao",
        "en": "Appeal channel",
        "es": "Canal de apelacion",
    },
    "appeal_modal_title": {
        "pt": "Enviar apelacao",
        "en": "Submit appeal",
        "es": "Enviar apelacion",
    },
    "appeal_subject_label": {
        "pt": "Assunto da apelacao",
        "en": "Appeal subject",
        "es": "Asunto de la apelacion",
    },
    "appeal_subject_placeholder": {
        "pt": "Ex: Reconsideracao de banimento",
        "en": "Example: Ban reconsideration",
        "es": "Ej: Reconsideracion del baneo",
    },
    "appeal_message_label": {
        "pt": "Explique seu recurso",
        "en": "Explain your appeal",
        "es": "Explica tu apelacion",
    },
    "appeal_message_placeholder": {
        "pt": "Descreva o contexto, o que aconteceu e por que a equipe deveria revisar o caso.",
        "en": "Describe the context, what happened, and why the team should review your case.",
        "es": "Describe el contexto, que paso y por que el equipo deberia revisar tu caso.",
    },
    "appeal_staff_title": {
        "pt": "Nova apelacao",
        "en": "New appeal",
        "es": "Nueva apelacion",
    },
    "appeal_staff_description": {
        "pt": "Uma nova apelacao foi aberta sem alerta automatico de cargo.",
        "en": "A new appeal was opened without automatic role ping.",
        "es": "Se abrio una nueva apelacion sin ping automatico de rol.",
    },
    "appeal_user_title": {
        "pt": "Apelacao registrada",
        "en": "Appeal submitted",
        "es": "Apelacion registrada",
    },
    "appeal_subject_field": {
        "pt": "Assunto",
        "en": "Subject",
        "es": "Asunto",
    },
    "appeal_message_field": {
        "pt": "Apelacao",
        "en": "Appeal",
        "es": "Apelacion",
    },
    "appeal_status_field": {
        "pt": "Status",
        "en": "Status",
        "es": "Estado",
    },
    "appeal_status_open": {
        "pt": "Aberta para analise",
        "en": "Open for review",
        "es": "Abierta para revision",
    },
    "appeal_guidance_field": {
        "pt": "Proximos passos",
        "en": "Next steps",
        "es": "Siguientes pasos",
    },
    "appeal_guidance_value": {
        "pt": "Revise o contexto, responda no canal e use /mail fechar quando a decisao for concluida.",
        "en": "Review the context, reply in the channel, and use /mail fechar when the decision is complete.",
        "es": "Revisa el contexto, responde en el canal y usa /mail fechar cuando la decision este completa.",
    },
    "appeal_accept_button": {
        "pt": "Aceitar apelacao",
        "en": "Accept appeal",
        "es": "Aceptar apelacion",
    },
    "appeal_reject_button": {
        "pt": "Negar apelacao",
        "en": "Reject appeal",
        "es": "Rechazar apelacion",
    },
    "appeal_staff_only": {
        "pt": "Apenas a staff com permissao de moderacao pode decidir apelacoes.",
        "en": "Only staff with moderation permissions can decide appeals.",
        "es": "Solo el staff con permisos de moderacion puede decidir apelaciones.",
    },
    "appeal_accepted_title": {
        "pt": "Apelacao aceita",
        "en": "Appeal accepted",
        "es": "Apelacion aceptada",
    },
    "appeal_rejected_title": {
        "pt": "Apelacao negada",
        "en": "Appeal rejected",
        "es": "Apelacion rechazada",
    },
    "appeal_decision_dm": {
        "pt": "Sua apelacao no servidor **{guild}** foi marcada como **{decision}** por {moderator}.",
        "en": "Your appeal in **{guild}** was marked as **{decision}** by {moderator}.",
        "es": "Tu apelacion en **{guild}** fue marcada como **{decision}** por {moderator}.",
    },
    "appeal_accepted_label": {
        "pt": "aceita",
        "en": "accepted",
        "es": "aceptada",
    },
    "appeal_rejected_label": {
        "pt": "negada",
        "en": "rejected",
        "es": "rechazada",
    },
    "appeal_decision_by": {
        "pt": "Decisao por",
        "en": "Decision by",
        "es": "Decision por",
    },
    "appeal_decision_logged": {
        "pt": "A decisao foi registrada e os botoes foram bloqueados.",
        "en": "The decision was logged and the buttons were disabled.",
        "es": "La decision fue registrada y los botones fueron desactivados.",
    },
}


class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.database = Database(bot.pool)
        self.modmail_idle_watcher.start()

    def cog_unload(self):
        self.modmail_idle_watcher.cancel()

    mail = app_commands.Group(name="mail", description="ModMail commands")

    async def _lang(self, interaction: discord.Interaction) -> str:
        return await self.bot.i18n.language_for_interaction(self.bot, interaction)

    @staticmethod
    def _t(key: str, lang: str, **kwargs) -> str:
        return TEXTS[key].get(lang, TEXTS[key]["pt"]).format(**kwargs)

    async def _fetch_settings(self, guild_id: int) -> dict[str, object]:
        row = await self.database.fetchrow(
            """
            SELECT
                modmail_category_id,
                modmail_alert_role_id,
                modmail_anonymous_replies,
                modmail_close_on_idle,
                modmail_auto_close_hours,
                logs_enabled,
                log_modmail_transcripts,
                log_channel_id
            FROM guilds
            WHERE guild_id = $1
            """,
            guild_id,
        )

        defaults: dict[str, object] = {
            "modmail_category_id": None,
            "modmail_alert_role_id": None,
            "modmail_alert_role_ids": [],
            "modmail_anonymous_replies": False,
            "modmail_close_on_idle": True,
            "modmail_auto_close_hours": 48,
            "logs_enabled": True,
            "log_modmail_transcripts": True,
            "log_channel_id": None,
        }
        if row is None:
            return defaults

        payload = dict(row)
        defaults.update({key: value for key, value in payload.items() if value is not None})

        role_rows = await self.database.fetch(
            "SELECT role_id FROM guild_modmail_roles WHERE guild_id = $1 ORDER BY role_id",
            guild_id,
        )
        role_ids = [int(item["role_id"]) for item in role_rows if item and item["role_id"] is not None]
        if role_ids:
            defaults["modmail_alert_role_ids"] = role_ids
        elif defaults.get("modmail_alert_role_id"):
            defaults["modmail_alert_role_ids"] = [int(defaults["modmail_alert_role_id"])]

        return defaults

    async def _ensure_mail_enabled(self, interaction: discord.Interaction, lang: str) -> bool:
        if interaction.guild is None:
            return True
        if await self.bot.is_cog_enabled(interaction.guild.id, "mail"):
            return True
        await self._send_error(interaction, "Error", self._t("mail_disabled", lang))
        return False

    async def _extract_user_from_channel(self, channel: discord.TextChannel) -> discord.User | None:
        try:
            user_id = int(channel.name.split("-")[-1])
            return await self.bot.fetch_user(user_id)
        except (ValueError, discord.NotFound):
            return None

    async def _channel_last_activity(self, channel: discord.TextChannel) -> datetime:
        async for last_message in channel.history(limit=1):
            return last_message.created_at.replace(tzinfo=None)
        return channel.created_at.replace(tzinfo=None)

    @staticmethod
    def _safe_channel_slug(prefix: str, user: discord.abc.User) -> str:
        base_name = f"{prefix}-{user.name}".lower().replace(" ", "-")
        safe_name = "".join(ch for ch in base_name if ch.isalnum() or ch == "-")[:80]
        return f"{safe_name}-{user.id}"[:95]

    @staticmethod
    def _can_manage_appeals(member: discord.abc.User | discord.Member | None) -> bool:
        if not isinstance(member, discord.Member):
            return False
        perms = member.guild_permissions
        return bool(
            perms.administrator
            or perms.manage_guild
            or perms.manage_messages
            or perms.moderate_members
            or perms.ban_members
        )

    async def _build_transcript(self, channel: discord.TextChannel) -> str:
        lines: list[str] = []
        async for message in channel.history(limit=100, oldest_first=True):
            content = message.content.strip() if message.content else ""
            if not content and message.embeds:
                embed = message.embeds[0]
                content = embed.description or embed.title or "[embed]"
            content = content or "[sem texto]"
            safe_content = content.replace("\r", " ").replace("\n", " ")
            lines.append(f"[{message.created_at:%Y-%m-%d %H:%M}] {message.author}: {safe_content[:180]}")

        transcript = "\n".join(lines)
        return transcript[:3900] if transcript else "[empty transcript]"

    async def _log_transcript(self, guild: discord.Guild, settings: dict[str, object], channel: discord.TextChannel, closer: str, reason: str | None = None) -> None:
        if not bool(settings.get("logs_enabled")) or not bool(settings.get("log_modmail_transcripts")):
            return

        log_channel_id = settings.get("log_channel_id")
        if not log_channel_id:
            return

        log_channel = guild.get_channel(int(log_channel_id))
        if not isinstance(log_channel, discord.TextChannel):
            return

        transcript = await self._build_transcript(channel)
        embed = discord.Embed(
            title="ModMail Transcript",
            description=transcript,
            color=discord.Color.dark_blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Channel", value=channel.name, inline=True)
        embed.add_field(name="Closed By", value=closer, inline=True)
        if reason:
            embed.add_field(name="Reason", value=reason[:1024], inline=False)

        try:
            await log_channel.send(embed=embed)
        except Exception:
            return

    @tasks.loop(minutes=30)
    async def modmail_idle_watcher(self):
        for guild in self.bot.guilds:
            if not await self.bot.is_cog_enabled(guild.id, "mail"):
                continue

            settings = await self._fetch_settings(guild.id)
            if not bool(settings.get("modmail_close_on_idle")):
                continue

            category_id = settings.get("modmail_category_id")
            if not category_id:
                continue

            category = guild.get_channel(int(category_id))
            if not isinstance(category, discord.CategoryChannel):
                continue

            idle_hours = max(1, int(settings.get("modmail_auto_close_hours") or 48))
            threshold = datetime.utcnow() - timedelta(hours=idle_hours)
            lang = await self.bot.i18n.get_guild_language(self.bot.pool, guild.id)

            for channel in category.text_channels:
                if not channel.name.startswith("modmail-"):
                    continue

                try:
                    last_activity = await self._channel_last_activity(channel)
                except Exception:
                    continue

                if last_activity > threshold:
                    continue

                user = await self._extract_user_from_channel(channel)
                if user is not None:
                    try:
                        await user.send(self._t("auto_closed", lang))
                    except discord.Forbidden:
                        pass

                await self._log_transcript(guild, settings, channel, closer="AutoClose", reason="Inactive modmail")
                try:
                    await channel.delete(reason="Auto-closed due to inactivity")
                except (discord.Forbidden, discord.HTTPException):
                    continue

    @modmail_idle_watcher.before_loop
    async def before_modmail_idle_watcher(self):
        await self.bot.wait_until_ready()

    async def _send_error(self, interaction: discord.Interaction, title: str, description: str):
        embed = discord.Embed(title=title, description=description, color=discord.Color.red())
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _send_success(self, interaction: discord.Interaction, title: str, description: str):
        embed = discord.Embed(title=title, description=description, color=discord.Color.green())
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _notify_appeal_decision(
        self,
        user: discord.User,
        guild: discord.Guild,
        moderator: discord.abc.User,
        lang: str,
        accepted: bool,
    ) -> None:
        decision_key = "appeal_accepted_label" if accepted else "appeal_rejected_label"
        title_key = "appeal_accepted_title" if accepted else "appeal_rejected_title"
        embed = discord.Embed(
            title=self._t(title_key, lang),
            description=self._t(
                "appeal_decision_dm",
                lang,
                guild=guild.name,
                decision=self._t(decision_key, lang),
                moderator=getattr(moderator, "mention", str(moderator)),
            ),
            color=discord.Color.green() if accepted else discord.Color.red(),
            timestamp=datetime.now(),
        )
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            pass

    @mail.command(name="enviar", description="Enviar mensagem para a equipe de moderacao")
    async def modmail(self, interaction: discord.Interaction, assunto: str, mensagem: str):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await self._send_error(interaction, "Error", self._t("guild_only", lang))
            return

        if not await self._ensure_mail_enabled(interaction, lang):
            return

        settings = await self._fetch_settings(interaction.guild.id)
        if settings["modmail_category_id"] is None:
            await self._send_error(interaction, "Error", self._t("modmail_not_configured", lang))
            return

        category = interaction.guild.get_channel(int(settings["modmail_category_id"]))
        if not isinstance(category, discord.CategoryChannel):
            await self._send_error(interaction, "Error", self._t("modmail_not_configured", lang))
            return

        channel_name = self._safe_channel_slug("modmail", interaction.user)

        channel = discord.utils.get(category.text_channels, name=channel_name)
        channel_created = channel is None
        if channel is None:
            channel = await category.create_text_channel(
                channel_name,
                topic=f"ModMail user {interaction.user} ({interaction.user.id})",
            )

        staff_embed = discord.Embed(
            title="ModMail",
            description=self._t("sent_ok", lang) + f"\n{interaction.user.mention}",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        staff_embed.add_field(name={"pt": "Assunto", "en": "Subject", "es": "Asunto"}[lang], value=assunto[:1024], inline=False)
        staff_embed.add_field(name={"pt": "Mensagem", "en": "Message", "es": "Mensaje"}[lang], value=mensagem[:1024], inline=False)

        if channel_created and settings.get("modmail_alert_role_ids"):
            mentions = []
            for role_id in settings.get("modmail_alert_role_ids", []):
                role = interaction.guild.get_role(int(role_id))
                if role is not None:
                    mentions.append(role.mention)
            await channel.send(content=" ".join(mentions) if mentions else None, embed=staff_embed)
        else:
            await channel.send(embed=staff_embed)

        user_embed = discord.Embed(
            title="ModMail",
            description=self._t("sent_ok", lang),
            color=discord.Color.green(),
            timestamp=datetime.now(),
        )
        user_embed.add_field(name={"pt": "Assunto", "en": "Subject", "es": "Asunto"}[lang], value=assunto[:1024], inline=False)
        user_embed.add_field(name={"pt": "Mensagem", "en": "Message", "es": "Mensaje"}[lang], value=mensagem[:1024], inline=False)
        await interaction.response.send_message(embed=user_embed, ephemeral=True)

    @mail.command(name="responder", description="Responder um ModMail")
    async def reply(self, interaction: discord.Interaction, mensagem: str):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await self._send_error(interaction, "Error", self._t("guild_only", lang))
            return

        if not await self._ensure_mail_enabled(interaction, lang):
            return

        if not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
            await self._send_error(interaction, "Error", self._t("invalid_modmail_channel", lang))
            return

        if not interaction.channel.name.startswith("modmail-"):
            await self._send_error(interaction, "Error", self._t("invalid_modmail_channel", lang))
            return

        user = await self._extract_user_from_channel(interaction.channel)
        if user is None:
            await self._send_error(interaction, "Error", self._t("user_not_found", lang))
            return

        settings = await self._fetch_settings(interaction.guild.id)
        anonymous = bool(settings.get("modmail_anonymous_replies"))

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            dm_embed = discord.Embed(
                title={"pt": "Resposta de ModMail", "en": "ModMail Reply", "es": "Respuesta de ModMail"}[lang],
                description={"pt": "Servidor", "en": "Server", "es": "Servidor"}[lang] + f": {interaction.guild.name if interaction.guild else '-'}",
                color=discord.Color.blurple(),
                timestamp=datetime.now(),
            )
            dm_embed.add_field(name={"pt": "Mensagem", "en": "Message", "es": "Mensaje"}[lang], value=mensagem[:1024], inline=False)
            dm_embed.add_field(
                name={"pt": "Equipe", "en": "Team", "es": "Equipo"}[lang] if anonymous else {"pt": "Moderador", "en": "Moderator", "es": "Moderador"}[lang],
                value="Luma Staff" if anonymous else interaction.user.mention,
                inline=False,
            )
            await user.send(embed=dm_embed)

            log_embed = discord.Embed(
                title={"pt": "Resposta Enviada", "en": "Reply Sent", "es": "Respuesta Enviada"}[lang],
                description={"pt": "Para", "en": "To", "es": "Para"}[lang] + f": {user.mention}",
                color=discord.Color.green(),
                timestamp=datetime.now(),
            )
            log_embed.add_field(name={"pt": "Mensagem", "en": "Message", "es": "Mensaje"}[lang], value=mensagem[:1024], inline=False)
            log_embed.add_field(name={"pt": "Modo", "en": "Mode", "es": "Modo"}[lang], value="Anonymous" if anonymous else "Named", inline=True)
            await interaction.channel.send(embed=log_embed)

            await interaction.followup.send(self._t("reply_ok", lang, user=user.mention), ephemeral=True)
        except discord.Forbidden:
            await self._send_error(interaction, "Error", self._t("dm_forbidden", lang))

    @mail.command(name="fechar", description="Fechar um ModMail aberto")
    async def close(self, interaction: discord.Interaction, motivo: str | None = None):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await self._send_error(interaction, "Error", self._t("guild_only", lang))
            return

        if not await self._ensure_mail_enabled(interaction, lang):
            return

        if not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
            await self._send_error(interaction, "Error", self._t("invalid_modmail_channel", lang))
            return

        if not interaction.channel.name.startswith("modmail-"):
            await self._send_error(interaction, "Error", self._t("invalid_modmail_channel", lang))
            return

        user = await self._extract_user_from_channel(interaction.channel)
        if user is None:
            await self._send_error(interaction, "Error", self._t("user_not_found", lang))
            return

        settings = await self._fetch_settings(interaction.guild.id)

        class CloseView(discord.ui.View):
            def __init__(self, cog: "Utils"):
                super().__init__(timeout=60)
                self.cog = cog
                confirm_button = discord.ui.Button(
                    label={"pt": "Confirmar", "en": "Confirm", "es": "Confirmar"}[lang],
                    style=discord.ButtonStyle.danger,
                )
                cancel_button = discord.ui.Button(
                    label={"pt": "Cancelar", "en": "Cancel", "es": "Cancelar"}[lang],
                    style=discord.ButtonStyle.secondary,
                )
                confirm_button.callback = self.confirm
                cancel_button.callback = self.cancel
                self.add_item(confirm_button)
                self.add_item(cancel_button)

            async def confirm(self, btn_interaction: discord.Interaction):
                await btn_interaction.response.defer(ephemeral=True)
                try:
                    dm_embed = discord.Embed(
                        title={"pt": "ModMail Fechado", "en": "ModMail Closed", "es": "ModMail Cerrado"}[lang],
                        description=motivo or {"pt": "Sem motivo", "en": "No reason provided", "es": "Sin motivo"}[lang],
                        color=discord.Color.red(),
                        timestamp=datetime.now(),
                    )
                    await user.send(embed=dm_embed)
                except discord.Forbidden:
                    pass

                await self.cog._log_transcript(interaction.guild, settings, interaction.channel, closer=str(interaction.user), reason=motivo)
                await interaction.channel.delete(reason=f"ModMail closed by {interaction.user}")
                await btn_interaction.followup.send(self.cog._t("close_done", lang), ephemeral=True)

            async def cancel(self, btn_interaction: discord.Interaction):
                await btn_interaction.response.send_message(self.cog._t("close_cancel", lang), ephemeral=True)

        embed = discord.Embed(
            title={"pt": "Fechar ModMail", "en": "Close ModMail", "es": "Cerrar ModMail"}[lang],
            description=self._t("close_confirm", lang, user=user.mention),
            color=discord.Color.orange(),
        )
        if motivo:
            embed.add_field(name={"pt": "Motivo", "en": "Reason", "es": "Motivo"}[lang], value=motivo[:1024], inline=False)

        await interaction.response.send_message(embed=embed, view=CloseView(self), ephemeral=True)

    @mail.command(name="appelar", description="Apelar para reabrir um ModMail fechado")
    async def appeal(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await self._send_error(interaction, "Error", self._t("guild_only", lang))
            return

        if not await self._ensure_mail_enabled(interaction, lang):
            return

        settings = await self._fetch_settings(interaction.guild.id)
        if settings["modmail_category_id"] is None:
            await self._send_error(interaction, "Error", self._t("modmail_not_configured", lang))
            return

        category = interaction.guild.get_channel(int(settings["modmail_category_id"]))
        if not isinstance(category, discord.CategoryChannel):
            await self._send_error(interaction, "Error", self._t("modmail_not_configured", lang))
            return

        cog = self

        class AppealModal(discord.ui.Modal, title=TEXTS["appeal_modal_title"][lang]):
            subject = discord.ui.TextInput(
                label=TEXTS["appeal_subject_label"][lang],
                placeholder=TEXTS["appeal_subject_placeholder"][lang],
                max_length=120,
            )
            message = discord.ui.TextInput(
                label=TEXTS["appeal_message_label"][lang],
                placeholder=TEXTS["appeal_message_placeholder"][lang],
                style=discord.TextStyle.paragraph,
                max_length=1500,
            )

            async def on_submit(self, modal_interaction: discord.Interaction):
                channel_name = cog._safe_channel_slug("appeal", modal_interaction.user)
                existing_channel = discord.utils.get(category.text_channels, name=channel_name)
                overwrite = discord.PermissionOverwrite(
                    send_messages=True,
                    read_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                )

                channel = existing_channel
                created_now = False
                if channel is None:
                    channel = await category.create_text_channel(
                        channel_name,
                        topic=f"ModMail appeal from {modal_interaction.user} ({modal_interaction.user.id})",
                        overwrites={modal_interaction.user: overwrite},
                    )
                    created_now = True

                if channel is None:
                    await cog._send_error(modal_interaction, "Error", cog._t("modmail_not_configured", lang))
                    return

                if not created_now:
                    await cog._send_error(modal_interaction, "Error", cog._t("appeal_exists", lang))
                    return

                class AppealDecisionView(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=None)

                    async def _resolve(self, button_interaction: discord.Interaction, accepted: bool):
                        if not cog._can_manage_appeals(button_interaction.user):
                            await cog._send_error(button_interaction, "Error", cog._t("appeal_staff_only", lang))
                            return

                        decision_title = cog._t("appeal_accepted_title", lang) if accepted else cog._t("appeal_rejected_title", lang)
                        decision_label = cog._t("appeal_accepted_label", lang) if accepted else cog._t("appeal_rejected_label", lang)

                        for item in self.children:
                            item.disabled = True

                        decision_embed = discord.Embed(
                            title=decision_title,
                            description=cog._t("appeal_decision_logged", lang),
                            color=discord.Color.green() if accepted else discord.Color.red(),
                            timestamp=datetime.now(),
                        )
                        decision_embed.add_field(
                            name=cog._t("appeal_status_field", lang),
                            value=decision_label,
                            inline=True,
                        )
                        decision_embed.add_field(
                            name=cog._t("appeal_decision_by", lang),
                            value=button_interaction.user.mention,
                            inline=True,
                        )

                        await cog._notify_appeal_decision(
                            modal_interaction.user,
                            modal_interaction.guild,
                            button_interaction.user,
                            lang,
                            accepted,
                        )

                        await button_interaction.response.edit_message(view=self)
                        await channel.send(embed=decision_embed)

                    @discord.ui.button(label=TEXTS["appeal_accept_button"][lang], style=discord.ButtonStyle.success)
                    async def accept(self, button_interaction: discord.Interaction, _: discord.ui.Button):
                        await self._resolve(button_interaction, accepted=True)

                    @discord.ui.button(label=TEXTS["appeal_reject_button"][lang], style=discord.ButtonStyle.danger)
                    async def reject(self, button_interaction: discord.Interaction, _: discord.ui.Button):
                        await self._resolve(button_interaction, accepted=False)

                staff_embed = discord.Embed(
                    title=cog._t("appeal_staff_title", lang),
                    description=f"{cog._t('appeal_staff_description', lang)}\n{modal_interaction.user.mention}",
                    color=discord.Color.orange(),
                    timestamp=datetime.now(),
                )
                staff_embed.add_field(name=cog._t("appeal_subject_field", lang), value=str(self.subject)[:1024], inline=False)
                staff_embed.add_field(name=cog._t("appeal_message_field", lang), value=str(self.message)[:1024], inline=False)
                staff_embed.add_field(name=cog._t("appeal_status_field", lang), value=cog._t("appeal_status_open", lang), inline=True)
                staff_embed.add_field(name=cog._t("appeal_guidance_field", lang), value=cog._t("appeal_guidance_value", lang), inline=False)

                user_embed = discord.Embed(
                    title=cog._t("appeal_user_title", lang),
                    description=cog._t("appeal_created", lang),
                    color=discord.Color.green(),
                    timestamp=datetime.now(),
                )
                user_embed.add_field(name=cog._t("appeal_subject_field", lang), value=str(self.subject)[:1024], inline=False)
                user_embed.add_field(
                    name=cog._t("appeal_channel_label", lang),
                    value=channel.mention,
                    inline=False,
                )

                await channel.send(embed=staff_embed, view=AppealDecisionView())
                await cog._send_success(modal_interaction, cog._t("appeal_user_title", lang), cog._t("appeal_created", lang) + f"\n{channel.mention}")

                try:
                    await modal_interaction.user.send(embed=user_embed)
                except discord.Forbidden:
                    pass

        await interaction.response.send_modal(AppealModal())


async def setup(bot):
    print("[DEBUG] Carregando cog Mail...")
    await bot.add_cog(Utils(bot))
    print("[DEBUG] Cog Mail carregado com sucesso!")
