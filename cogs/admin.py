import discord
from discord import app_commands
from discord.ext import commands


def tr(lang: str, pt: str, en: str, es: str) -> str:
    return {"pt": pt, "en": en, "es": es}.get(lang, pt)


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

    @admin.command(name="embed", description="Send a custom embed")
    async def embed(self, interaction: discord.Interaction, titulo: str, descricao: str, cor_hex: str | None = None):
        lang = await self._lang(interaction)
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(tr(lang, "Voce precisa de Gerenciar Mensagens.", "You need Manage Messages permission.", "Necesitas permiso Gestionar Mensajes."), ephemeral=True)
            return

        color = discord.Color.blue()
        if cor_hex:
            try:
                color = discord.Color(int(cor_hex.strip().lstrip("#"), 16))
            except ValueError:
                await interaction.response.send_message(tr(lang, "Cor invalida. Use hexadecimal.", "Invalid color. Use hexadecimal.", "Color invalido. Usa hexadecimal."), ephemeral=True)
                return

        embed = discord.Embed(title=titulo[:256], description=descricao[:4096], color=color)
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message(tr(lang, "Embed enviado.", "Embed sent.", "Embed enviado."), ephemeral=True)

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
