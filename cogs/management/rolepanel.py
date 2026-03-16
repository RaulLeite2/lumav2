import discord
from discord import app_commands
from discord.ext import commands

from modules.admin.services import AuditLogger
from modules.moderation.services import StatsService


def tr(lang: str, pt: str, en: str, es: str) -> str:
    return {"pt": pt, "en": en, "es": es}.get(lang, pt)


class RolePanelSelect(discord.ui.Select):
    def __init__(self, panel_id: int, options: list[discord.SelectOption], role_ids: list[int], placeholder: str):
        super().__init__(
            placeholder=placeholder,
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id=f"rolepanel:{panel_id}:select",
        )
        self.panel_id = panel_id
        self.role_ids = role_ids

    async def callback(self, interaction: discord.Interaction):
        lang = await interaction.client.i18n.language_for_interaction(interaction.client, interaction)
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(tr(lang, "Este painel so funciona em servidor.", "This panel only works in a server.", "Este panel solo funciona en un servidor."), ephemeral=True)
            return

        selected_role_ids = {int(value) for value in self.values}
        panel_role_ids = set(self.role_ids)

        to_add = []
        to_remove = []
        for role_id in panel_role_ids:
            role = interaction.guild.get_role(role_id)
            if role is None:
                continue
            if role_id in selected_role_ids and role not in interaction.user.roles:
                to_add.append(role)
            if role_id not in selected_role_ids and role in interaction.user.roles:
                to_remove.append(role)

        if to_add:
            await interaction.user.add_roles(*to_add, reason="Role panel selection")
        if to_remove:
            await interaction.user.remove_roles(*to_remove, reason="Role panel selection")

        if interaction.guild is not None and (to_add or to_remove):
            async with interaction.client.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO metric_counters (guild_id, metric_name, metric_value)
                    VALUES ($1, 'rolepanel_assignments', 1)
                    ON CONFLICT (guild_id, metric_name)
                    DO UPDATE SET metric_value = metric_counters.metric_value + 1, updated_at = CURRENT_TIMESTAMP
                    """,
                    interaction.guild.id,
                )

        added_names = ", ".join(role.name for role in to_add) if to_add else tr(lang, "nenhum", "none", "ninguno")
        removed_names = ", ".join(role.name for role in to_remove) if to_remove else tr(lang, "nenhum", "none", "ninguno")

        await interaction.response.send_message(
            tr(lang, f"Pronto! Adicionados: {added_names}. Removidos: {removed_names}.", f"Done! Added: {added_names}. Removed: {removed_names}.", f"Listo! Anadidos: {added_names}. Quitados: {removed_names}."),
            ephemeral=True,
        )


class RolePanelView(discord.ui.View):
    def __init__(self, panel_id: int, options: list[discord.SelectOption], role_ids: list[int], placeholder: str):
        super().__init__(timeout=None)
        self.add_item(RolePanelSelect(panel_id=panel_id, options=options, role_ids=role_ids, placeholder=placeholder))


class RolePanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.stats_service = StatsService(bot.pool)
        self.audit_logger = AuditLogger(bot.pool)

    rolepanel = app_commands.Group(name="rolepanel", description="Role panel commands")

    async def _lang(self, interaction: discord.Interaction) -> str:
        return await self.bot.i18n.language_for_interaction(self.bot, interaction)

    async def _build_panel_view(self, panel_id: int, guild_id: int) -> RolePanelView | None:
        lang = await self.bot.i18n.get_guild_language(self.bot.pool, guild_id)
        async with self.bot.pool.acquire() as conn:
            options_rows = await conn.fetch(
                """
                SELECT role_id, label, description, emoji
                FROM role_panel_options
                WHERE panel_id = $1
                ORDER BY position ASC, id ASC
                """,
                panel_id,
            )

        if not options_rows:
            return None

        select_options: list[discord.SelectOption] = []
        role_ids: list[int] = []
        for row in options_rows:
            role_ids.append(row["role_id"])
            select_options.append(
                discord.SelectOption(
                    label=row["label"][:100],
                    description=(row["description"] or "")[:100] or None,
                    value=str(row["role_id"]),
                    emoji=row["emoji"] or None,
                )
            )

        placeholder = tr(
            lang,
            "Selecione os cargos que voce quer receber",
            "Select the roles you want",
            "Selecciona los roles que quieres recibir",
        )
        return RolePanelView(panel_id=panel_id, options=select_options, role_ids=role_ids, placeholder=placeholder)

    @commands.Cog.listener()
    async def on_ready(self):
        async with self.bot.pool.acquire() as conn:
            panels = await conn.fetch(
                """
                SELECT id, guild_id, message_id
                FROM role_panels
                WHERE is_active = TRUE
                  AND message_id IS NOT NULL
                """
            )

        for panel in panels:
            view = await self._build_panel_view(panel["id"], panel["guild_id"])
            if view is None:
                continue
            self.bot.add_view(view, message_id=panel["message_id"])

    @rolepanel.command(name="criar", description="Create role selection panel")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def criar(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
        titulo: str,
        mensagem: str,
        cargo_1: discord.Role,
        cargo_2: discord.Role | None = None,
        cargo_3: discord.Role | None = None,
        cargo_4: discord.Role | None = None,
        cargo_5: discord.Role | None = None,
    ):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await interaction.response.send_message(tr(lang, "Use esse comando em servidor.", "Use this command in a server.", "Usa este comando en un servidor."), ephemeral=True)
            return

        bot_member = interaction.guild.get_member(self.bot.user.id) if self.bot.user else None
        if bot_member is None or not bot_member.guild_permissions.manage_roles:
            await interaction.response.send_message(tr(lang, "Eu preciso da permissao Gerenciar Cargos.", "I need Manage Roles permission.", "Necesito permiso de Gestionar Roles."), ephemeral=True)
            return

        role_list = [r for r in [cargo_1, cargo_2, cargo_3, cargo_4, cargo_5] if r is not None]
        unique_roles = []
        seen = set()
        for role in role_list:
            if role.id in seen:
                continue
            seen.add(role.id)
            unique_roles.append(role)

        for role in unique_roles:
            if role >= bot_member.top_role:
                await interaction.response.send_message(
                    tr(lang, f"Nao posso gerenciar o cargo {role.mention} porque ele esta acima do meu.", f"I cannot manage role {role.mention} because it is above mine.", f"No puedo gestionar el rol {role.mention} porque esta por encima del mio."),
                    ephemeral=True,
                )
                return

        await interaction.response.defer(ephemeral=True, thinking=True)

        async with self.bot.pool.acquire() as conn:
            panel_row = await conn.fetchrow(
                """
                INSERT INTO role_panels (guild_id, channel_id, title, description, created_by)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                interaction.guild.id,
                canal.id,
                titulo,
                mensagem,
                interaction.user.id,
            )
            panel_id = panel_row["id"]

            for idx, role in enumerate(unique_roles):
                await conn.execute(
                    """
                    INSERT INTO role_panel_options (panel_id, role_id, label, description, emoji, position)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    panel_id,
                    role.id,
                    role.name[:100],
                    f"Role {role.name}"[:100],
                    None,
                    idx,
                )

        view = await self._build_panel_view(panel_id, interaction.guild.id)
        if view is None:
            await interaction.followup.send(tr(lang, "Falha ao criar painel: nenhuma opcao valida.", "Failed to create panel: no valid options.", "No se pudo crear el panel: sin opciones validas."), ephemeral=True)
            return

        embed = discord.Embed(title=titulo[:256], description=mensagem[:4096], color=discord.Color.blurple(), timestamp=discord.utils.utcnow())
        embed.set_footer(text=f"Panel #{panel_id}")

        panel_message = await canal.send(embed=embed, view=view)
        self.bot.add_view(view, message_id=panel_message.id)

        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE role_panels
                SET message_id = $1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
                """,
                panel_message.id,
                panel_id,
            )

        await self.stats_service.increment_metric(interaction.guild.id, "rolepanel_created")
        await self.audit_logger.log(
            guild=interaction.guild,
            action_name="rolepanel:create",
            executor=interaction.user,
            reason="Role panel creation",
            metadata={"panel_id": panel_id, "channel_id": canal.id},
        )

        await interaction.followup.send(
            tr(lang, f"Painel criado em {canal.mention}. ID: {panel_id}.", f"Panel created in {canal.mention}. ID: {panel_id}.", f"Panel creado en {canal.mention}. ID: {panel_id}."),
            ephemeral=True,
        )

    @rolepanel.command(name="remover", description="Disable and remove a role panel")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def remover(self, interaction: discord.Interaction, painel_id: int):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await interaction.response.send_message(tr(lang, "Use esse comando em servidor.", "Use this command in a server.", "Usa este comando en un servidor."), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        async with self.bot.pool.acquire() as conn:
            panel = await conn.fetchrow(
                """
                SELECT id, channel_id, message_id
                FROM role_panels
                WHERE id = $1 AND guild_id = $2 AND is_active = TRUE
                """,
                painel_id,
                interaction.guild.id,
            )

            if not panel:
                await interaction.followup.send(tr(lang, "Painel nao encontrado ou ja removido.", "Panel not found or already removed.", "Panel no encontrado o ya eliminado."), ephemeral=True)
                return

            await conn.execute(
                """
                UPDATE role_panels
                SET is_active = FALSE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                painel_id,
            )

        channel = interaction.guild.get_channel(panel["channel_id"])
        if isinstance(channel, discord.TextChannel) and panel["message_id"]:
            try:
                msg = await channel.fetch_message(panel["message_id"])
                await msg.edit(view=None)
            except discord.HTTPException:
                pass

        await self.audit_logger.log(
            guild=interaction.guild,
            action_name="rolepanel:remove",
            executor=interaction.user,
            reason="Role panel removal",
            metadata={"panel_id": painel_id},
        )

        await interaction.followup.send(tr(lang, f"Painel {painel_id} desativado.", f"Panel {painel_id} disabled.", f"Panel {painel_id} desactivado."), ephemeral=True)

    @rolepanel.command(name="listar", description="List active role panels")
    async def listar(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        if interaction.guild is None:
            await interaction.response.send_message(tr(lang, "Use esse comando em servidor.", "Use this command in a server.", "Usa este comando en un servidor."), ephemeral=True)
            return

        async with self.bot.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, channel_id, title, message_id
                FROM role_panels
                WHERE guild_id = $1 AND is_active = TRUE
                ORDER BY id DESC
                LIMIT 20
                """,
                interaction.guild.id,
            )

        if not rows:
            await interaction.response.send_message(tr(lang, "Nenhum painel ativo encontrado.", "No active panels found.", "No se encontraron paneles activos."), ephemeral=True)
            return

        lines = [f"• ID {row['id']} | <#{row['channel_id']}> | `{row['message_id']}` | {row['title']}" for row in rows]
        embed = discord.Embed(
            title=tr(lang, "Paineis de cargos ativos", "Active role panels", "Paneles de roles activos"),
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    print("[DEBUG] Carregando cog RolePanel...")
    await bot.add_cog(RolePanel(bot))
    print("[DEBUG] Cog RolePanel carregado com sucesso!")
