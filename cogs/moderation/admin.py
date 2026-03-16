import discord
from discord import app_commands
from discord.ext import commands
from dataclasses import dataclass
from urllib.parse import urlparse


def tr(lang: str, pt: str, en: str, es: str) -> str:
    return {"pt": pt, "en": en, "es": es}.get(lang, pt)


@dataclass
class EmbedDraft:
    title: str
    description: str
    content: str | None = None
    footer: str | None = None
    image_url: str | None = None
    thumbnail_url: str | None = None
    author_name: str | None = None
    author_icon_url: str | None = None
    color_hex: str | None = None
    use_timestamp: bool = False


class EmbedTextModal(discord.ui.Modal):
    def __init__(self, view: "EmbedBuilderView"):
        self.view = view
        lang = view.lang
        super().__init__(title=tr(lang, "Editar conteudo do embed", "Edit embed content", "Editar contenido del embed"))

        self.title_input = discord.ui.TextInput(
            label=tr(lang, "Titulo", "Title", "Titulo"),
            default=view.draft.title,
            max_length=256,
            required=True,
        )
        self.description_input = discord.ui.TextInput(
            label=tr(lang, "Descricao", "Description", "Descripcion"),
            default=view.draft.description,
            style=discord.TextStyle.paragraph,
            max_length=4000,
            required=True,
        )
        self.content_input = discord.ui.TextInput(
            label=tr(lang, "Mensagem acima do embed", "Message above embed", "Mensaje arriba del embed"),
            default=view.draft.content or "",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=False,
        )
        self.footer_input = discord.ui.TextInput(
            label=tr(lang, "Rodape", "Footer", "Pie"),
            default=view.draft.footer or "",
            max_length=2048,
            required=False,
        )

        self.add_item(self.title_input)
        self.add_item(self.description_input)
        self.add_item(self.content_input)
        self.add_item(self.footer_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.view.draft.title = self.title_input.value.strip()
        self.view.draft.description = self.description_input.value.strip()
        self.view.draft.content = self.content_input.value.strip() or None
        self.view.draft.footer = self.footer_input.value.strip() or None

        await interaction.response.defer()
        await self.view.refresh_message()


class EmbedMediaModal(discord.ui.Modal):
    def __init__(self, view: "EmbedBuilderView"):
        self.view = view
        lang = view.lang
        super().__init__(title=tr(lang, "Editar midia do embed", "Edit embed media", "Editar media del embed"))

        self.author_name_input = discord.ui.TextInput(
            label=tr(lang, "Nome do autor", "Author name", "Nombre del autor"),
            default=view.draft.author_name or "",
            max_length=256,
            required=False,
        )
        self.author_icon_input = discord.ui.TextInput(
            label=tr(lang, "URL do icone do autor", "Author icon URL", "URL del icono del autor"),
            default=view.draft.author_icon_url or "",
            max_length=500,
            required=False,
        )
        self.thumbnail_input = discord.ui.TextInput(
            label=tr(lang, "URL da thumbnail", "Thumbnail URL", "URL de la miniatura"),
            default=view.draft.thumbnail_url or "",
            max_length=500,
            required=False,
        )
        self.image_input = discord.ui.TextInput(
            label=tr(lang, "URL da imagem", "Image URL", "URL de la imagen"),
            default=view.draft.image_url or "",
            max_length=500,
            required=False,
        )

        self.add_item(self.author_name_input)
        self.add_item(self.author_icon_input)
        self.add_item(self.thumbnail_input)
        self.add_item(self.image_input)

    async def on_submit(self, interaction: discord.Interaction):
        lang = self.view.lang

        try:
            self.view.draft.author_icon_url = self.view.cog._validate_url(self.author_icon_input.value.strip() or None)
            self.view.draft.thumbnail_url = self.view.cog._validate_url(self.thumbnail_input.value.strip() or None)
            self.view.draft.image_url = self.view.cog._validate_url(self.image_input.value.strip() or None)
        except ValueError:
            await interaction.response.send_message(
                tr(
                    lang,
                    "Uma das URLs esta invalida. Use apenas links http ou https.",
                    "One of the URLs is invalid. Use only http or https links.",
                    "Una de las URLs es invalida. Usa solo enlaces http o https.",
                ),
                ephemeral=True,
            )
            return

        self.view.draft.author_name = self.author_name_input.value.strip() or None
        await interaction.response.defer()
        await self.view.refresh_message()


class EmbedColorModal(discord.ui.Modal):
    def __init__(self, view: "EmbedBuilderView"):
        self.view = view
        lang = view.lang
        super().__init__(title=tr(lang, "Cor personalizada", "Custom color", "Color personalizada"))

        self.color_input = discord.ui.TextInput(
            label=tr(lang, "Cor hexadecimal", "Hex color", "Color hexadecimal"),
            placeholder="#55DFCF",
            default=view.draft.color_hex or "",
            max_length=7,
            required=False,
        )
        self.add_item(self.color_input)

    async def on_submit(self, interaction: discord.Interaction):
        lang = self.view.lang
        raw_value = self.color_input.value.strip() or None

        try:
            self.view.cog._parse_hex_color(raw_value)
        except ValueError:
            await interaction.response.send_message(
                tr(lang, "Cor invalida. Use um hexadecimal como #55DFCF.", "Invalid color. Use hex like #55DFCF.", "Color invalido. Usa un hexadecimal como #55DFCF."),
                ephemeral=True,
            )
            return

        self.view.draft.color_hex = raw_value
        await interaction.response.defer()
        await self.view.refresh_message()


class EmbedBuilderView(discord.ui.View):
    def __init__(self, cog: "Admin", author_id: int, target_channel: discord.TextChannel, lang: str, draft: EmbedDraft):
        super().__init__(timeout=600)
        self.cog = cog
        self.author_id = author_id
        self.target_channel = target_channel
        self.lang = lang
        self.draft = draft
        self.message: discord.InteractionMessage | None = None
        self._sync_color_buttons()

    def _sync_color_buttons(self) -> None:
        current = (self.draft.color_hex or "#55DFCF").lower().lstrip("#")
        self.color_aqua.style = discord.ButtonStyle.success if current == "55dfcf" else discord.ButtonStyle.secondary
        self.color_blue.style = discord.ButtonStyle.primary if current == "7eb6ff" else discord.ButtonStyle.secondary
        self.color_amber.style = discord.ButtonStyle.danger if current == "ffb06f" else discord.ButtonStyle.secondary

        if self.draft.use_timestamp:
            self.toggle_timestamp.label = tr(self.lang, "Timestamp: ligado", "Timestamp: on", "Timestamp: activo")
            self.toggle_timestamp.style = discord.ButtonStyle.success
        else:
            self.toggle_timestamp.label = tr(self.lang, "Timestamp: desligado", "Timestamp: off", "Timestamp: apagado")
            self.toggle_timestamp.style = discord.ButtonStyle.secondary

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                tr(self.lang, "So quem abriu o criador pode usar estes botoes.", "Only the person who opened the builder can use these buttons.", "Solo quien abrio el constructor puede usar estos botones."),
                ephemeral=True,
            )
            return False
        return True

    def build_status_embed(self) -> discord.Embed:
        status = discord.Embed(
            title=tr(self.lang, "Criador de Embed", "Embed Builder", "Constructor de Embeds"),
            description=tr(
                self.lang,
                "Use os botoes abaixo para editar texto, midia, cor e publicar quando estiver pronto.",
                "Use the buttons below to edit text, media, color and publish when ready.",
                "Usa los botones de abajo para editar texto, media, color y publicar cuando este listo.",
            ),
            color=discord.Color.dark_embed(),
        )
        status.add_field(name=tr(self.lang, "Canal", "Channel", "Canal"), value=self.target_channel.mention, inline=True)
        status.add_field(name=tr(self.lang, "Cor", "Color", "Color"), value=self.draft.color_hex or "#55DFCF", inline=True)
        status.add_field(
            name=tr(self.lang, "Timestamp", "Timestamp", "Timestamp"),
            value=tr(self.lang, "Ligado" if self.draft.use_timestamp else "Desligado", "On" if self.draft.use_timestamp else "Off", "Activo" if self.draft.use_timestamp else "Apagado"),
            inline=True,
        )
        status.add_field(name=tr(self.lang, "Mensagem", "Message", "Mensaje"), value=self.draft.content[:1024] if self.draft.content else tr(self.lang, "Nenhuma", "None", "Ninguno"), inline=False)
        return status

    async def refresh_message(self) -> None:
        if self.message is None:
            return
        self._sync_color_buttons()
        await self.message.edit(embeds=[self.build_status_embed(), self.cog._build_embed_from_draft(self.draft)], view=self)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            await self.message.edit(view=self)

    @discord.ui.button(label="Texto", style=discord.ButtonStyle.primary, row=0)
    async def edit_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmbedTextModal(self))

    @discord.ui.button(label="Midia", style=discord.ButtonStyle.primary, row=0)
    async def edit_media(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmbedMediaModal(self))

    @discord.ui.button(label="Cor custom", style=discord.ButtonStyle.secondary, row=0)
    async def custom_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmbedColorModal(self))

    @discord.ui.button(label="Timestamp", style=discord.ButtonStyle.secondary, row=0)
    async def toggle_timestamp(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.draft.use_timestamp = not self.draft.use_timestamp
        await interaction.response.defer()
        await self.refresh_message()

    @discord.ui.button(label="Aqua", style=discord.ButtonStyle.secondary, row=1)
    async def color_aqua(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.draft.color_hex = "#55DFCF"
        await interaction.response.defer()
        await self.refresh_message()

    @discord.ui.button(label="Blue", style=discord.ButtonStyle.secondary, row=1)
    async def color_blue(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.draft.color_hex = "#7EB6FF"
        await interaction.response.defer()
        await self.refresh_message()

    @discord.ui.button(label="Amber", style=discord.ButtonStyle.secondary, row=1)
    async def color_amber(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.draft.color_hex = "#FFB06F"
        await interaction.response.defer()
        await self.refresh_message()

    @discord.ui.button(label="Publicar", style=discord.ButtonStyle.success, row=1)
    async def publish(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.target_channel.send(
            content=self.draft.content[:2000] if self.draft.content else None,
            embed=self.cog._build_embed_from_draft(self.draft),
            allowed_mentions=discord.AllowedMentions.none(),
        )

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            embeds=[
                discord.Embed(
                    title=tr(self.lang, "Embed publicado", "Embed published", "Embed publicado"),
                    description=tr(
                        self.lang,
                        f"O embed foi enviado em {self.target_channel.mention}.",
                        f"The embed was sent to {self.target_channel.mention}.",
                        f"El embed fue enviado a {self.target_channel.mention}.",
                    ),
                    color=discord.Color.green(),
                )
            ],
            view=self,
        )
        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            embeds=[
                discord.Embed(
                    title=tr(self.lang, "Criacao cancelada", "Creation cancelled", "Creacion cancelada"),
                    description=tr(
                        self.lang,
                        "Nenhum embed foi publicado.",
                        "No embed was published.",
                        "No se publico ningun embed.",
                    ),
                    color=discord.Color.red(),
                )
            ],
            view=self,
        )
        self.stop()


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    admin = app_commands.Group(name="admin", description="Administrative commands")

    async def _lang(self, interaction: discord.Interaction) -> str:
        return await self.bot.i18n.language_for_interaction(self.bot, interaction)

    async def _send_ephemeral(self, interaction: discord.Interaction, message: str) -> None:
        if not interaction.response.is_done():
            await interaction.response.send_message(message, ephemeral=True)
        else:
            await interaction.followup.send(message, ephemeral=True)

    @staticmethod
    def _parse_hex_color(color_value: str | None) -> discord.Color:
        if not color_value:
            return discord.Color.from_rgb(85, 223, 207)

        cleaned = color_value.strip().lstrip("#")
        if len(cleaned) not in {3, 6}:
            raise ValueError("invalid hex length")

        if len(cleaned) == 3:
            cleaned = "".join(char * 2 for char in cleaned)

        return discord.Color(int(cleaned, 16))

    @staticmethod
    def _validate_url(url_value: str | None) -> str | None:
        if not url_value:
            return None

        parsed = urlparse(url_value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("invalid url")

        return url_value.strip()

    def _build_embed_from_draft(self, draft: EmbedDraft) -> discord.Embed:
        embed = discord.Embed(
            title=draft.title[:256],
            description=draft.description[:4096],
            color=self._parse_hex_color(draft.color_hex),
            timestamp=discord.utils.utcnow() if draft.use_timestamp else None,
        )

        if draft.author_name:
            embed.set_author(name=draft.author_name[:256], icon_url=draft.author_icon_url)
        if draft.footer:
            embed.set_footer(text=draft.footer[:2048])
        if draft.thumbnail_url:
            embed.set_thumbnail(url=draft.thumbnail_url)
        if draft.image_url:
            embed.set_image(url=draft.image_url)

        return embed

    async def _validate_embed_target(self, interaction: discord.Interaction, target_channel: discord.TextChannel) -> bool:
        lang = await self._lang(interaction)
        bot_member = interaction.guild.get_member(self.bot.user.id) if interaction.guild and self.bot.user else None
        permissions = target_channel.permissions_for(bot_member) if bot_member else None
        if permissions is None or not permissions.send_messages or not permissions.embed_links:
            await self._send_ephemeral(
                interaction,
                tr(
                    lang,
                    "Eu preciso de permissao para enviar mensagens e embeds nesse canal.",
                    "I need permission to send messages and embeds in that channel.",
                    "Necesito permiso para enviar mensajes y embeds en ese canal.",
                ),
            )
            return False
        return True

    async def _validate_manage_channels(self, interaction: discord.Interaction) -> bool:
        lang = await self._lang(interaction)
        if interaction.guild is None or interaction.channel is None:
            await self._send_ephemeral(interaction, tr(lang, "Esse comando so funciona em servidor.", "This command only works in a server.", "Este comando solo funciona en servidor."))
            return False

        if not interaction.user.guild_permissions.manage_channels:
            await self._send_ephemeral(interaction, tr(lang, "Voce precisa de Gerenciar Canais.", "You need Manage Channels permission.", "Necesitas permiso Gestionar Canales."))
            return False

        return True

    @admin.command(name="sync", description="Sync slash commands")
    @app_commands.checks.has_permissions(administrator=True)
    async def sync(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        await interaction.response.defer(ephemeral=True, thinking=True)

        guild_synced = 0
        if interaction.guild is not None:
            self.bot.tree.clear_commands(guild=interaction.guild)
            guild_synced = len(await self.bot.tree.sync(guild=interaction.guild))

        global_synced = len(await self.bot.tree.sync())
        await interaction.followup.send(
            tr(
                lang,
                f"Sincronizacao concluida. Servidor: {guild_synced}. Global: {global_synced}.",
                f"Sync complete. Server: {guild_synced}. Global: {global_synced}.",
                f"Sincronizacion completa. Servidor: {guild_synced}. Global: {global_synced}.",
            ),
            ephemeral=True,
        )

    @sync.error
    async def sync_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        lang = await self._lang(interaction)
        if isinstance(error, app_commands.MissingPermissions):
            await self._send_ephemeral(interaction, tr(lang, "So administradores podem usar este comando.", "Only administrators can use this command.", "Solo administradores pueden usar este comando."))
            return
        await self._send_ephemeral(interaction, str(error))

    @admin.command(name="health", description="Check bot health")
    async def health(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        latency_ms = round(self.bot.latency * 1000)
        database_ping = "OK" if self.bot.pool and not self.bot.pool._closed else "OFF"
        await interaction.response.send_message(
            tr(lang, f"Pong! Latencia: {latency_ms}ms | DB: {database_ping}", f"Pong! Latency: {latency_ms}ms | DB: {database_ping}", f"Pong! Latencia: {latency_ms}ms | DB: {database_ping}"),
            ephemeral=True,
        )

    @admin.command(name="lockdown", description="Lock current channel")
    async def lockdown(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        if not await self._validate_manage_channels(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
            await interaction.followup.send(tr(lang, f"Canal {interaction.channel.mention} trancado.", f"Channel {interaction.channel.mention} locked.", f"Canal {interaction.channel.mention} bloqueado."), ephemeral=True)
        except Exception as e:
            await interaction.followup.send(str(e), ephemeral=True)

    @admin.command(name="unlock", description="Unlock current channel")
    async def unlock(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        if not await self._validate_manage_channels(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
            await interaction.followup.send(tr(lang, f"Canal {interaction.channel.mention} destrancado.", f"Channel {interaction.channel.mention} unlocked.", f"Canal {interaction.channel.mention} desbloqueado."), ephemeral=True)
        except Exception as e:
            await interaction.followup.send(str(e), ephemeral=True)

    @admin.command(name="slowmode", description="Set slowmode for current channel")
    async def slowmode(self, interaction: discord.Interaction, segundos: int):
        lang = await self._lang(interaction)
        if not await self._validate_manage_channels(interaction):
            return

        if segundos < 0 or segundos > 21600:
            await interaction.response.send_message(tr(lang, "Valor invalido. Use entre 0 e 21600.", "Invalid value. Use between 0 and 21600.", "Valor invalido. Usa entre 0 y 21600."), ephemeral=True)
            return

        await interaction.channel.edit(slowmode_delay=segundos)
        await interaction.response.send_message(
            tr(lang, f"Slowmode ajustado para {segundos}s.", f"Slowmode set to {segundos}s.", f"Slowmode ajustado a {segundos}s."),
            ephemeral=True,
        )

    @admin.command(name="embed", description="Open an interactive embed builder")
    @app_commands.describe(
        canal="Channel where the embed should be sent",
    )
    async def embed(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel | None = None,
    ):
        lang = await self._lang(interaction)
        if interaction.guild is None or interaction.channel is None:
            await self._send_ephemeral(interaction, tr(lang, "Esse comando so funciona em servidor.", "This command only works in a server.", "Este comando solo funciona en servidor."))
            return

        if not interaction.user.guild_permissions.manage_messages:
            await self._send_ephemeral(interaction, tr(lang, "Voce precisa de Gerenciar Mensagens.", "You need Manage Messages permission.", "Necesitas permiso Gestionar Mensajes."))
            return

        target_channel = canal or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await self._send_ephemeral(interaction, tr(lang, "Escolha um canal de texto valido.", "Choose a valid text channel.", "Elige un canal de texto valido."))
            return

        if not await self._validate_embed_target(interaction, target_channel):
            return

        draft = EmbedDraft(
            title=tr(lang, "Novo anuncio", "New announcement", "Nuevo anuncio"),
            description=tr(
                lang,
                "Escreva uma mensagem clara e profissional para o seu servidor.",
                "Write a clear and professional message for your server.",
                "Escribe un mensaje claro y profesional para tu servidor.",
            ),
            footer=tr(lang, "Publicado com Luma", "Published with Luma", "Publicado con Luma"),
            color_hex="#55DFCF",
        )

        view = EmbedBuilderView(self, interaction.user.id, target_channel, lang, draft)
        await interaction.response.send_message(
            embeds=[view.build_status_embed(), self._build_embed_from_draft(draft)],
            view=view,
            ephemeral=True,
        )
        view.message = await interaction.original_response()

    @admin.command(name="reload", description="Reload bot")
    @app_commands.checks.has_permissions(administrator=True)
    async def reload(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        owner_id = 947849382278094880
        if interaction.user.id != owner_id:
            await interaction.response.send_message(tr(lang, "Voce nao tem permissao para isso.", "You do not have permission for this.", "No tienes permiso para esto."), ephemeral=True)
            return

        await interaction.response.send_message(tr(lang, "Recarregando bot...", "Reloading bot...", "Recargando bot..."), ephemeral=True)
        await self.bot.close()


async def setup(bot):
    print("[DEBUG] Carregando cog Admin...")
    await bot.add_cog(Admin(bot))
    print("[DEBUG] Cog Admin carregado com sucesso!")
