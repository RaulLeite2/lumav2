import asyncio
import logging
import os
import re
import time
import traceback
from pathlib import Path

import asyncpg
import discord
from discord import app_commands
from aiohttp import web
from discord.ext import commands
from dotenv import load_dotenv

from modules.i18n import I18nService
from modules.moderation.services import StatsService
from modules.ops import CommandRateLimiter, ErrorCatalog, ErrorCode, OwnerAlertService
from modules.plugin_system import PluginSystem

# Carrega as variáveis do arquivo .env
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

TOKEN = os.getenv("TOKEN")
if TOKEN is None:
    print("[ERROR] TOKEN environment variable not set. Please set it and restart the bot.")
    exit(1)


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


configure_logging()
logger = logging.getLogger(__name__)


class LumaCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None or interaction.command is None:
            return True

        bot = self.client
        if not isinstance(bot, MyBot):
            return True

        command_name = interaction.command.qualified_name
        allowed, retry_after = bot.command_rate_limiter.allow(interaction.guild.id, command_name)
        if allowed:
            return True

        await bot.record_rate_limit_metric(interaction.guild.id, command_name)
        message = (
            f"Rate limit do comando /{command_name} atingido neste servidor. "
            f"Tente novamente em {max(1, int(retry_after))}s."
        )
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
        return False


class MyBot(commands.AutoShardedBot):
    COG_STATE_CACHE_SECONDS = 60

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._commands_synced = False
        self.i18n = I18nService(default_lang="pt")
        self._cog_state_cache: dict[tuple[int, str], tuple[float, bool]] = {}
        self.owner_alerts = OwnerAlertService(self)
        self.command_rate_limiter = CommandRateLimiter(
            limit=int(os.getenv("COMMAND_RATE_LIMIT_PER_GUILD", "30")),
            window_seconds=int(os.getenv("COMMAND_RATE_LIMIT_WINDOW_SECONDS", "60")),
        )
        self.stats_service: StatsService | None = None
        self.loaded_cogs: list[str] = []
        self.failed_cogs: list[str] = []
        self.internal_modules: list[str] = []
        self.database_ready = False
        self.migrations_ready = False
        self._health_runner: web.AppRunner | None = None
        self._health_site: web.TCPSite | None = None

    async def record_rate_limit_metric(self, guild_id: int, command_name: str) -> None:
        if self.stats_service is None:
            return

        metric_suffix = re.sub(r"[^a-z0-9_]+", "_", command_name.lower().replace(" ", "_"))
        metric_suffix = metric_suffix.strip("_")[:80] or "unknown"
        try:
            await self.stats_service.increment_metric(guild_id, "rate_limited_total")
            await self.stats_service.increment_metric(guild_id, f"rate_limited_{metric_suffix}")
        except Exception as exc:
            logger.warning("Failed to store rate-limit metric for guild %s command %s: %s", guild_id, command_name, exc)

    @staticmethod
    def _database_targets() -> list[tuple[str, dict[str, str | None]]]:
        database_url = os.getenv("DATABASE_URL")
        discrete_config = {
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "database": os.getenv("DB_NAME"),
            "host": os.getenv("DB_HOST"),
            "port": os.getenv("DB_PORT"),
        }

        targets: list[tuple[str, dict[str, str | None]]] = []
        if database_url:
            targets.append(("DATABASE_URL", {"dsn": database_url}))

        if all(discrete_config.values()):
            targets.append(("DB_*", discrete_config))

        return targets
    
    async def load_cogs(self):
        logger.info("[COG] Loading extensions...")
        cogs_dir = Path(__file__).parent / "cogs"
        self.loaded_cogs = []
        self.failed_cogs = []
        for path in sorted(cogs_dir.rglob("*.py")):
            if path.name == "__init__.py":
                continue
            # Converte o path para notação de módulo Python:
            # cogs/moderation/mod.py → cogs.moderation.mod
            module_name = ".".join(path.relative_to(Path(__file__).parent).with_suffix("").parts)
            try:
                await self.load_extension(module_name)
                self.loaded_cogs.append(module_name)
                logger.info("[COG] loaded=%s", module_name)
            except Exception as e:
                self.failed_cogs.append(module_name)
                logger.exception("[COG] failed=%s error=%s", module_name, e)
        logger.info("[COG] loaded_count=%s failed_count=%s", len(self.loaded_cogs), len(self.failed_cogs))

    async def is_cog_enabled(self, guild_id: int | None, cog_name: str) -> bool:
        if guild_id is None:
            return True

        cache_key = (guild_id, cog_name)
        now = time.monotonic()
        cached = self._cog_state_cache.get(cache_key)
        if cached and (now - cached[0]) < self.COG_STATE_CACHE_SECONDS:
            return cached[1]

        pool = getattr(self, "pool", None)
        if pool is None:
            return True

        try:
            async with pool.acquire() as connection:
                enabled = await connection.fetchval(
                    "SELECT enabled FROM guild_cog_settings WHERE guild_id = $1 AND cog_name = $2",
                    guild_id,
                    cog_name,
                )
        except Exception as exc:
            logger.warning("[COG] Failed to load state for %s in guild %s: %s", cog_name, guild_id, exc)
            return True

        effective = True if enabled is None else bool(enabled)
        self._cog_state_cache[cache_key] = (now, effective)
        return effective

    def invalidate_cog_cache(self, guild_id: int | None = None, cog_name: str | None = None) -> None:
        if guild_id is None and cog_name is None:
            self._cog_state_cache.clear()
            return

        stale_keys = []
        for cached_guild_id, cached_cog_name in self._cog_state_cache:
            if guild_id is not None and cached_guild_id != guild_id:
                continue
            if cog_name is not None and cached_cog_name != cog_name:
                continue
            stale_keys.append((cached_guild_id, cached_cog_name))

        for key in stale_keys:
            self._cog_state_cache.pop(key, None)

    async def setup_hook(self):
        await self._start_health_server()
        self._discover_internal_modules()
        await self.database_connect()
        await self.load_cogs()

    async def notify_owner_error(
        self,
        title: str,
        error: BaseException,
        context: str | None = None,
        *,
        is_test: bool = False,
    ) -> None:
        await self.owner_alerts.notify_error(title=title, error=error, context=context, is_test=is_test)

    async def _start_health_server(self) -> None:
        host = os.getenv("HEALTHCHECK_HOST", "0.0.0.0")
        raw_port = os.getenv("HEALTHCHECK_PORT") or os.getenv("PORT") or "8080"
        try:
            port = int(raw_port)
        except ValueError:
            logger.warning("Invalid HEALTHCHECK_PORT/PORT value: %s. Falling back to 8080.", raw_port)
            port = 8080

        async def health_handler(_request: web.Request) -> web.Response:
            payload = {
                "status": "ok",
                "database_ready": self.database_ready,
                "migrations_ready": self.migrations_ready,
                "discord_ready": self.is_ready(),
                "loaded_cogs": len(self.loaded_cogs),
                "failed_cogs": len(self.failed_cogs),
                "internal_modules": len(self.internal_modules),
            }
            return web.json_response(payload, status=200)

        async def ready_handler(_request: web.Request) -> web.Response:
            ready = self.database_ready and self.migrations_ready and self.is_ready()
            payload = {
                "status": "ready" if ready else "not_ready",
                "database_ready": self.database_ready,
                "migrations_ready": self.migrations_ready,
                "discord_ready": self.is_ready(),
                "loaded_cogs": len(self.loaded_cogs),
                "failed_cogs": len(self.failed_cogs),
            }
            return web.json_response(payload, status=200 if ready else 503)

        app = web.Application()
        app.router.add_get("/health", health_handler)
        app.router.add_get("/ready", ready_handler)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host=host, port=port)
        await site.start()

        self._health_runner = runner
        self._health_site = site
        logger.info("Health server listening on %s:%s", host, port)

    def _discover_internal_modules(self):
        modules_root = Path(__file__).parent / "modules"
        plugin_system = PluginSystem(modules_root)
        discovered = plugin_system.discover()
        self.internal_modules = [module.name for module in discovered]

        if not discovered:
            logger.info("[PLUGIN] No internal modules found.")
            return

        logger.info("[PLUGIN] Internal modules detected:")
        for module in discovered:
            logger.info("[PLUGIN] module=%s", module.name)

    async def sync_command_tree(self):
        # Limpa comandos de guild antigos para evitar CommandSignatureMismatch.
        for guild in self.guilds:
            self.tree.clear_commands(guild=guild)
            await self.tree.sync(guild=guild)

        await self.tree.sync()
        self._commands_synced = True
        
    async def close(self):
        logger.info("[BOT] Shutting down...")
        pool = getattr(self, "pool", None)
        if pool is not None:
            await pool.close()

        if self._health_runner is not None:
            await self._health_runner.cleanup()
            self._health_runner = None
            self._health_site = None

        await super().close()
    
    async def database_connect(self):
        targets = self._database_targets()

        if not targets:
            logger.error("[DB] No database configuration found. Set DATABASE_URL or DB_USER/DB_PASSWORD/DB_NAME/DB_HOST/DB_PORT.")
            await self.close()
            return

        for source_name, connection_kwargs in targets:
            for i in range(5):
                logger.info("[DB] source=%s attempt=%s/5 connecting...", source_name, i + 1)
                try:
                    self.pool = await asyncpg.create_pool(**connection_kwargs)
                    self.database_ready = True
                    self.stats_service = StatsService(self.pool)
                    logger.info("[DB] Database connection established via %s", source_name)
                    break
                except Exception as e:
                    logger.error("[DB] Database connection failed via %s (attempt %s/5): %s", source_name, i + 1, e)
                    if i < 4:
                        logger.info("[DB] Retrying in 5 seconds...")
                        await asyncio.sleep(5)
                    else:
                        logger.error("[DB] All attempts failed via %s", source_name)
            else:
                continue

            break
        else:
            logger.error("[DB] Could not connect using DATABASE_URL or DB_* settings. Shutting down.")
            await self.close()
            return

        await asyncio.sleep(1)
        logger.info("[DB] Setting up database tables...")
        try:
            await self._run_migrations()
            self.migrations_ready = True
        except Exception as e:
            logger.error("[DB] Failed to set up database tables: %s", e)
            await self.notify_owner_error("database_setup", e, context="Failed to run migrations during startup")
            await self.close()
            return
    
    async def _run_migrations(self):
        """Execute all SQL migration files with tracking to prevent duplicates"""
        migrations_dir = Path(__file__).parent / "migrations"
        
        if not migrations_dir.exists():
            logger.info("[DB] No migrations directory found, skipping migrations.")
            return
        
        migration_files = sorted(migrations_dir.glob("*.sql"))
        
        if not migration_files:
            logger.info("[DB] No migration files found.")
            return
        
        async with self.pool.acquire() as conn:
            # Create migrations tracking table
            try:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        migration_name TEXT PRIMARY KEY,
                        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            except Exception as e:
                logger.error("[DB] Failed to create migrations table: %s", e)
                raise
            
            for migration_file in migration_files:
                migration_name = migration_file.name
                try:
                    # Check if migration already executed
                    executed = await conn.fetchval(
                        "SELECT 1 FROM schema_migrations WHERE migration_name = $1",
                        migration_name,
                    )
                    
                    if executed:
                        logger.info("[DB] Migration already executed: %s", migration_name)
                        continue
                    
                    # Execute migration in transaction
                    async with conn.transaction():
                        # utf-8-sig tolerates accidental BOM in SQL files.
                        with open(migration_file, 'r', encoding='utf-8-sig') as f:
                            sql_content = f.read()
                        
                        await conn.execute(sql_content)
                        
                        # Register execution
                        await conn.execute(
                            "INSERT INTO schema_migrations (migration_name) VALUES ($1)",
                            migration_name,
                        )
                        logger.info("[DB] Migration executed: %s", migration_name)
                    
                except Exception as e:
                    logger.error("[DB] Failed to execute migration %s: %s", migration_name, e)
                    raise

shard_count_raw = os.getenv("SHARD_COUNT", "").strip()
bot_kwargs: dict[str, object] = {
    "command_prefix": "!",
    "intents": intents,
    "tree_cls": LumaCommandTree,
}
if shard_count_raw.isdigit() and int(shard_count_raw) > 0:
    bot_kwargs["shard_count"] = int(shard_count_raw)

bot = MyBot(**bot_kwargs)

@bot.event
async def on_ready():
    try:
        await bot.change_presence(activity=discord.Game(name="Luma!"))
    except Exception as exc:
        logger.warning("[BOT] Failed to update presence: %s", exc)

    if not bot._commands_synced:
        try:
            await bot.sync_command_tree()
            logger.info("[BOT] Slash commands synced successfully.")
        except Exception as e:
            logger.error("[BOT] Failed to sync slash commands: %s", e)
            await bot.notify_owner_error("slash_sync", e, context="Failed to sync slash command tree")

    logger.info(
        "[BOT] ready user=%s id=%s shard_count=%s loaded_cogs=%s failed_cogs=%s",
        bot.user,
        bot.user.id if bot.user else None,
        bot.shard_count,
        len(bot.loaded_cogs),
        len(bot.failed_cogs),
    )


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    command_name = interaction.command.qualified_name if interaction.command else "unknown"
    lang = await bot.i18n.language_for_interaction(bot, interaction)
    error_code = ErrorCatalog.from_exception(error)
    logger.exception("[APP_CMD - Error] /%s: %s", command_name, error)
    await bot.notify_owner_error(
        "app_command",
        error,
        context=(
            f"command=/{command_name} guild={getattr(interaction.guild, 'id', None)} "
            f"user={interaction.user.id} code={error_code.value}"
        ),
    )

    message = f"{ErrorCatalog.user_message(error_code, lang)} (codigo: {error_code.value})"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except Exception as notify_error:
        logger.exception("[APP_CMD - Error] Falha ao notificar usuario: %s", notify_error)


@bot.event
async def on_error(event_method: str, *args, **kwargs):
    error = traceback.format_exc()
    logger.error("[BOT - Error] Event %s failed: %s", event_method, error)
    try:
        raise RuntimeError(f"Unhandled event error in {event_method}\n{error}")
    except RuntimeError as wrapped_error:
        await bot.notify_owner_error(
            "event_error",
            wrapped_error,
            context=f"event={event_method}",
        )

bot.run(TOKEN)