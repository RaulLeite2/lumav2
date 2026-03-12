import asyncio

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

TOKEN = os.getenv("TOKEN")
if TOKEN is None:
    print("[ERROR] TOKEN environment variable not set. Please set it and restart the bot.")
    exit(1)

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._commands_synced = False
        self.i18n = I18nService(default_lang="pt")
    
    async def load_cogs(self):
        print("""
            ================ COG LOADER ================
            [COG] Carregando extensões...
        """)
        cog = os.listdir("cogs")
        loaded_count = 0
        if cog:
            for filename in cog:
                if filename.endswith(".py") and filename != "__init__.py":
                    try:
                        await self.load_extension(f"cogs.{filename[:-3]}")
                        print(f"  ✓ {filename[:-3]} carregado com sucesso")
                        loaded_count += 1
                    except Exception as e:
                        print(f"  ✗ {filename[:-3]}: {e}")
        print(f"[COG] {loaded_count} extensão(ões) carregada(s).")
        print("            ==========================================\n")

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
        await self.pool.close()
        await super().close()
    
    async def database_connect(self):
        for i in range(5):
            print(f"""
                ================ DATABASE INIT ================
                [DB] Status  : Starting connection(Tentative {i+1}/5)
                [DB] Host    : {os.getenv("DB_HOST")}
                [DB] Port    : {os.getenv("DB_PORT")}
                [DB] User    : {os.getenv("DB_USER")}
                [DB] Database: {os.getenv("DB_NAME")}
                
                [DB] Trying to connect to the database...
                ===============================================
            """)
            try:
                self.pool = await asyncpg.create_pool(
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    database=os.getenv("DB_NAME"),
                    host=os.getenv("DB_HOST"),
                    port=os.getenv("DB_PORT")
                )
                print("[DB] Database connection established.")
                break
            except Exception as e:
                print(f"[DB - Error] Database connection failed (Attempt {i+1}/5): {e}")
                if i < 4:
                    print("[DB] Retrying in 5 seconds...")
                    await asyncio.sleep(5)
                else:
                    print("[DB - Error] All connection attempts failed. Shutting down.")
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