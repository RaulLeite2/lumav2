import discord
from discord import app_commands
from discord.ext import commands


HELP_UI = {
    "pt": {
        "main_title": "Cantinho de Ajuda da Luma ✨",
        "main_desc": "Escolha uma categoria e eu te mostro os comandos principais, bem direitinho.",
        "usage_name": "Como usar",
        "usage_value": "1. Escolha uma categoria\n2. Veja os comandos\n3. Teste no seu servidor",
        "footer": "Luma • fofinha e pronta para ajudar",
        "placeholder": "Selecione uma categoria com carinho",
        "options": [
            ("geral", "Geral", "Comandos basicos"),
            ("admin", "Administracao", "Comandos administrativos"),
            ("mail", "Mail", "Mensagens privadas"),
            ("mod", "Moderacao", "Controle de membros"),
            ("setup", "Setup", "Configuracao do servidor"),
        ],
        "cards": {
            "geral": ("Comandos Gerais", "Use estes comandos para conversar comigo e explorar a Luma."),
            "admin": ("Comandos de Administracao", "Ferramentas para manter tudo organizado com tranquilidade."),
            "mail": ("Comandos de Mail", "Canal de mensagens privadas com a equipe."),
            "mod": ("Comandos de Moderacao", "Acoes para proteger a comunidade com equilibrio."),
            "setup": ("Comandos de Setup", "Configuracoes principais para deixar o servidor do seu jeitinho."),
        },
    },
    "en": {
        "main_title": "Luma Help Corner ✨",
        "main_desc": "Pick a category and I will show the main commands in a neat way.",
        "usage_name": "How to use",
        "usage_value": "1. Pick a category\n2. Check the commands\n3. Try them in your server",
        "footer": "Luma • gentle and ready to help",
        "placeholder": "Pick a category",
        "options": [
            ("general", "General", "Basic commands"),
            ("admin", "Administration", "Administrative commands"),
            ("mail", "Mail", "Private messaging"),
            ("mod", "Moderation", "Member management"),
            ("setup", "Setup", "Server configuration"),
        ],
        "cards": {
            "general": ("General Commands", "Use these commands to chat with me and explore Luma."),
            "admin": ("Administration Commands", "Tools to keep everything organized and smooth."),
            "mail": ("Mail Commands", "Private messaging flow with your staff team."),
            "mod": ("Moderation Commands", "Safety and order controls for your community."),
            "setup": ("Setup Commands", "Main settings to shape the server your way."),
        },
    },
    "es": {
        "main_title": "Rinconcito de Ayuda de Luma ✨",
        "main_desc": "Elige una categoria y te muestro los comandos principales, bien ordenados.",
        "usage_name": "Como usar",
        "usage_value": "1. Elige una categoria\n2. Revisa los comandos\n3. Usalos en tu servidor",
        "footer": "Luma • tierna y lista para ayudarte",
        "placeholder": "Selecciona una categoria",
        "options": [
            ("general", "General", "Comandos basicos"),
            ("admin", "Administracion", "Comandos administrativos"),
            ("mail", "Mail", "Mensajeria privada"),
            ("mod", "Moderacion", "Gestion de miembros"),
            ("setup", "Setup", "Configuracion del servidor"),
        ],
        "cards": {
            "general": ("Comandos Generales", "Usa estos comandos para hablar conmigo y explorar Luma."),
            "admin": ("Comandos de Administracion", "Herramientas para mantener todo ordenado."),
            "mail": ("Comandos de Mail", "Flujo de mensajes privados con el equipo."),
            "mod": ("Comandos de Moderacion", "Controles de seguridad y orden para la comunidad."),
            "setup": ("Comandos de Setup", "Ajustes principales para personalizar tu servidor."),
        },
    },
}


COMMAND_BLOCKS = {
    "pt": {
        "geral": ["/help", "/ask", "/criador", "/stats"],
        "admin": ["/admin sync", "/admin health", "/admin lockdown", "/admin unlock", "/admin slowmode", "/admin embed"],
        "mail": ["/mail enviar", "/mail responder", "/mail fechar"],
        "mod": ["/mod ban", "/mod unban", "/mod kick", "/mod timeout", "/mod warn"],
        "setup": ["/setup", "/language"],
    },
    "en": {
        "general": ["/help", "/ask", "/criador", "/stats"],
        "admin": ["/admin sync", "/admin health", "/admin lockdown", "/admin unlock", "/admin slowmode", "/admin embed"],
        "mail": ["/mail send", "/mail reply", "/mail close"],
        "mod": ["/mod ban", "/mod unban", "/mod kick", "/mod timeout", "/mod warn"],
        "setup": ["/setup", "/language"],
    },
    "es": {
        "general": ["/help", "/ask", "/criador", "/stats"],
        "admin": ["/admin sync", "/admin health", "/admin lockdown", "/admin unlock", "/admin slowmode", "/admin embed"],
        "mail": ["/mail enviar", "/mail responder", "/mail cerrar"],
        "mod": ["/mod ban", "/mod unban", "/mod kick", "/mod timeout", "/mod warn"],
        "setup": ["/setup", "/language"],
    },
}


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show the help menu and command categories")
    async def help(self, interaction: discord.Interaction):
        lang = await self.bot.i18n.language_for_interaction(self.bot, interaction)
        ui = HELP_UI[lang]

        class HelpSelection(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label=label, description=description, value=value)
                    for value, label, description in ui["options"]
                ]
                super().__init__(placeholder=ui["placeholder"], options=options)

            async def callback(self, select_interaction: discord.Interaction):
                key = self.values[0]
                title, description = ui["cards"][key]
                embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
                embed.add_field(name="Commands", value="\n".join(COMMAND_BLOCKS[lang][key]), inline=False)
                embed.set_footer(text=ui["footer"])
                await select_interaction.response.send_message(embed=embed, ephemeral=True)

        class HelpView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=180)
                self.add_item(HelpSelection())

        main_embed = discord.Embed(
            title=ui["main_title"],
            description=ui["main_desc"],
            color=discord.Color.blurple(),
        )
        main_embed.add_field(name=ui["usage_name"], value=ui["usage_value"], inline=False)
        main_embed.set_footer(text=ui["footer"])

        await interaction.response.send_message(embed=main_embed, view=HelpView(), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Help(bot))