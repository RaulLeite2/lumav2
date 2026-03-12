from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

import scripts.db

Database = scripts.db.Database


def tr(lang: str, pt: str, en: str, es: str) -> str:
    return {"pt": pt, "en": en, "es": es}.get(lang, pt)


class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _lang(self, interaction: discord.Interaction) -> str:
        return await self.bot.i18n.language_for_interaction(self.bot, interaction)

    @app_commands.command(name="setup", description="Server setup panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await interaction.response.send_message(tr(lang, "Ops! Este comando so pode ser usado em servidores.", "Oops! This command can only be used in servers.", "Ups! Este comando solo puede usarse en servidores."), ephemeral=True)
            return

        db = Database(self.bot.pool)

        async def send_status_embed(target_interaction: discord.Interaction):
            guild = target_interaction.guild
            row = await db.fetchrow(
                """
                SELECT
                    log_channel_id,
                    auto_moderation,
                    quant_warnings,
                    acao,
                    modmail_category_id,
                    smart_antiflood,
                    language_code,
                    ticket_default_category_id,
                    ticket_default_support_role_id,
                    ai_enabled
                FROM guilds
                WHERE guild_id = $1
                """,
                guild.id,
            )

            log_channel = guild.get_channel(row["log_channel_id"]) if row and row["log_channel_id"] else None
            modmail_category = guild.get_channel(row["modmail_category_id"]) if row and row["modmail_category_id"] else None
            ticket_default_category = guild.get_channel(row["ticket_default_category_id"]) if row and row["ticket_default_category_id"] else None
            ticket_default_support_role = guild.get_role(row["ticket_default_support_role_id"]) if row and row["ticket_default_support_role_id"] else None
            current_lang = (row["language_code"] if row and row["language_code"] else "pt").upper()
            ai_enabled = True if row is None or row["ai_enabled"] is None else bool(row["ai_enabled"])

            embed = discord.Embed(
                title=tr(lang, "Status atual do setup ✨", "Current setup status ✨", "Estado actual del setup ✨"),
                color=discord.Color.blurple(),
                timestamp=datetime.now(),
            )
            embed.add_field(name=tr(lang, "Canal de logs", "Log channel", "Canal de logs"), value=log_channel.mention if log_channel else tr(lang, "Nao configurado", "Not configured", "No configurado"), inline=False)
            embed.add_field(
                name="AutoMod",
                value=(
                    f"{tr(lang, 'Status', 'Status', 'Estado')}: {tr(lang, 'Ativado' if row and row['auto_moderation'] else 'Desativado', 'Enabled' if row and row['auto_moderation'] else 'Disabled', 'Activado' if row and row['auto_moderation'] else 'Desactivado')}\n"
                    f"{tr(lang, 'Limite', 'Limit', 'Limite')}: {row['quant_warnings'] if row and row['quant_warnings'] else 3}\n"
                    f"{tr(lang, 'Acao', 'Action', 'Accion')}: {(row['acao'] if row and row['acao'] else 'kick').upper()}"
                ),
                inline=False,
            )
            embed.add_field(name=tr(lang, "Anti-flood", "Anti-flood", "Anti-flood"), value=tr(lang, "Ativado" if row and row["smart_antiflood"] else "Desativado", "Enabled" if row and row["smart_antiflood"] else "Disabled", "Activado" if row and row["smart_antiflood"] else "Desactivado"), inline=False)
            embed.add_field(name="ModMail", value=modmail_category.mention if modmail_category else tr(lang, "Nao configurado", "Not configured", "No configurado"), inline=False)
            embed.add_field(
                name=tr(lang, "Padrao de Tickets", "Ticket Defaults", "Valores por Defecto de Tickets"),
                value=(
                    f"{tr(lang, 'Categoria', 'Category', 'Categoria')}: {ticket_default_category.mention if ticket_default_category else tr(lang, 'Nao configurada', 'Not configured', 'No configurada')}\n"
                    f"{tr(lang, 'Cargo de suporte', 'Support role', 'Rol de soporte')}: {ticket_default_support_role.mention if ticket_default_support_role else tr(lang, 'Nao configurado', 'Not configured', 'No configurado')}"
                ),
                inline=False,
            )
            embed.add_field(
                name="AI",
                value=tr(lang, "Ativada" if ai_enabled else "Desativada", "Enabled" if ai_enabled else "Disabled", "Activada" if ai_enabled else "Desactivada"),
                inline=False,
            )
            embed.add_field(name=tr(lang, "Idioma", "Language", "Idioma"), value=current_lang, inline=False)
            embed.set_footer(text=f"{interaction.guild.name}")

            await target_interaction.response.send_message(embed=embed, ephemeral=True)

        class FormAutoModeration(discord.ui.Modal):
            def __init__(self):
                super().__init__(title=tr(lang, "Configurar AutoMod", "Configure AutoMod", "Configurar AutoMod"))
                self.auto_moderation = discord.ui.TextInput(
                    label=tr(lang, "Ativar? (sim/nao)", "Enable? (yes/no)", "Activar? (si/no)"),
                    placeholder=tr(lang, "sim", "yes", "si"),
                    required=True,
                    max_length=5,
                )
                self.quant_warnings = discord.ui.TextInput(
                    label=tr(lang, "Limite de avisos", "Warning limit", "Limite de advertencias"),
                    placeholder="3",
                    required=True,
                    max_length=2,
                )
                self.acao = discord.ui.TextInput(
                    label=tr(lang, "Acao", "Action", "Accion"),
                    placeholder="kick | ban | mute",
                    required=True,
                    max_length=4,
                )
                self.add_item(self.auto_moderation)
                self.add_item(self.quant_warnings)
                self.add_item(self.acao)

            async def on_submit(self, modal_interaction: discord.Interaction):
                raw_enabled = self.auto_moderation.value.lower().strip()
                enabled = raw_enabled in ["sim", "s", "yes", "y", "si"]

                try:
                    warning_count = int(self.quant_warnings.value)
                    if warning_count < 1:
                        raise ValueError
                except ValueError:
                    await modal_interaction.response.send_message(tr(lang, "Numero invalido. Tenta um valor maior que zero.", "Invalid number. Try a value greater than zero.", "Numero invalido. Intenta un valor mayor que cero."), ephemeral=True)
                    return

                action_value = self.acao.value.lower().strip()
                if action_value not in ["kick", "ban", "mute"]:
                    await modal_interaction.response.send_message(tr(lang, "Acao invalida. Use kick, ban ou mute, combinado?", "Invalid action. Please use kick, ban or mute.", "Accion invalida. Usa kick, ban o mute, vale?"), ephemeral=True)
                    return

                await db.execute(
                    """
                    INSERT INTO guilds (guild_id, auto_moderation, quant_warnings, acao)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (guild_id)
                    DO UPDATE SET auto_moderation = $2, quant_warnings = $3, acao = $4
                    """,
                    modal_interaction.guild.id,
                    enabled,
                    warning_count,
                    action_value,
                )

                await modal_interaction.response.send_message(
                    tr(lang, "AutoMod configurado com sucesso. Tudo certinho!", "AutoMod configured successfully. All set!", "AutoMod configurado correctamente. Todo listo!"),
                    ephemeral=True,
                )

        class FormLogChannel(discord.ui.Modal):
            def __init__(self):
                super().__init__(title=tr(lang, "Canal de Logs", "Log Channel", "Canal de Logs"))
                self.log_channel = discord.ui.TextInput(
                    label=tr(lang, "Nome do canal ou 'criar'", "Channel name or 'create'", "Nombre del canal o 'crear'"),
                    placeholder="logs",
                    required=True,
                    max_length=100,
                )
                self.add_item(self.log_channel)

            async def on_submit(self, modal_interaction: discord.Interaction):
                guild = modal_interaction.guild
                log_channel_name = self.log_channel.value.strip()
                if log_channel_name.lower() == "create":
                    log_channel = await guild.create_text_channel("logs")
                else:
                    channel_name = log_channel_name.replace("#", "").strip()
                    log_channel = discord.utils.get(guild.text_channels, name=channel_name)

                if log_channel is None:
                    await modal_interaction.response.send_message(tr(lang, "Nao achei esse canal. Confere o nome e tenta de novo.", "I could not find that channel. Check the name and try again.", "No encontre ese canal. Revisa el nombre e intenta de nuevo."), ephemeral=True)
                    return

                await db.execute(
                    """
                    INSERT INTO guilds (guild_id, log_channel_id)
                    VALUES ($1, $2)
                    ON CONFLICT (guild_id)
                    DO UPDATE SET log_channel_id = $2
                    """,
                    guild.id,
                    log_channel.id,
                )
                await modal_interaction.response.send_message(tr(lang, f"Prontinho! Canal de logs configurado: {log_channel.mention}", f"All set! Log channel configured: {log_channel.mention}", f"Listo! Canal de logs configurado: {log_channel.mention}"), ephemeral=True)

        class FormModmailCategory(discord.ui.Modal):
            def __init__(self):
                super().__init__(title=tr(lang, "Configurar ModMail", "Configure ModMail", "Configurar ModMail"))
                self.modmail_category = discord.ui.TextInput(
                    label=tr(lang, "Nome da categoria ou 'criar'", "Category name or 'create'", "Nombre de categoria o 'crear'"),
                    placeholder="ModMail",
                    required=True,
                    max_length=100,
                )
                self.add_item(self.modmail_category)

            async def on_submit(self, modal_interaction: discord.Interaction):
                guild = modal_interaction.guild
                category_name = self.modmail_category.value.strip()
                if category_name.lower() == "create":
                    category = await guild.create_category("ModMail")
                else:
                    category = discord.utils.get(guild.categories, name=category_name)

                if category is None:
                    await modal_interaction.response.send_message(tr(lang, "Nao achei essa categoria. Confere o nome e tenta de novo.", "I could not find that category. Check the name and try again.", "No encontre esa categoria. Revisa el nombre e intenta de nuevo."), ephemeral=True)
                    return

                await db.execute(
                    """
                    INSERT INTO guilds (guild_id, modmail_category_id)
                    VALUES ($1, $2)
                    ON CONFLICT (guild_id)
                    DO UPDATE SET modmail_category_id = $2
                    """,
                    guild.id,
                    category.id,
                )
                await modal_interaction.response.send_message(tr(lang, f"Perfeito! Categoria de ModMail configurada: {category.name}", f"Perfect! ModMail category configured: {category.name}", f"Perfecto! Categoria de ModMail configurada: {category.name}"), ephemeral=True)

        class FormSmartAntiFlood(discord.ui.Modal):
            def __init__(self):
                super().__init__(title=tr(lang, "Configurar Anti-Flood", "Configure Anti-Flood", "Configurar Anti-Flood"))
                self.smart_antiflood = discord.ui.TextInput(
                    label=tr(lang, "Ativar? (sim/nao)", "Enable? (yes/no)", "Activar? (si/no)"),
                    placeholder=tr(lang, "sim", "yes", "si"),
                    required=True,
                    max_length=5,
                )
                self.add_item(self.smart_antiflood)

            async def on_submit(self, modal_interaction: discord.Interaction):
                raw_enabled = self.smart_antiflood.value.lower().strip()
                enabled = raw_enabled in ["sim", "s", "yes", "y", "si"]
                await db.execute(
                    """
                    INSERT INTO guilds (guild_id, smart_antiflood)
                    VALUES ($1, $2)
                    ON CONFLICT (guild_id)
                    DO UPDATE SET smart_antiflood = $2
                    """,
                    modal_interaction.guild.id,
                    enabled,
                )
                await modal_interaction.response.send_message(
                    tr(lang, f"Anti-flood {'ativado' if enabled else 'desativado'} com sucesso.", f"Anti-flood {'enabled' if enabled else 'disabled'} successfully.", f"Anti-flood {'activado' if enabled else 'desactivado'} correctamente."),
                    ephemeral=True,
                )

        class FormTicketDefaults(discord.ui.Modal):
            def __init__(self):
                super().__init__(title=tr(lang, "Padrao de Tickets", "Ticket Defaults", "Valores por Defecto de Tickets"))
                self.category_input = discord.ui.TextInput(
                    label=tr(
                        lang,
                        "Categoria (nome, 'criar' ou 'nenhum')",
                        "Category (name, 'create' or 'none')",
                        "Categoria (nombre, 'crear' o 'ninguno')",
                    ),
                    placeholder=tr(lang, "tickets", "tickets", "tickets"),
                    required=True,
                    max_length=100,
                )
                self.support_role_input = discord.ui.TextInput(
                    label=tr(
                        lang,
                        "Cargo suporte (nome, ID ou 'nenhum')",
                        "Support role (name, ID or 'none')",
                        "Rol soporte (nombre, ID o 'ninguno')",
                    ),
                    placeholder=tr(lang, "Suporte", "Support", "Soporte"),
                    required=False,
                    max_length=100,
                )
                self.add_item(self.category_input)
                self.add_item(self.support_role_input)

            async def on_submit(self, modal_interaction: discord.Interaction):
                guild = modal_interaction.guild
                category_raw = self.category_input.value.strip()
                role_raw = self.support_role_input.value.strip()

                selected_category = None
                if category_raw.lower() in ["nenhum", "none", "ninguno", "limpar", "clear"]:
                    selected_category = None
                elif category_raw.lower() in ["criar", "create", "crear"]:
                    selected_category = await guild.create_category("tickets")
                else:
                    selected_category = discord.utils.get(guild.categories, name=category_raw)
                    if selected_category is None:
                        await modal_interaction.response.send_message(
                            tr(lang, "Nao encontrei essa categoria.", "I could not find that category.", "No encontre esa categoria."),
                            ephemeral=True,
                        )
                        return

                selected_role = None
                if role_raw:
                    if role_raw.lower() not in ["nenhum", "none", "ninguno", "limpar", "clear"]:
                        role_id_digits = "".join(ch for ch in role_raw if ch.isdigit())
                        if role_id_digits:
                            selected_role = guild.get_role(int(role_id_digits))
                        if selected_role is None:
                            selected_role = discord.utils.get(guild.roles, name=role_raw)
                        if selected_role is None:
                            await modal_interaction.response.send_message(
                                tr(lang, "Nao encontrei esse cargo de suporte.", "I could not find that support role.", "No encontre ese rol de soporte."),
                                ephemeral=True,
                            )
                            return

                await db.execute(
                    """
                    INSERT INTO guilds (guild_id, ticket_default_category_id, ticket_default_support_role_id)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (guild_id)
                    DO UPDATE SET
                        ticket_default_category_id = $2,
                        ticket_default_support_role_id = $3,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    guild.id,
                    selected_category.id if selected_category else None,
                    selected_role.id if selected_role else None,
                )
                await modal_interaction.response.send_message(
                    tr(lang, "Padroes de ticket atualizados. Tudo pronto!", "Ticket defaults updated. All set!", "Valores por defecto de ticket actualizados. Todo listo!"),
                    ephemeral=True,
                )

        class FormAISettings(discord.ui.Modal):
            def __init__(self):
                super().__init__(title=tr(lang, "Configurar IA", "Configure AI", "Configurar IA"))
                self.ai_enabled_input = discord.ui.TextInput(
                    label=tr(lang, "Ativar IA? (sim/nao)", "Enable AI? (yes/no)", "Activar IA? (si/no)"),
                    placeholder=tr(lang, "sim", "yes", "si"),
                    required=True,
                    max_length=5,
                )
                self.add_item(self.ai_enabled_input)

            async def on_submit(self, modal_interaction: discord.Interaction):
                enabled = self.ai_enabled_input.value.strip().lower() in ["sim", "s", "yes", "y", "si"]
                await db.execute(
                    """
                    INSERT INTO guilds (guild_id, ai_enabled)
                    VALUES ($1, $2)
                    ON CONFLICT (guild_id)
                    DO UPDATE SET ai_enabled = $2, updated_at = CURRENT_TIMESTAMP
                    """,
                    modal_interaction.guild.id,
                    enabled,
                )
                await modal_interaction.response.send_message(
                    tr(lang, f"IA {'ativada' if enabled else 'desativada'} com sucesso.", f"AI {'enabled' if enabled else 'disabled'} successfully.", f"IA {'activada' if enabled else 'desactivada'} correctamente."),
                    ephemeral=True,
                )

        class SetupSelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label=tr(lang, "Canal de Logs", "Log Channel", "Canal de Logs"), description=tr(lang, "Configurar logs", "Configure logs", "Configurar logs"), value="logs"),
                    discord.SelectOption(label="AutoMod", description=tr(lang, "Moderacao automatica", "Automatic moderation", "Moderacion automatica"), value="automod"),
                    discord.SelectOption(label="Anti-Flood", description=tr(lang, "Protecao contra spam", "Spam protection", "Proteccion anti spam"), value="antiflood"),
                    discord.SelectOption(label="ModMail", description=tr(lang, "Categoria de suporte", "Support category", "Categoria de soporte"), value="modmail"),
                    discord.SelectOption(label=tr(lang, "Padrao de Tickets", "Ticket Defaults", "Valores por Defecto de Tickets"), description=tr(lang, "Categoria e cargo padrao", "Default category and support role", "Categoria y rol de soporte por defecto"), value="ticket_defaults"),
                    discord.SelectOption(label="AI", description=tr(lang, "Ativar ou desativar IA", "Enable or disable AI", "Activar o desactivar IA"), value="ai"),
                ]
                super().__init__(placeholder=tr(lang, "Escolha uma configuracao", "Choose a setting", "Elige una configuracion"), options=options)

            async def callback(self, select_interaction: discord.Interaction):
                choice = self.values[0]
                if choice == "logs":
                    await select_interaction.response.send_modal(FormLogChannel())
                elif choice == "automod":
                    await select_interaction.response.send_modal(FormAutoModeration())
                elif choice == "antiflood":
                    await select_interaction.response.send_modal(FormSmartAntiFlood())
                elif choice == "modmail":
                    await select_interaction.response.send_modal(FormModmailCategory())
                elif choice == "ticket_defaults":
                    await select_interaction.response.send_modal(FormTicketDefaults())
                elif choice == "ai":
                    await select_interaction.response.send_modal(FormAISettings())

        class SetupView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)
                self.add_item(SetupSelect())
                status_button = discord.ui.Button(
                    label=tr(lang, "Ver Status", "View Status", "Ver Estado"),
                    style=discord.ButtonStyle.gray,
                    row=1,
                )
                close_button = discord.ui.Button(
                    label=tr(lang, "Fechar", "Close", "Cerrar"),
                    style=discord.ButtonStyle.red,
                    row=1,
                )
                status_button.callback = self.status
                close_button.callback = self.close
                self.add_item(status_button)
                self.add_item(close_button)

            async def status(self, button_interaction: discord.Interaction):
                await send_status_embed(button_interaction)

            async def close(self, button_interaction: discord.Interaction):
                self.stop()
                await button_interaction.response.edit_message(content=tr(lang, "Setup encerrado. Se precisar, e so me chamar de novo.", "Setup closed. If you need anything else, call me again.", "Setup cerrado. Si necesitas algo mas, llamame de nuevo."), embed=None, view=None)

        embed_main = discord.Embed(
            title=tr(lang, "Painel de setup da Luma", "Luma setup panel", "Panel de setup de Luma"),
            description=tr(lang, "Escolha um modulo para configurar e eu cuido do resto.", "Choose a module to configure and I will handle the rest.", "Elige un modulo para configurar y yo me encargo del resto."),
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed_main.add_field(name="Logs", value=tr(lang, "Defina o canal de logs do servidor.", "Set the server log channel.", "Define el canal de logs del servidor."), inline=False)
        embed_main.add_field(name="AutoMod", value=tr(lang, "Configure limite de avisos e acao automatica.", "Configure warning limit and automatic action.", "Configura limite de advertencias y accion automatica."), inline=False)
        embed_main.add_field(name="Anti-Flood", value=tr(lang, "Ative a protecao contra spam e excesso de mensagens.", "Enable spam and flood protection.", "Activa la proteccion contra spam y flood."), inline=False)
        embed_main.add_field(name="ModMail", value=tr(lang, "Configure a categoria de atendimento privado.", "Configure the private support category.", "Configura la categoria de soporte privado."), inline=False)
        embed_main.add_field(name=tr(lang, "Padrao de Tickets", "Ticket Defaults", "Valores por Defecto de Tickets"), value=tr(lang, "Defina categoria e cargo de suporte padrao para novos tickets.", "Set default category and support role for new tickets.", "Define categoria y rol de soporte por defecto para nuevos tickets."), inline=False)
        embed_main.add_field(name="AI", value=tr(lang, "Ative ou desative respostas da IA no servidor.", "Enable or disable AI replies in the server.", "Activa o desactiva respuestas de IA en el servidor."), inline=False)

        await interaction.response.send_message(embed=embed_main, view=SetupView(), ephemeral=True)

    @app_commands.command(name="language", description="Set bot language for this server")
    @app_commands.describe(idioma="Choose Portugues, English or Espanol")
    @app_commands.choices(
        idioma=[
            app_commands.Choice(name="Portugues", value="pt"),
            app_commands.Choice(name="English", value="en"),
            app_commands.Choice(name="Espanol", value="es"),
        ]
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def language(self, interaction: discord.Interaction, idioma: app_commands.Choice[str]):
        if interaction.guild is None:
            await interaction.response.send_message("Oops! This command can only be used in a server.", ephemeral=True)
            return

        selected_lang = await self.bot.i18n.set_guild_language(self.bot.pool, interaction.guild.id, idioma.value)
        names = {"pt": "Portugues", "en": "English", "es": "Espanol"}
        msg = {
            "pt": f"Prontinho! Idioma atualizado para **{names[selected_lang]}**.",
            "en": f"All set! Language updated to **{names[selected_lang]}**.",
            "es": f"Listo! Idioma actualizado a **{names[selected_lang]}**.",
        }
        await interaction.response.send_message(msg[selected_lang], ephemeral=True)

    @setup.error
    async def setup_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            message = "Only administrators can use this command."
        else:
            message = f"I had a setup error: {error}"

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @language.error
    async def language_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            message = "Only administrators can change the bot language."
        else:
            message = f"I could not change the language right now: {error}"

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot):
    print("[DEBUG] Carregando cog Setup...")
    await bot.add_cog(Setup(bot))
    print("[DEBUG] Cog Setup carregado com sucesso!")
