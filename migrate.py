"""
Migration runner for Luma bot
Executes all SQL migration files in the migrations/ directory
"""

import asyncio
import asyncpg
import os
from pathlib import Path

async def run_migrations(pool: asyncpg.Pool):
    """
    Execute all migration SQL files in order
    Files are processed alphabetically by filename
    """
    migrations_dir = Path(__file__).parent / "migrations"
    
    if not migrations_dir.exists():
        print(f"❌ Migrations directory not found: {migrations_dir}")
        return
    
    migration_files = sorted(migrations_dir.glob("*.sql"))
    
    if not migration_files:
        print("⚠️  No migration files found in migrations/")
        return
    
    async with pool.acquire() as conn:
        for migration_file in migration_files:
            try:
                with open(migration_file, 'r', encoding='utf-8') as f:
                    sql_content = f.read()
                
                # Execute the migration
                await conn.execute(sql_content)
                print(f"✅ Migration executed: {migration_file.name}")
                
            except Exception as e:
                print(f"❌ Error executing migration {migration_file.name}: {e}")
                raise

async def main():
    """
    Example usage - connect to PostgreSQL and run migrations
    Adjust DATABASE_URL to your configuration
    """
    DATABASE_URL = "postgresql://user:password@localhost/luma_bot"
    
    try:
        pool = await asyncpg.create_pool(DATABASE_URL)
        print("🔄 Starting migrations...")
        await run_migrations(pool)
        print("✅ All migrations completed successfully!")
        await pool.close()
    except Exception as e:
        print(f"❌ Migration process failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
