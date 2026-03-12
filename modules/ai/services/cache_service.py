from __future__ import annotations

import re
import asyncpg

from modules.ai.config import AI_CACHE_MAX_QUESTION_KEY, AI_CACHE_MIN_QUESTION_LENGTH


class AICacheService:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    @staticmethod
    def normalize_question(text: str) -> str:
        normalized = re.sub(r"\s+", " ", text.lower().strip())
        normalized = re.sub(r"[^a-z0-9à-ÿç ?!.,-]", "", normalized)
        return normalized[:AI_CACHE_MAX_QUESTION_KEY]

    async def get_cached_answer(self, guild_id: int, question: str) -> str | None:
        question_key = self.normalize_question(question)
        if len(question_key) < AI_CACHE_MIN_QUESTION_LENGTH:
            return None

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, answer
                FROM ai_response_cache
                WHERE guild_id = $1 AND question_key = $2
                """,
                guild_id,
                question_key,
            )

            if not row:
                return None

            await conn.execute(
                """
                UPDATE ai_response_cache
                SET hits = hits + 1,
                    last_hit_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                row["id"],
            )

        return row["answer"]

    async def store_answer(self, guild_id: int, question: str, answer: str) -> None:
        question_key = self.normalize_question(question)
        if len(question_key) < AI_CACHE_MIN_QUESTION_LENGTH:
            return

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO ai_response_cache (guild_id, question_key, original_question, answer, hits)
                VALUES ($1, $2, $3, $4, 0)
                ON CONFLICT (guild_id, question_key)
                DO UPDATE SET
                    answer = EXCLUDED.answer,
                    original_question = EXCLUDED.original_question,
                    updated_at = CURRENT_TIMESTAMP
                """,
                guild_id,
                question_key,
                question,
                answer,
            )
