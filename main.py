import asyncio
import logging
import os
import time
import traceback
from pathlib import Path

import asyncpg
import discord
from aiohttp import web
from discord.ext import commands
from dotenv import load_dotenv

from modules.i18n import I18nService
from modules.ops import OwnerAlertService
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

class MyBot(commands.Bot):
    COG_STATE_CACHE_SECONDS = 60

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._commands_synced = False
        self.i18n = I18nService(default_lang="pt")
        self._cog_state_cache: dict[tuple[int, str], tuple[float, bool]] = {}
        self.owner_alerts = OwnerAlertService(self)
        self.database_ready = False
        self.migrations_ready = False
        self._health_runner: web.AppRunner | None = None
        self._health_site: web.TCPSite | None = None

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
        print("""
            ================ COG LOADER ================
            [COG] Carregando extensões...
        """)
        cogs_dir = Path(__file__).parent / "cogs"
        loaded_count = 0
        for path in sorted(cogs_dir.rglob("*.py")):
            if path.name == "__init__.py":
                continue
            # Converte o path para notação de módulo Python:
            # cogs/moderation/mod.py → cogs.moderation.mod
            module_name = ".".join(path.relative_to(Path(__file__).parent).with_suffix("").parts)
            try:
                await self.load_extension(module_name)
                print(f"  ✓ {module_name} carregado com sucesso")
                loaded_count += 1
            except Exception as e:
                print(f"  ✗ {module_name}: {e}")
        print(f"[COG] {loaded_count} extensão(ões) carregada(s).")
        print("            ==========================================\n")

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
            print(f"[COG] Failed to load state for {cog_name} in guild {guild_id}: {exc}")
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
            }
            return web.json_response(payload, status=200)

        async def ready_handler(_request: web.Request) -> web.Response:
            ready = self.database_ready and self.migrations_ready and self.is_ready()
            payload = {
                "status": "ready" if ready else "not_ready",
                "database_ready": self.database_ready,
                "migrations_ready": self.migrations_ready,
                "discord_ready": self.is_ready(),
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

        if not discovered:
            print("[PLUGIN] Nenhum modulo interno encontrado.")
            return

        print("[PLUGIN] Modulos internos detectados:")
        for module in discovered:
            print(f"  • {module.name}")

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
            print("[DB - Error] No database configuration found. Set DATABASE_URL or DB_USER/DB_PASSWORD/DB_NAME/DB_HOST/DB_PORT.")
            await self.close()
            return

        for source_name, connection_kwargs in targets:
            for i in range(5):
                print(f"""
                ================ DATABASE INIT ================
                [DB] Source  : {source_name}
                [DB] Status  : Starting connection (Attempt {i+1}/5)
                [DB] Host    : {os.getenv("DB_HOST")}
                [DB] Port    : {os.getenv("DB_PORT")}
                [DB] User    : {os.getenv("DB_USER")}
                [DB] Database: {os.getenv("DB_NAME")}

                [DB] Trying to connect to the database...
                ===============================================
            """)
                try:
                    self.pool = await asyncpg.create_pool(**connection_kwargs)
                    self.database_ready = True
                    print(f"[DB] Database connection established via {source_name}.")
                    break
                except Exception as e:
                    print(f"[DB - Error] Database connection failed via {source_name} (Attempt {i+1}/5): {e}")
                    if i < 4:
                        print("[DB] Retrying in 5 seconds...")
                        await asyncio.sleep(5)
                    else:
                        print(f"[DB - Error] All attempts failed via {source_name}.")
            else:
                continue

            break
        else:
            print("[DB - Error] Could not connect using DATABASE_URL or DB_* settings. Shutting down.")
            await self.close()
            return

        await asyncio.sleep(1)
        print("""
            ================ DATABASE SETUP ================
            [DB] Setting up database tables...
        """)
        try:
            await self._run_migrations()
            self.migrations_ready = True
        except Exception as e:
            print(f"[DB - Error] Failed to set up database tables: {e}")
            await self.notify_owner_error("database_setup", e, context="Failed to run migrations during startup")
            await self.close()
            return
    
    async def _run_migrations(self):
        """Execute all SQL migration files with tracking to prevent duplicates"""
        migrations_dir = Path(__file__).parent / "migrations"
        
        if not migrations_dir.exists():
            print("[DB] No migrations directory found, skipping migrations.")
            return
        
        migration_files = sorted(migrations_dir.glob("*.sql"))
        
        if not migration_files:
            print("[DB] No migration files found.")
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
                print(f"[DB - Error] Failed to create migrations table: {e}")
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
                        print(f"[DB] ⏭️  Migration already executed: {migration_name}")
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
                        print(f"[DB] ✅ Migration executed: {migration_name}")
                    
                except Exception as e:
                    print(f"[DB - Error] Failed to execute migration {migration_name}: {e}")
                    raise

bot = MyBot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        await bot.change_presence(activity=discord.Game(name="Luma!"))
    except Exception as exc:
        print(f"[BOT - Error] Falha ao atualizar presence: {exc}")

    if not bot._commands_synced:
        try:
            await bot.sync_command_tree()
            print("[BOT] Slash commands sincronizados com sucesso.")
        except Exception as e:
            print(f"[BOT - Error] Falha ao sincronizar slash commands: {e}")
            await bot.notify_owner_error("slash_sync", e, context="Failed to sync slash command tree")

    print(f"""
            ================ BOT READY ===============
            [BOT] Conectado como {bot.user}
            [BOT] ID: {bot.user.id}
            ==========================================
    """)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    command_name = interaction.command.qualified_name if interaction.command else "unknown"
    logger.exception("[APP_CMD - Error] /%s: %s", command_name, error)
    await bot.notify_owner_error(
        "app_command",
        error,
        context=f"command=/{command_name} guild={getattr(interaction.guild, 'id', None)} user={interaction.user.id}",
    )

    message = "Ocorreu um erro ao executar este comando. Tenta novamente em alguns segundos."
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