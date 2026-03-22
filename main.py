import asyncio
import time

import discord 
import asyncpg 
from discord.ext import commands
import os
from dotenv import load_dotenv
from pathlib import Path

from scripts import db
from modules.i18n import I18nService
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

class MyBot(commands.Bot):
    COG_STATE_CACHE_SECONDS = 60

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._commands_synced = False
        self.i18n = I18nService(default_lang="pt")
        self._cog_state_cache: dict[tuple[int, str], tuple[float, bool]] = {}

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
        self._discover_internal_modules()
        await self.database_connect()
        await self.load_cogs()

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
        print("[BOT] Shutting down...")
        pool = getattr(self, "pool", None)
        if pool is not None:
            await pool.close()
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
        except Exception as e:
            print(f"[DB - Error] Failed to set up database tables: {e}")
            await self.close()
            return
    
    async def _run_migrations(self):
        """Execute all SQL migration files"""
        migrations_dir = Path(__file__).parent / "migrations"
        
        if not migrations_dir.exists():
            print("[DB] No migrations directory found, skipping migrations.")
            return
        
        migration_files = sorted(migrations_dir.glob("*.sql"))
        
        if not migration_files:
            print("[DB] No migration files found.")
            return
        
        async with self.pool.acquire() as conn:
            for migration_file in migration_files:
                try:
                    with open(migration_file, 'r', encoding='utf-8') as f:
                        sql_content = f.read()
                    
                    await conn.execute(sql_content)
                    print(f"[DB] ✅ Migration executed: {migration_file.name}")
                    
                except Exception as e:
                    print(f"[DB - Error] Failed to execute migration {migration_file.name}: {e}")
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

    print(f"""
            ================ BOT READY ===============
            [BOT] Conectado como {bot.user}
            [BOT] ID: {bot.user.id}
            ==========================================
    """)

bot.run(TOKEN)