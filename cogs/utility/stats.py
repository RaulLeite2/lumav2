import discord
from discord import app_commands
from discord.ext import commands

from modules.admin.services import AuditLogger
from modules.moderation.services import StatsService


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.stats_service = StatsService(bot.pool)
        self.audit_logger = AuditLogger(bot.pool)

    @staticmethod
    def _extract_target_and_reason(interaction: discord.Interaction) -> tuple[discord.abc.User | None, str | None]:
        target = None
        reason = None

        namespace = getattr(interaction, "namespace", None)
        if namespace:
            for key in ["user", "member", "alvo"]:
                candidate = getattr(namespace, key, None)
                if isinstance(candidate, (discord.Member, discord.User)):
                    target = candidate
                    break

            for key in ["reason", "motivo"]:
                candidate_reason = getattr(namespace, key, None)
                if isinstance(candidate_reason, str) and candidate_reason.strip():
                    reason = candidate_reason.strip()
                    break

        return target, reason

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command: app_commands.Command):
        if interaction.guild is None:
            return

        command_name = command.qualified_name
        await self.stats_service.increment_command(interaction.guild.id, command_name)

        target, reason = self._extract_target_and_reason(interaction)
        await self.audit_logger.log(
            guild=interaction.guild,
            action_name=f"command:{command_name}",
            executor=interaction.user,
            target=target,
            reason=reason,
            metadata={
                "channel_id": interaction.channel_id,
                "command_id": getattr(command, "id", None),
            },
        )

    @app_commands.command(name="stats", description="Mostra estatisticas gerais do bot neste servidor")
    async def stats(self, interaction: discord.Interaction):
        lang = await self.bot.i18n.language_for_interaction(self.bot, interaction)

        labels = {
            "pt": {
                "guild_only": "Esse comando so funciona em servidor.",
                "title": "Estatisticas da Luma",
                "commands": "Comandos usados",
                "api": "IA via API",
                "cache": "IA via cache",
                "warns": "Warns aplicados",
                "tickets": "Tickets abertos",
                "roles": "Cargos auto-atribuidos",
                "top": "Top comandos",
                "footer": "Servidor: {guild}",
            },
            "en": {
                "guild_only": "This command only works in a server.",
                "title": "Luma Stats",
                "commands": "Commands used",
                "api": "AI via API",
                "cache": "AI via cache",
                "warns": "Warnings applied",
                "tickets": "Tickets opened",
                "roles": "Auto-assigned roles",
                "top": "Top commands",
                "footer": "Server: {guild}",
            },
            "es": {
                "guild_only": "Este comando solo funciona en un servidor.",
                "title": "Estadisticas de Luma",
                "commands": "Comandos usados",
                "api": "IA por API",
                "cache": "IA por cache",
                "warns": "Advertencias aplicadas",
                "tickets": "Tickets abiertos",
                "roles": "Roles auto-asignados",
                "top": "Comandos mas usados",
                "footer": "Servidor: {guild}",
            },
        }
        txt = labels[lang]

        if interaction.guild is None:
            await interaction.response.send_message(txt["guild_only"], ephemeral=True)
            return

        overview = await self.stats_service.get_guild_overview(interaction.guild.id)
        metrics = overview["metrics"]
        top_commands = overview["top_commands"]

        embed = discord.Embed(
            title=f"📊 {txt['title']}",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name=txt["commands"], value=str(overview["commands_total"]), inline=True)
        embed.add_field(name=txt["api"], value=str(metrics.get("ai_used_api", 0)), inline=True)
        embed.add_field(name=txt["cache"], value=str(metrics.get("ai_used_cache", 0)), inline=True)
        embed.add_field(name=txt["warns"], value=str(metrics.get("warns_applied", 0)), inline=True)
        embed.add_field(name=txt["tickets"], value=str(metrics.get("tickets_opened", 0)), inline=True)
        embed.add_field(name=txt["roles"], value=str(metrics.get("rolepanel_assignments", 0)), inline=True)

        if top_commands:
            lines = [f"• /{row['command_name']}: {row['used_count']}" for row in top_commands]
            embed.add_field(name=txt["top"], value="\n".join(lines)[:1024], inline=False)

        embed.set_footer(text=txt["footer"].format(guild=interaction.guild.name))
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    print("[DEBUG] Carregando cog Stats...")
    await bot.add_cog(Stats(bot))
    print("[DEBUG] Cog Stats carregado com sucesso!")
