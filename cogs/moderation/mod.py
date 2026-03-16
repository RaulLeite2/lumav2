import os
from datetime import timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from modules.admin.services import AuditLogger
from modules.ai.services import GroqClient
from modules.moderation.services import StatsService
from scripts.db import Database


def tr(lang: str, pt: str, en: str, es: str) -> str:
    return {"pt": pt, "en": en, "es": es}.get(lang, pt)


class ModerationLogger:
    @staticmethod
    async def get_log_channel(bot, guild_id: int, action: str) -> Optional[discord.TextChannel]:
        try:
            database = Database(bot.pool)
            try:
                result = await database.fetchrow(
                    """
                    SELECT
                        log_channel_id,
                        log_ban_channel_id,
                        logs_enabled,
                        log_moderation,
                        log_ban_events
                    FROM guilds
                    WHERE guild_id = $1
                    """,
                    guild_id,
                )
            except Exception:
                # Backward-compatible fallback while older schemas are still around.
                result = await database.fetchrow("SELECT log_channel_id FROM guilds WHERE guild_id = $1", guild_id)

            if not result:
                return None

            result = dict(result)

            logs_enabled = True if "logs_enabled" not in result else bool(result["logs_enabled"])
            if not logs_enabled:
                return None

            normalized_action = action.lower()
            channel_id = result.get("log_channel_id")

            if normalized_action in {"ban", "unban"}:
                if "log_ban_events" in result and not bool(result["log_ban_events"]):
                    return None
                channel_id = result.get("log_ban_channel_id") or channel_id
            else:
                if "log_moderation" in result and not bool(result["log_moderation"]):
                    return None

            if channel_id:
                guild = bot.get_guild(guild_id)
                if guild:
                    channel = guild.get_channel(channel_id)
                    if isinstance(channel, discord.TextChannel):
                        return channel
        except Exception as e:
            print(f"[Moderation] log channel error: {e}")
        return None

    @staticmethod
    async def log_action(bot, guild: discord.Guild, action: str, moderator: discord.Member, target: discord.Member | discord.User, reason: Optional[str] = None, duration: Optional[str] = None):
        log_channel = await ModerationLogger.get_log_channel(bot, guild.id, action)
        if log_channel is None:
            return False

        color_map = {
            "ban": discord.Color.red(),
            "unban": discord.Color.green(),
            "kick": discord.Color.orange(),
            "timeout": discord.Color.yellow(),
            "warn": discord.Color.gold(),
            "purge": discord.Color.blue(),
        }
        embed = discord.Embed(
            title=f"{action.upper()}",
            color=color_map.get(action.lower(), discord.Color.greyple()),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Moderator", value=f"{moderator.mention}", inline=True)
        embed.add_field(name="Target", value=f"{target.mention if hasattr(target, 'mention') else target}", inline=True)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        if duration:
            embed.add_field(name="Duration", value=duration, inline=True)
        try:
            await log_channel.send(embed=embed)
            return True
        except Exception:
            return False


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.stats_service = StatsService(bot.pool)
        self.audit_logger = AuditLogger(bot.pool)
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    mod = app_commands.Group(name="mod", description="Moderation commands")

    async def _lang(self, interaction: discord.Interaction) -> str:
        return await self.bot.i18n.language_for_interaction(self.bot, interaction)

    async def _ensure_cog_enabled(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return True
        if await self.bot.is_cog_enabled(interaction.guild.id, "mod"):
            return True

        lang = await self._lang(interaction)
        await interaction.response.send_message(
            tr(lang, "A moderacao esta desativada neste servidor pelo painel.", "Moderation is disabled in this server by the dashboard.", "La moderacion esta desactivada en este servidor por el panel."),
            ephemeral=True,
        )
        return False

    async def _check_perm(self, interaction: discord.Interaction, permission: str, action_desc: str) -> bool:
        lang = await self._lang(interaction)
        if not getattr(interaction.user.guild_permissions, permission, False):
            await interaction.response.send_message(tr(lang, f"Ops! Voce nao tem permissao para {action_desc}.", f"Oops! You do not have permission to {action_desc}.", f"Ups! No tienes permiso para {action_desc}."), ephemeral=True)
            return False
        bot_member = interaction.guild.get_member(self.bot.user.id) if interaction.guild and self.bot.user else None
        if not bot_member or not getattr(bot_member.guild_permissions, permission, False):
            await interaction.response.send_message(tr(lang, f"Eu nao tenho permissao para {action_desc} ainda.", f"I do not have permission to {action_desc} yet.", f"No tengo permiso para {action_desc} aun."), ephemeral=True)
            return False
        return True

    @mod.command(name="ban", description="Ban a user")
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        lang = await self._lang(interaction)
        if not await self._ensure_cog_enabled(interaction):
            return
        if not await self._check_perm(interaction, "ban_members", "ban"):
            return
        if user == interaction.user:
            await interaction.response.send_message(tr(lang, "Ei, voce nao pode se banir.", "Hey, you cannot ban yourself.", "Hey, no puedes banearte a ti mismo."), ephemeral=True)
            return

        await user.ban(reason=reason)
        await interaction.response.send_message(tr(lang, f"Prontinho! {user.mention} foi banido.", f"All set! {user.mention} was banned.", f"Listo! {user.mention} fue baneado."))
        await ModerationLogger.log_action(self.bot, interaction.guild, "ban", interaction.user, user, reason=reason)

    @mod.command(name="unban", description="Unban by user ID")
    async def unban(self, interaction: discord.Interaction, user_id: str):
        lang = await self._lang(interaction)
        if not await self._ensure_cog_enabled(interaction):
            return
        if not await self._check_perm(interaction, "ban_members", "unban"):
            return

        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            await interaction.response.send_message(tr(lang, f"Tudo certo! Usuario {user.mention} desbanido.", f"Done! User {user.mention} was unbanned.", f"Todo bien! Usuario {user.mention} fue desbaneado."))
            await ModerationLogger.log_action(self.bot, interaction.guild, "unban", interaction.user, user)
        except Exception as exc:
            await interaction.response.send_message(tr(lang, f"Nao consegui desbanir agora: {exc}", f"I could not unban right now: {exc}", f"No pude desbanear ahora: {exc}"), ephemeral=True)

    @mod.command(name="kick", description="Kick a user")
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        lang = await self._lang(interaction)
        if not await self._ensure_cog_enabled(interaction):
            return
        if not await self._check_perm(interaction, "kick_members", "kick"):
            return
        if user == interaction.user:
            await interaction.response.send_message(tr(lang, "Ei, voce nao pode se expulsar.", "Hey, you cannot kick yourself.", "Hey, no puedes expulsarte a ti mismo."), ephemeral=True)
            return

        await user.kick(reason=reason)
        await interaction.response.send_message(tr(lang, f"Feito! {user.mention} foi expulso.", f"Done! {user.mention} was kicked.", f"Hecho! {user.mention} fue expulsado."))
        await ModerationLogger.log_action(self.bot, interaction.guild, "kick", interaction.user, user, reason=reason)

    @mod.command(name="timeout", description="Apply timeout to a user")
    async def timeout(self, interaction: discord.Interaction, user: discord.Member, duration: str, reason: str):
        lang = await self._lang(interaction)
        if not await self._ensure_cog_enabled(interaction):
            return
        if not await self._check_perm(interaction, "moderate_members", "timeout members"):
            return

        def parse_duration(duration_str: str) -> int:
            unit_multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
            if len(duration_str) < 2:
                raise ValueError("invalid format")
            unit = duration_str[-1].lower()
            if unit not in unit_multipliers:
                raise ValueError("invalid unit")
            value = int(duration_str[:-1])
            seconds = value * unit_multipliers[unit]
            if seconds <= 0 or seconds > 28 * 24 * 60 * 60:
                raise ValueError("invalid range")
            return seconds

        try:
            seconds = parse_duration(duration)
            timeout_until = discord.utils.utcnow() + timedelta(seconds=seconds)
            await user.timeout(timeout_until, reason=reason)
            await interaction.response.send_message(tr(lang, f"Tudo certo! {user.mention} entrou em timeout por {duration}.", f"All good! {user.mention} was timed out for {duration}.", f"Todo bien! {user.mention} entro en timeout por {duration}."))
            await ModerationLogger.log_action(self.bot, interaction.guild, "timeout", interaction.user, user, reason=reason, duration=duration)
        except Exception as exc:
            await interaction.response.send_message(tr(lang, f"Nao consegui aplicar timeout agora: {exc}", f"I could not apply timeout right now: {exc}", f"No pude aplicar timeout ahora: {exc}"), ephemeral=True)

    @mod.command(name="warn", description="Warn a user")
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        lang = await self._lang(interaction)
        if not await self._ensure_cog_enabled(interaction):
            return
        if not await self._check_perm(interaction, "manage_messages", "warn users"):
            return

        db = Database(self.bot.pool)
        warning_row = await db.fetchrow(
            """
            INSERT INTO user_warnings (guild_id, user_id, warning_count)
            VALUES ($1, $2, 1)
            ON CONFLICT (guild_id, user_id)
            DO UPDATE SET warning_count = user_warnings.warning_count + 1, warned_at = CURRENT_TIMESTAMP
            RETURNING warning_count
            """,
            interaction.guild.id,
            user.id,
        )
        warning_count = warning_row["warning_count"] if warning_row else 1

        guild_settings = await db.fetchrow(
            "SELECT auto_moderation, quant_warnings, acao, warn_dm_user FROM guilds WHERE guild_id = $1",
            interaction.guild.id,
        )
        escalation_rows = await db.fetch(
            "SELECT threshold, action FROM guild_warning_escalations WHERE guild_id = $1 ORDER BY threshold ASC",
            interaction.guild.id,
        )
        escalation_steps = [
            {"threshold": int(item["threshold"]), "action": str(item["action"]).lower()}
            for item in escalation_rows
            if item and item["threshold"] is not None and item["action"] is not None
        ]
        if not escalation_steps:
            fallback_threshold = guild_settings["quant_warnings"] if guild_settings and guild_settings["quant_warnings"] else 3
            fallback_action = str(guild_settings["acao"] if guild_settings and guild_settings["acao"] else "kick").lower()
            escalation_steps = [{"threshold": int(fallback_threshold), "action": fallback_action}]
        quant_warnings = max(step["threshold"] for step in escalation_steps)

        embed = discord.Embed(
            title=tr(lang, "Usuario advertido", "User warned", "Usuario advertido"),
            description=tr(lang, f"{user.mention} recebeu um aviso. Vamos manter tudo em ordem.", f"{user.mention} received a warning. Let's keep things in order.", f"{user.mention} recibio una advertencia. Mantengamos todo en orden."),
            color=discord.Color.orange(),
        )
        embed.add_field(name=tr(lang, "Avisos", "Warnings", "Advertencias"), value=f"{warning_count}/{quant_warnings}", inline=True)
        embed.add_field(name=tr(lang, "Motivo", "Reason", "Motivo"), value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

        if guild_settings is None or guild_settings["warn_dm_user"] is None or bool(guild_settings["warn_dm_user"]):
            try:
                dm_embed = discord.Embed(
                    title=tr(lang, "Voce recebeu um aviso", "You received a warning", "Recibiste una advertencia"),
                    description=tr(
                        lang,
                        f"Servidor: **{interaction.guild.name}**\nMotivo: {reason}",
                        f"Server: **{interaction.guild.name}**\nReason: {reason}",
                        f"Servidor: **{interaction.guild.name}**\nMotivo: {reason}",
                    ),
                    color=discord.Color.orange(),
                    timestamp=discord.utils.utcnow(),
                )
                dm_embed.add_field(name=tr(lang, "Avisos", "Warnings", "Advertencias"), value=f"{warning_count}/{quant_warnings}", inline=True)
                await user.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        matching_step = next((step for step in escalation_steps if warning_count == int(step["threshold"])), None)
        if matching_step is not None:
            action = str(matching_step["action"])
            try:
                if action == "kick":
                    await user.kick(reason=f"Warn escalation reached ({warning_count})")
                    await ModerationLogger.log_action(self.bot, interaction.guild, "kick", interaction.user, user, reason=reason)
                elif action == "ban":
                    await user.ban(reason=f"Warn escalation reached ({warning_count})", delete_message_days=0)
                    await ModerationLogger.log_action(self.bot, interaction.guild, "ban", interaction.user, user, reason=reason)
                elif action in {"mute", "timeout"}:
                    await user.timeout(discord.utils.utcnow() + timedelta(hours=1), reason=f"Warn escalation reached ({warning_count})")
                    await ModerationLogger.log_action(self.bot, interaction.guild, "timeout", interaction.user, user, reason=reason, duration="1h")
            except Exception:
                pass

        await self.stats_service.increment_metric(interaction.guild.id, "warns_applied")
        await self.audit_logger.log(
            guild=interaction.guild,
            action_name="moderation:warn",
            executor=interaction.user,
            target=user,
            reason=reason,
            metadata={"warning_count": warning_count, "threshold": quant_warnings},
        )
        await ModerationLogger.log_action(self.bot, interaction.guild, "warn", interaction.user, user, reason=reason)

    @mod.command(name="ai-analisar", description="Analyze message with AI")
    async def ai_analisar(self, interaction: discord.Interaction, mensagem: str):
        lang = await self._lang(interaction)
        if not await self._ensure_cog_enabled(interaction):
            return
        if not await self._check_perm(interaction, "manage_messages", "analyze messages"):
            return

        if not self.groq_api_key:
            await interaction.response.send_message(
                tr(lang, "GROQ_API_KEY nao esta configurada ainda.", "GROQ_API_KEY is not configured yet.", "GROQ_API_KEY aun no esta configurada."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        prompt = (
            "You are a moderation assistant. Analyze the text and return strict JSON with keys: "
            "toxicity(0-100), spam(0-100), aggression(0-100), suggested_action(none|warn|timeout|kick|ban), "
            "justification, risk(low|medium|high).\n\n"
            f"Message: {mensagem}"
        )

        client = GroqClient(
            api_url="https://api.groq.com/openai/v1/chat/completions",
            api_key=self.groq_api_key,
            model_name=self.groq_model,
        )

        try:
            raw = await client.chat_completion(
                system_prompt="Return valid JSON only.",
                user_prompt=prompt,
                temperature=0.2,
            )
        except Exception as exc:
            await interaction.followup.send(tr(lang, f"Nao consegui consultar a IA agora: {exc}", f"I could not query AI right now: {exc}", f"No pude consultar la IA ahora: {exc}"), ephemeral=True)
            return

        toxicity = "N/A"
        spam = "N/A"
        aggression = "N/A"
        suggested = "N/A"
        justification = raw[:900] if raw else "No output"
        risk = "N/A"

        try:
            import json

            parsed = json.loads(raw)
            toxicity = parsed.get("toxicity", parsed.get("toxicidade", "N/A"))
            spam = parsed.get("spam", "N/A")
            aggression = parsed.get("aggression", parsed.get("agressividade", "N/A"))
            suggested = parsed.get("suggested_action", parsed.get("sugestao_punicao", "N/A"))
            justification = parsed.get("justification", parsed.get("justificativa", "No justification"))
            risk = parsed.get("risk", parsed.get("risco_geral", "N/A"))
        except Exception:
            pass

        embed = discord.Embed(
            title=tr(lang, "Analise de IA para Moderacao", "AI Moderation Analysis", "Analisis de IA para Moderacion"),
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name=tr(lang, "Mensagem", "Message", "Mensaje"), value=mensagem[:1024], inline=False)
        embed.add_field(name=tr(lang, "Toxicidade", "Toxicity", "Toxicidad"), value=f"{toxicity}", inline=True)
        embed.add_field(name="Spam", value=f"{spam}", inline=True)
        embed.add_field(name=tr(lang, "Agressividade", "Aggression", "Agresividad"), value=f"{aggression}", inline=True)
        embed.add_field(name=tr(lang, "Risco", "Risk", "Riesgo"), value=f"{risk}", inline=True)
        embed.add_field(name=tr(lang, "Sugestao", "Suggestion", "Sugerencia"), value=f"{suggested}", inline=True)
        embed.add_field(name=tr(lang, "Justificativa", "Justification", "Justificacion"), value=str(justification)[:1024], inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)
        await self.stats_service.increment_metric(interaction.guild.id, "ai_moderation_checks")

    @mod.command(name="purge", description="Purge messages from current channel")
    async def purge(self, interaction: discord.Interaction, limit: int):
        lang = await self._lang(interaction)
        if not await self._ensure_cog_enabled(interaction):
            return
        if not await self._check_perm(interaction, "manage_messages", "purge messages"):
            return

        if limit < 1 or limit > 500:
            await interaction.response.send_message(tr(lang, "Escolha um limite entre 1 e 500, por favor.", "Please choose a limit between 1 and 500.", "Por favor elige un limite entre 1 y 500."), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        deleted = await interaction.channel.purge(limit=limit)
        await interaction.followup.send(tr(lang, f"Prontinho! Deletei {len(deleted)} mensagens.", f"All set! Deleted {len(deleted)} messages.", f"Listo! Se eliminaron {len(deleted)} mensajes."), ephemeral=True)
        await ModerationLogger.log_action(self.bot, interaction.guild, "purge", interaction.user, interaction.user, reason=f"purge {len(deleted)}")


async def setup(bot):
    print("[DEBUG] Carregando cog Moderation...")
    await bot.add_cog(Moderation(bot))
    print("[DEBUG] Cog Moderation carregado com sucesso!")
