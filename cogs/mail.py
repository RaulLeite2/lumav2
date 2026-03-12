from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

import scripts.db

Database = scripts.db.Database


TEXTS = {
    "guild_only": {
        "pt": "Ops! Este comando so funciona dentro de servidores.",
        "en": "Oops! This command only works inside servers.",
        "es": "Ups! Este comando solo funciona dentro de servidores.",
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
    "dm_forbidden": {
        "pt": "Nao consegui enviar DM para o usuario (talvez esteja bloqueada).",
        "en": "I could not send DM to the user (it may be blocked).",
        "es": "No pude enviar DM al usuario (puede que este bloqueado).",
    },
}


class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    mail = app_commands.Group(name="mail", description="ModMail commands")

    async def _lang(self, interaction: discord.Interaction) -> str:
        return await self.bot.i18n.language_for_interaction(self.bot, interaction)

    @staticmethod
    def _t(key: str, lang: str, **kwargs) -> str:
        return TEXTS[key].get(lang, TEXTS[key]["pt"]).format(**kwargs)

    async def _send_error(self, interaction: discord.Interaction, title: str, description: str):
        embed = discord.Embed(title=title, description=description, color=discord.Color.red())
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @mail.command(name="enviar", description="Enviar mensagem para a equipe de moderacao")
    async def modmail(self, interaction: discord.Interaction, assunto: str, mensagem: str):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await self._send_error(interaction, "Error", self._t("guild_only", lang))
            return

        db = Database(self.bot.pool)
        row = await db.fetchrow("SELECT modmail_category_id FROM guilds WHERE guild_id = $1", interaction.guild.id)
        if row is None or row["modmail_category_id"] is None:
            await self._send_error(interaction, "Error", self._t("modmail_not_configured", lang))
            return

        category = interaction.guild.get_channel(row["modmail_category_id"])
        if not isinstance(category, discord.CategoryChannel):
            await self._send_error(interaction, "Error", self._t("modmail_not_configured", lang))
            return

        base_name = f"modmail-{interaction.user.name}".lower().replace(" ", "-")
        safe_name = "".join(ch for ch in base_name if ch.isalnum() or ch == "-")[:80]
        channel_name = f"{safe_name}-{interaction.user.id}"[:95]

        channel = discord.utils.get(category.text_channels, name=channel_name)
        if channel is None:
            channel = await category.create_text_channel(
                channel_name,
                topic=f"ModMail user {interaction.user} ({interaction.user.id})",
            )

        staff_embed = discord.Embed(
            title="ModMail",
            description=\
                self._t("sent_ok", lang) + f"\n{interaction.user.mention}",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        staff_embed.add_field(name={"pt": "Assunto", "en": "Subject", "es": "Asunto"}[lang], value=assunto[:1024], inline=False)
        staff_embed.add_field(name={"pt": "Mensagem", "en": "Message", "es": "Mensaje"}[lang], value=mensagem[:1024], inline=False)
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
        if not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
            await self._send_error(interaction, "Error", self._t("invalid_modmail_channel", lang))
            return

        if not interaction.channel.name.startswith("modmail-"):
            await self._send_error(interaction, "Error", self._t("invalid_modmail_channel", lang))
            return

        try:
            user_id = int(interaction.channel.name.split("-")[-1])
            user = await self.bot.fetch_user(user_id)
        except (ValueError, discord.NotFound):
            await self._send_error(interaction, "Error", self._t("user_not_found", lang))
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            dm_embed = discord.Embed(
                title={"pt": "Resposta de ModMail", "en": "ModMail Reply", "es": "Respuesta de ModMail"}[lang],
                description={"pt": "Servidor", "en": "Server", "es": "Servidor"}[lang] + f": {interaction.guild.name if interaction.guild else '-'}",
                color=discord.Color.blurple(),
                timestamp=datetime.now(),
            )
            dm_embed.add_field(name={"pt": "Mensagem", "en": "Message", "es": "Mensaje"}[lang], value=mensagem[:1024], inline=False)
            dm_embed.add_field(name={"pt": "Moderador", "en": "Moderator", "es": "Moderador"}[lang], value=interaction.user.mention, inline=False)
            await user.send(embed=dm_embed)

            log_embed = discord.Embed(
                title={"pt": "Resposta Enviada", "en": "Reply Sent", "es": "Respuesta Enviada"}[lang],
                description={"pt": "Para", "en": "To", "es": "Para"}[lang] + f": {user.mention}",
                color=discord.Color.green(),
                timestamp=datetime.now(),
            )
            log_embed.add_field(name={"pt": "Mensagem", "en": "Message", "es": "Mensaje"}[lang], value=mensagem[:1024], inline=False)
            await interaction.channel.send(embed=log_embed)

            await interaction.followup.send(self._t("reply_ok", lang, user=user.mention), ephemeral=True)
        except discord.Forbidden:
            await self._send_error(interaction, "Error", self._t("dm_forbidden", lang))

    @mail.command(name="fechar", description="Fechar um ModMail aberto")
    async def close(self, interaction: discord.Interaction, motivo: str | None = None):
        lang = await self._lang(interaction)
        if not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
            await self._send_error(interaction, "Error", self._t("invalid_modmail_channel", lang))
            return

        if not interaction.channel.name.startswith("modmail-"):
            await self._send_error(interaction, "Error", self._t("invalid_modmail_channel", lang))
            return

        try:
            user_id = int(interaction.channel.name.split("-")[-1])
            user = await self.bot.fetch_user(user_id)
        except (ValueError, discord.NotFound):
            await self._send_error(interaction, "Error", self._t("user_not_found", lang))
            return

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


async def setup(bot):
    print("[DEBUG] Carregando cog Mail...")
    await bot.add_cog(Utils(bot))
    print("[DEBUG] Cog Mail carregado com sucesso!")
