import asyncpg
import os

async def connect_db():
    pool = await asyncpg.create_pool(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        port=int(os.getenv("DB_PORT", "5432"))
    )
    return pool

class Database:
    def __init__(self, pool):
        self.pool = pool
    
    async def execute(self, query, *args):
        async with self.pool.acquire() as connection:
            await connection.execute(query, *args)
    
    async def fetch(self, query, *args):
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)
    
    async def fetchrow(self, query, *args):
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, *args)
    
    async def fetchval(self, query, *args):
        async with self.pool.acquire() as connection:
            return await connection.fetchval(query, *args)
    
    async def transaction(self):
        return self.pool.transaction()
    
    async def executemany(self, query, args_list):
        async with self.pool.acquire() as connection:
            await connection.executemany(query, args_list)