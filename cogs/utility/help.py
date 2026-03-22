import discord
from discord import app_commands
from discord.ext import commands


HELP_UI = {
    "pt": {
        "main_title": "Central de Ajuda da Luma",
        "main_desc": "Escolha uma categoria para ver comandos, exemplos e o fluxo mais rapido para usar cada modulo.",
        "usage_name": "Como usar",
        "usage_value": "1. Escolha uma categoria\n2. Veja os comandos principais\n3. Copie o exemplo e adapte ao seu servidor",
        "summary_name": "Cobertura",
        "summary_value": "Moderacao, IA, suporte, economia, levels e configuracao em um unico painel.",
        "commands_name": "Comandos principais",
        "example_name": "Exemplo rapido",
        "tip_name": "Dica da Luma",
        "tip_value": "Se um modulo estiver desligado no painel, alguns comandos podem responder dizendo que o recurso esta desativado para esse servidor.",
        "footer": "Luma • ajuda interativa",
        "placeholder": "Selecione uma categoria",
        "back_label": "Visao geral",
        "options": {
            "general": ("Geral", "Comandos rapidos do dia a dia"),
            "ai": ("IA", "Perguntas e respostas com a Luma"),
            "moderation": ("Moderacao", "Acoes de staff e protecao"),
            "support": ("Suporte", "Modmail, tickets e cargos"),
            "economy": ("Economia", "Saldo, loja e ranking"),
            "levels": ("Levels", "XP, rank e leaderboard"),
            "setup": ("Setup", "Configuracao e administracao"),
        },
    },
    "en": {
        "main_title": "Luma Help Center",
        "main_desc": "Pick a category to view commands, examples, and the fastest way to use each module.",
        "usage_name": "How to use",
        "usage_value": "1. Pick a category\n2. Check the main commands\n3. Copy the example and adapt it to your server",
        "summary_name": "Coverage",
        "summary_value": "Moderation, AI, support, economy, levels, and setup in one place.",
        "commands_name": "Main commands",
        "example_name": "Quick example",
        "tip_name": "Luma tip",
        "tip_value": "If a module is disabled in the dashboard, some commands may answer that the feature is turned off for this server.",
        "footer": "Luma • interactive help",
        "placeholder": "Select a category",
        "back_label": "Overview",
        "options": {
            "general": ("General", "Everyday utility commands"),
            "ai": ("AI", "Ask Luma questions"),
            "moderation": ("Moderation", "Staff actions and protection"),
            "support": ("Support", "Modmail, tickets, and roles"),
            "economy": ("Economy", "Balance, shop, and rankings"),
            "levels": ("Levels", "XP, rank, and leaderboard"),
            "setup": ("Setup", "Configuration and admin flow"),
        },
    },
    "es": {
        "main_title": "Centro de Ayuda de Luma",
        "main_desc": "Elige una categoria para ver comandos, ejemplos y la forma mas rapida de usar cada modulo.",
        "usage_name": "Como usar",
        "usage_value": "1. Elige una categoria\n2. Revisa los comandos principales\n3. Copia el ejemplo y adaptalo a tu servidor",
        "summary_name": "Cobertura",
        "summary_value": "Moderacion, IA, soporte, economia, niveles y configuracion en un solo panel.",
        "commands_name": "Comandos principales",
        "example_name": "Ejemplo rapido",
        "tip_name": "Consejo de Luma",
        "tip_value": "Si un modulo esta desactivado en el panel, algunos comandos pueden avisar que la funcion no esta habilitada para ese servidor.",
        "footer": "Luma • ayuda interactiva",
        "placeholder": "Selecciona una categoria",
        "back_label": "Vista general",
        "options": {
            "general": ("General", "Comandos utiles del dia a dia"),
            "ai": ("IA", "Preguntas y respuestas con Luma"),
            "moderation": ("Moderacion", "Acciones del staff y proteccion"),
            "support": ("Soporte", "Modmail, tickets y roles"),
            "economy": ("Economia", "Saldo, tienda y ranking"),
            "levels": ("Niveles", "XP, rango y clasificacion"),
            "setup": ("Setup", "Configuracion y administracion"),
        },
    },
}


HELP_CATEGORIES = {
    "pt": {
        "general": {
            "emoji": "✨",
            "title": "Comandos gerais",
            "description": "Comandos leves para consultar informacoes rapidas, noticias e utilidades basicas.",
            "commands": [
                ("/help", "abre este painel interativo"),
                ("/ping", "mostra a latencia atual do bot"),
                ("/about", "resume status e identidade da Luma"),
                ("/news", "consulta as ultimas noticias publicadas"),
                ("/dice", "rola dados no formato XdY"),
                ("/stats", "mostra estatisticas gerais do servidor"),
            ],
            "example": "/news 3",
        },
        "ai": {
            "emoji": "🧠",
            "title": "Assistente de IA",
            "description": "Use a Luma para responder perguntas, resumir contexto e sugerir texto para a staff.",
            "commands": [
                ("/ask", "faz uma pergunta direta para a Luma"),
            ],
            "example": "/ask escreva um anuncio claro e profissional para abrir as inscricoes do evento",
        },
        "moderation": {
            "emoji": "🛡️",
            "title": "Moderacao",
            "description": "Ferramentas centrais da staff para aplicar acoes e manter a comunidade segura.",
            "commands": [
                ("/mod ban", "bane um membro com motivo"),
                ("/mod unban", "remove um ban pelo ID do usuario"),
                ("/mod kick", "expulsa um membro"),
                ("/mod timeout", "aplica timeout com duracao"),
                ("/mod warn", "registra advertencia e aciona escalonamento"),
            ],
            "example": "/mod warn @usuario motivo: spam em canais errados",
        },
        "support": {
            "emoji": "📨",
            "title": "Suporte e cargos",
            "description": "Fluxos para atendimento, tickets e distribuicao controlada de cargos.",
            "commands": [
                ("/mail enviar", "abre contato com a equipe via modmail"),
                ("/mail responder", "responde o usuario no canal de modmail"),
                ("/mail fechar", "encerra o atendimento atual"),
                ("/ticket painel", "publica um painel para abrir tickets"),
                ("/ticket fechar", "fecha um ticket ativo"),
                ("/rolepanel criar", "cria painel de autoatribuicao de cargos"),
            ],
            "example": "/ticket painel #suporte titulo: Suporte Luma mensagem: Clique para abrir atendimento",
        },
        "economy": {
            "emoji": "💸",
            "title": "Economia",
            "description": "Saldo, recompensas, loja, inventario e ranking da temporada em um mesmo sistema.",
            "commands": [
                ("/balance", "consulta seu saldo de Lumicoins"),
                ("/daily", "resgata a recompensa diaria"),
                ("/shop", "lista itens disponiveis na loja"),
                ("/buy", "compra itens da loja"),
                ("/inventory", "mostra o inventario de itens"),
                ("/useitem", "consome um item do inventario"),
                ("/transfer", "envia Lumicoins para outro usuario"),
                ("/leaderboard", "abre o ranking de Lumicoins"),
                ("/season", "mostra a temporada atual"),
                ("/profile", "abre o perfil publico do usuario"),
            ],
            "example": "/daily",
        },
        "levels": {
            "emoji": "📈",
            "title": "Levels",
            "description": "Acompanhe XP, rank pessoal e a classificacao do servidor.",
            "commands": [
                ("/levels rank", "mostra seu nivel atual"),
                ("/levels leaderboard", "mostra o top XP do servidor"),
            ],
            "example": "/levels rank",
        },
        "setup": {
            "emoji": "⚙️",
            "title": "Setup e administracao",
            "description": "Configura idioma, embeds e partes operacionais usadas pela equipe.",
            "commands": [
                ("/setup", "abre a configuracao guiada do servidor"),
                ("/language", "altera o idioma da guild"),
                ("/admin embed", "monta um embed interativo"),
                ("/admin health", "checa recursos operacionais"),
                ("/admin sync", "sincroniza comandos"),
            ],
            "example": "/setup",
        },
    },
    "en": {
        "general": {
            "emoji": "✨",
            "title": "General commands",
            "description": "Light commands for quick info, news, and everyday utilities.",
            "commands": [
                ("/help", "opens this interactive panel"),
                ("/ping", "shows the current bot latency"),
                ("/about", "summarizes Luma status and identity"),
                ("/news", "checks the latest published news"),
                ("/dice", "rolls dice using XdY format"),
                ("/stats", "shows server-wide bot stats"),
            ],
            "example": "/news 3",
        },
        "ai": {
            "emoji": "🧠",
            "title": "AI assistant",
            "description": "Ask Luma questions, get summaries, and draft cleaner staff messages.",
            "commands": [
                ("/ask", "sends a direct question to Luma"),
            ],
            "example": "/ask write a professional announcement for event signups",
        },
        "moderation": {
            "emoji": "🛡️",
            "title": "Moderation",
            "description": "Core staff actions for safety, escalation, and member management.",
            "commands": [
                ("/mod ban", "bans a member with a reason"),
                ("/mod unban", "removes a ban by user ID"),
                ("/mod kick", "kicks a member"),
                ("/mod timeout", "applies a timed timeout"),
                ("/mod warn", "stores a warning and escalation data"),
            ],
            "example": "/mod warn @user reason: repeated spam",
        },
        "support": {
            "emoji": "📨",
            "title": "Support and roles",
            "description": "Flows for modmail, tickets, and controlled role self-assignment.",
            "commands": [
                ("/mail enviar", "starts modmail contact with staff"),
                ("/mail responder", "replies from the current modmail channel"),
                ("/mail fechar", "closes the current support flow"),
                ("/ticket painel", "publishes a ticket panel"),
                ("/ticket fechar", "closes an open ticket"),
                ("/rolepanel criar", "creates a self-role panel"),
            ],
            "example": "/ticket painel #support title: Luma Support message: Click to open a ticket",
        },
        "economy": {
            "emoji": "💸",
            "title": "Economy",
            "description": "Balance, rewards, shop, inventory, and seasonal ranking in one system.",
            "commands": [
                ("/balance", "checks your Lumicoins balance"),
                ("/daily", "claims the daily reward"),
                ("/shop", "lists available shop items"),
                ("/buy", "buys an item from the shop"),
                ("/inventory", "shows your item inventory"),
                ("/useitem", "uses an owned item"),
                ("/transfer", "sends Lumicoins to another user"),
                ("/leaderboard", "opens the Lumicoins ranking"),
                ("/season", "shows the current season"),
                ("/profile", "opens the user's public profile"),
            ],
            "example": "/daily",
        },
        "levels": {
            "emoji": "📈",
            "title": "Levels",
            "description": "Track XP, your personal rank, and the server leaderboard.",
            "commands": [
                ("/levels rank", "shows your current level"),
                ("/levels leaderboard", "shows the server XP ranking"),
            ],
            "example": "/levels rank",
        },
        "setup": {
            "emoji": "⚙️",
            "title": "Setup and admin",
            "description": "Configure language, embeds, and operational admin tools.",
            "commands": [
                ("/setup", "opens guided server setup"),
                ("/language", "changes the guild language"),
                ("/admin embed", "opens the interactive embed builder"),
                ("/admin health", "checks operational resources"),
                ("/admin sync", "syncs slash commands"),
            ],
            "example": "/setup",
        },
    },
    "es": {
        "general": {
            "emoji": "✨",
            "title": "Comandos generales",
            "description": "Comandos ligeros para informacion rapida, noticias y utilidades diarias.",
            "commands": [
                ("/help", "abre este panel interactivo"),
                ("/ping", "muestra la latencia actual del bot"),
                ("/about", "resume el estado e identidad de Luma"),
                ("/news", "consulta las ultimas noticias publicadas"),
                ("/dice", "lanza dados con formato XdY"),
                ("/stats", "muestra estadisticas del servidor"),
            ],
            "example": "/news 3",
        },
        "ai": {
            "emoji": "🧠",
            "title": "Asistente de IA",
            "description": "Usa a Luma para preguntas, resumenes y mensajes de staff mejor escritos.",
            "commands": [
                ("/ask", "envia una pregunta directa a Luma"),
            ],
            "example": "/ask escribe un anuncio profesional para abrir inscripciones",
        },
        "moderation": {
            "emoji": "🛡️",
            "title": "Moderacion",
            "description": "Acciones centrales del staff para seguridad, escalado y gestion de miembros.",
            "commands": [
                ("/mod ban", "banea a un miembro con motivo"),
                ("/mod unban", "quita un baneo por ID"),
                ("/mod kick", "expulsa a un miembro"),
                ("/mod timeout", "aplica timeout con duracion"),
                ("/mod warn", "registra advertencia y escalado"),
            ],
            "example": "/mod warn @usuario motivo: spam repetido",
        },
        "support": {
            "emoji": "📨",
            "title": "Soporte y roles",
            "description": "Flujos para modmail, tickets y autoasignacion controlada de roles.",
            "commands": [
                ("/mail enviar", "inicia contacto con el staff"),
                ("/mail responder", "responde desde el canal de modmail"),
                ("/mail fechar", "cierra el flujo de soporte actual"),
                ("/ticket painel", "publica un panel de tickets"),
                ("/ticket fechar", "cierra un ticket abierto"),
                ("/rolepanel criar", "crea un panel de roles"),
            ],
            "example": "/ticket painel #soporte titulo: Soporte Luma mensaje: Haz clic para abrir un ticket",
        },
        "economy": {
            "emoji": "💸",
            "title": "Economia",
            "description": "Saldo, recompensas, tienda, inventario y ranking de temporada en un solo sistema.",
            "commands": [
                ("/balance", "consulta tu saldo de Lumicoins"),
                ("/daily", "reclama la recompensa diaria"),
                ("/shop", "lista los items de la tienda"),
                ("/buy", "compra un item de la tienda"),
                ("/inventory", "muestra tu inventario"),
                ("/useitem", "usa un item del inventario"),
                ("/transfer", "envia Lumicoins a otro usuario"),
                ("/leaderboard", "abre el ranking de Lumicoins"),
                ("/season", "muestra la temporada actual"),
                ("/profile", "abre el perfil publico del usuario"),
            ],
            "example": "/daily",
        },
        "levels": {
            "emoji": "📈",
            "title": "Niveles",
            "description": "Sigue XP, rango personal y clasificacion del servidor.",
            "commands": [
                ("/levels rank", "muestra tu nivel actual"),
                ("/levels leaderboard", "muestra el top XP del servidor"),
            ],
            "example": "/levels rank",
        },
        "setup": {
            "emoji": "⚙️",
            "title": "Setup y administracion",
            "description": "Configura idioma, embeds y herramientas operativas de administracion.",
            "commands": [
                ("/setup", "abre la configuracion guiada"),
                ("/language", "cambia el idioma de la guild"),
                ("/admin embed", "abre el creador interactivo de embeds"),
                ("/admin health", "revisa recursos operativos"),
                ("/admin sync", "sincroniza comandos slash"),
            ],
            "example": "/setup",
        },
    },
}


def _help_color() -> discord.Color:
    return discord.Color.from_rgb(132, 177, 255)


class HelpCategorySelect(discord.ui.Select):
    def __init__(self, cog: "Help", lang: str):
        self.cog = cog
        self.lang = lang
        ui = HELP_UI[lang]
        options = []
        for key, category in HELP_CATEGORIES[lang].items():
            label, description = ui["options"][key]
            options.append(
                discord.SelectOption(
                    label=label,
                    description=description,
                    value=key,
                    emoji=category["emoji"],
                )
            )

        super().__init__(placeholder=ui["placeholder"], options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, HelpView):
            return
        await view.show_category(interaction, self.values[0])


class HelpView(discord.ui.View):
    def __init__(self, cog: "Help", interaction: discord.Interaction, lang: str):
        super().__init__(timeout=240)
        self.cog = cog
        self.source_interaction = interaction
        self.lang = lang
        self.current_key: str | None = None
        self.select = HelpCategorySelect(cog, lang)
        self.add_item(self.select)
        self.back_button.label = HELP_UI[lang]["back_label"]
        self.back_button.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.source_interaction.user.id:
            await interaction.response.send_message("Esse painel de ajuda pertence a outra pessoa.", ephemeral=True)
            return False
        return True

    async def show_home(self, interaction: discord.Interaction):
        self.current_key = None
        self.back_button.disabled = True
        await interaction.response.edit_message(embed=self.cog.build_home_embed(self.lang, interaction), view=self)

    async def show_category(self, interaction: discord.Interaction, key: str):
        self.current_key = key
        self.back_button.disabled = False
        await interaction.response.edit_message(embed=self.cog.build_category_embed(self.lang, key, interaction), view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="Overview", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_home(interaction)


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def build_home_embed(self, lang: str, interaction: discord.Interaction) -> discord.Embed:
        ui = HELP_UI[lang]
        embed = discord.Embed(
            title=ui["main_title"],
            description=ui["main_desc"],
            color=_help_color(),
        )
        embed.add_field(name=ui["usage_name"], value=ui["usage_value"], inline=False)
        embed.add_field(name=ui["summary_name"], value=ui["summary_value"], inline=False)

        for key, category in HELP_CATEGORIES[lang].items():
            label = ui["options"][key][0]
            embed.add_field(
                name=f"{category['emoji']} {label}",
                value=category["description"],
                inline=False,
            )

        bot_user = getattr(interaction.client, "user", None)
        if bot_user is not None:
            embed.set_thumbnail(url=bot_user.display_avatar.url)
        embed.set_footer(text=ui["footer"])
        return embed

    def build_category_embed(self, lang: str, key: str, interaction: discord.Interaction) -> discord.Embed:
        ui = HELP_UI[lang]
        category = HELP_CATEGORIES[lang][key]
        embed = discord.Embed(
            title=f"{category['emoji']} {category['title']}",
            description=category["description"],
            color=_help_color(),
        )
        embed.add_field(
            name=ui["commands_name"],
            value="\n".join(f"`{name}` - {description}" for name, description in category["commands"]),
            inline=False,
        )
        embed.add_field(name=ui["example_name"], value=f"`{category['example']}`", inline=False)
        embed.add_field(name=ui["tip_name"], value=ui["tip_value"], inline=False)

        bot_user = getattr(interaction.client, "user", None)
        if bot_user is not None:
            embed.set_thumbnail(url=bot_user.display_avatar.url)
        embed.set_footer(text=ui["footer"])
        return embed

    @app_commands.command(name="help", description="Mostra um painel interativo com categorias e exemplos de comandos")
    async def help(self, interaction: discord.Interaction):
        lang = await self.bot.i18n.language_for_interaction(self.bot, interaction)
        view = HelpView(self, interaction, lang)
        await interaction.response.send_message(
            embed=self.build_home_embed(lang, interaction),
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))