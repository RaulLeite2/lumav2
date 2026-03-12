import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from modules.admin.services import AuditLogger
from modules.moderation.services import StatsService
from modules.tickets.config import TICKET_CHANNEL_PREFIX


def tr(lang: str, pt: str, en: str, es: str) -> str:
    return {"pt": pt, "en": en, "es": es}.get(lang, pt)


class TicketOpenView(discord.ui.View):
    def __init__(self, panel_id: int, lang: str):
        super().__init__(timeout=None)
        self.panel_id = panel_id
        open_label = tr(lang, "Abrir Ticket", "Open Ticket", "Abrir Ticket")
        button = discord.ui.Button(
            label=open_label,
            style=discord.ButtonStyle.green,
            emoji="🎫",
            custom_id=f"ticket:open:{panel_id}",
        )
        button.callback = self.open_ticket
        self.add_item(button)

    async def open_ticket(self, interaction: discord.Interaction):
        bot = interaction.client
        lang = await bot.i18n.language_for_interaction(bot, interaction)

        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(tr(lang, "Esse botao funciona apenas em servidor, ta bom?", "This button only works inside a server, alright?", "Este boton solo funciona dentro de un servidor, vale?"), ephemeral=True)
            return

        pool = getattr(interaction.client, "pool", None)
        if pool is None:
            await interaction.response.send_message(tr(lang, "O banco esta indisponivel agora. Tenta de novo em instantes.", "Database is unavailable right now. Please try again shortly.", "La base de datos no esta disponible ahora. Intenta de nuevo en un momento."), ephemeral=True)
            return

        async with pool.acquire() as conn:
            panel = await conn.fetchrow(
                """
                SELECT id, category_id, support_role_id
                FROM ticket_panels
                WHERE id = $1 AND guild_id = $2 AND is_active = TRUE
                """,
                self.panel_id,
                interaction.guild.id,
            )
            if not panel:
                await interaction.response.send_message(tr(lang, "Esse painel de ticket nao esta ativo agora.", "This ticket panel is not active right now.", "Este panel de tickets no esta activo ahora."), ephemeral=True)
                return

            existing = await conn.fetchrow(
                """
                SELECT channel_id
                FROM ticket_threads
                WHERE panel_id = $1
                  AND guild_id = $2
                  AND user_id = $3
                  AND status = 'open'
                """,
                self.panel_id,
                interaction.guild.id,
                interaction.user.id,
            )
            if existing:
                await interaction.response.send_message(
                    tr(lang, f"Voce ja tem um ticket aberto por aqui: <#{existing['channel_id']}>.", f"You already have an open ticket here: <#{existing['channel_id']}>.", f"Ya tienes un ticket abierto aqui: <#{existing['channel_id']}>."),
                    ephemeral=True,
                )
                return

        category = interaction.guild.get_channel(panel["category_id"]) if panel["category_id"] else None
        support_role = interaction.guild.get_role(panel["support_role_id"]) if panel["support_role_id"] else None

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }

        me = interaction.guild.get_member(interaction.client.user.id) if interaction.client.user else None
        if me:
            overwrites[me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, manage_messages=True, read_message_history=True)

        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)

        channel_name = f"{TICKET_CHANNEL_PREFIX}-{interaction.user.name.lower().replace(' ', '-')}-{interaction.user.id}"[:95]
        channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=category if isinstance(category, discord.CategoryChannel) else None,
            overwrites=overwrites,
            reason=f"Ticket opened by {interaction.user}",
        )

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO ticket_threads (panel_id, guild_id, channel_id, user_id, status)
                VALUES ($1, $2, $3, $4, 'open')
                """,
                self.panel_id,
                interaction.guild.id,
                channel.id,
                interaction.user.id,
            )
            await conn.execute(
                """
                INSERT INTO metric_counters (guild_id, metric_name, metric_value)
                VALUES ($1, 'tickets_opened', 1)
                ON CONFLICT (guild_id, metric_name)
                DO UPDATE SET metric_value = metric_counters.metric_value + 1, updated_at = CURRENT_TIMESTAMP
                """,
                interaction.guild.id,
            )

        welcome = discord.Embed(
            title=tr(lang, "Ticket Aberto", "Ticket Opened", "Ticket Abierto"),
            description=tr(
                lang,
                f"Ola {interaction.user.mention}! Conta pra gente o que aconteceu e vamos te ajudar.\nQuando terminar, use `/ticket fechar`.",
                f"Hi {interaction.user.mention}! Tell us what happened and we will help you out.\nWhen done, use `/ticket fechar`.",
                f"Hola {interaction.user.mention}! Cuentanos que paso y te ayudamos.\nCuando termines, usa `/ticket fechar`.",
            ),
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        await channel.send(embed=welcome)
        await interaction.response.send_message(
            tr(lang, f"Prontinho! Ticket criado em {channel.mention}", f"All set! Ticket created in {channel.mention}", f"Listo! Ticket creado en {channel.mention}"),
            ephemeral=True,
        )


class Ticket(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.stats_service = StatsService(bot.pool)
        self.audit_logger = AuditLogger(bot.pool)

    ticket = app_commands.Group(name="ticket", description="Ticket system")

    async def _lang(self, interaction: discord.Interaction) -> str:
        return await self.bot.i18n.language_for_interaction(self.bot, interaction)

    @commands.Cog.listener()
    async def on_ready(self):
        async with self.bot.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, guild_id, message_id
                FROM ticket_panels
                WHERE is_active = TRUE
                  AND message_id IS NOT NULL
                """
            )

        for row in rows:
            lang = await self.bot.i18n.get_guild_language(self.bot.pool, row["guild_id"])
            self.bot.add_view(TicketOpenView(panel_id=row["id"], lang=lang), message_id=row["message_id"])

    @ticket.command(name="painel", description="Create ticket panel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def painel(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
        titulo: str,
        mensagem: str,
        categoria: discord.CategoryChannel | None = None,
        cargo_suporte: discord.Role | None = None,
    ):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await interaction.response.send_message(tr(lang, "Use esse comando dentro de um servidor, por favor.", "Please use this command inside a server.", "Por favor usa este comando dentro de un servidor."), ephemeral=True)
            return

        selected_category = categoria
        selected_support_role = cargo_suporte
        if selected_category is None or selected_support_role is None:
            async with self.bot.pool.acquire() as conn:
                defaults_row = await conn.fetchrow(
                    """
                    SELECT ticket_default_category_id, ticket_default_support_role_id
                    FROM guilds
                    WHERE guild_id = $1
                    """,
                    interaction.guild.id,
                )

            if defaults_row:
                if selected_category is None and defaults_row["ticket_default_category_id"]:
                    found_category = interaction.guild.get_channel(defaults_row["ticket_default_category_id"])
                    if isinstance(found_category, discord.CategoryChannel):
                        selected_category = found_category

                if selected_support_role is None and defaults_row["ticket_default_support_role_id"]:
                    found_role = interaction.guild.get_role(defaults_row["ticket_default_support_role_id"])
                    if isinstance(found_role, discord.Role):
                        selected_support_role = found_role

        await interaction.response.defer(ephemeral=True, thinking=True)

        async with self.bot.pool.acquire() as conn:
            panel_row = await conn.fetchrow(
                """
                INSERT INTO ticket_panels (guild_id, channel_id, category_id, support_role_id, title, description, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                interaction.guild.id,
                canal.id,
                selected_category.id if selected_category else None,
                selected_support_role.id if selected_support_role else None,
                titulo,
                mensagem,
                interaction.user.id,
            )
            panel_id = panel_row["id"]

        view = TicketOpenView(panel_id=panel_id, lang=lang)
        embed = discord.Embed(title=titulo[:256], description=mensagem[:4096], color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.set_footer(
            text=tr(
                lang,
                f"Painel de ticket #{panel_id}",
                f"Ticket panel #{panel_id}",
                f"Panel de ticket #{panel_id}",
            )
        )

        msg = await canal.send(embed=embed, view=view)
        self.bot.add_view(view, message_id=msg.id)

        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ticket_panels
                SET message_id = $1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
                """,
                msg.id,
                panel_id,
            )

        await self.audit_logger.log(
            guild=interaction.guild,
            action_name="ticket:panel-create",
            executor=interaction.user,
            reason="Ticket panel creation",
            metadata={
                "panel_id": panel_id,
                "channel_id": canal.id,
                "category_id": selected_category.id if selected_category else None,
                "support_role_id": selected_support_role.id if selected_support_role else None,
            },
        )

        await interaction.followup.send(
            tr(lang, f"Painel criado com ID {panel_id} em {canal.mention}. Tudo pronto!", f"Panel created with ID {panel_id} in {canal.mention}. All set!", f"Panel creado con ID {panel_id} en {canal.mention}. Todo listo!"),
            ephemeral=True,
        )

    @ticket.command(name="fechar", description="Close current ticket")
    async def fechar(self, interaction: discord.Interaction, motivo: str | None = None):
        lang = await self._lang(interaction)
        if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(tr(lang, "Use este comando dentro de um ticket do servidor.", "Use this command inside a server ticket.", "Usa este comando dentro de un ticket del servidor."), ephemeral=True)
            return

        async with self.bot.pool.acquire() as conn:
            thread = await conn.fetchrow(
                """
                SELECT id, user_id, status
                FROM ticket_threads
                WHERE guild_id = $1
                  AND channel_id = $2
                """,
                interaction.guild.id,
                interaction.channel.id,
            )

        if not thread or thread["status"] != "open":
            await interaction.response.send_message(tr(lang, "Este canal nao parece um ticket aberto no momento.", "This channel does not look like an open ticket right now.", "Este canal no parece un ticket abierto en este momento."), ephemeral=True)
            return

        can_close = interaction.user.guild_permissions.manage_channels or interaction.user.id == thread["user_id"]
        if not can_close:
            await interaction.response.send_message(tr(lang, "Voce nao tem permissao para fechar este ticket.", "You do not have permission to close this ticket.", "No tienes permiso para cerrar este ticket."), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        target_user = interaction.guild.get_member(thread["user_id"])

        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ticket_threads
                SET status = 'closed',
                    closed_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                thread["id"],
            )

        await self.audit_logger.log(
            guild=interaction.guild,
            action_name="ticket:close",
            executor=interaction.user,
            target=target_user,
            reason=motivo,
            metadata={"channel_id": interaction.channel.id},
        )

        await interaction.followup.send(tr(lang, "Ticket fechado. Vou remover este canal em 5 segundos.", "Ticket closed. I will remove this channel in 5 seconds.", "Ticket cerrado. Voy a eliminar este canal en 5 segundos."), ephemeral=True)

        await interaction.channel.send(
            embed=discord.Embed(
                title=tr(lang, "Ticket Fechado", "Ticket Closed", "Ticket Cerrado"),
                description=tr(
                    lang,
                    f"Fechado por {interaction.user.mention}\nMotivo: {motivo or 'Nao informado'}",
                    f"Closed by {interaction.user.mention}\nReason: {motivo or 'Not provided'}",
                    f"Cerrado por {interaction.user.mention}\nMotivo: {motivo or 'No informado'}",
                ),
                color=discord.Color.red(),
            )
        )
        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")


async def setup(bot: commands.Bot):
    print("[DEBUG] Carregando cog Ticket...")
    await bot.add_cog(Ticket(bot))
    print("[DEBUG] Cog Ticket carregado com sucesso!")
