from __future__ import annotations

import logging
import os
import time
import traceback
from typing import Any

import discord

logger = logging.getLogger(__name__)


class OwnerAlertService:
    """Sends runtime error diagnostics to a configured Discord user via DM."""

    DEFAULT_OWNER_ID = 947849382278094880

    def __init__(self, bot: Any):
        self.bot = bot
        configured_id = os.getenv("OWNER_ALERT_USER_ID", "").strip()
        self.owner_user_id = int(configured_id) if configured_id.isdigit() else self.DEFAULT_OWNER_ID
        self.enabled = os.getenv("OWNER_ALERTS_ENABLED", "true").strip().lower() not in {"0", "false", "no"}
        self._last_sent_at = 0.0
        self._cooldown_seconds = int(os.getenv("OWNER_ALERT_COOLDOWN_SECONDS", "20"))

    async def notify_error(self, title: str, error: BaseException, context: str | None = None) -> None:
        logger.exception("%s: %s", title, error)

        if not self.enabled:
            return

        now = time.monotonic()
        if now - self._last_sent_at < self._cooldown_seconds:
            logger.warning("Owner alert suppressed by cooldown: %s", title)
            return

        self._last_sent_at = now

        user = self.bot.get_user(self.owner_user_id)
        if user is None:
            try:
                user = await self.bot.fetch_user(self.owner_user_id)
            except Exception:
                logger.exception("Could not resolve owner user for alerting")
                return

        if user is None:
            logger.warning("Owner user not found for alerting: %s", self.owner_user_id)
            return

        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        tb = tb[-3500:] if tb else "No traceback available"

        embed = discord.Embed(
            title=f"[Luma] Runtime error: {title[:180]}",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        if context:
            embed.add_field(name="Context", value=context[:1000], inline=False)

        # Keep traceback in a code block and trim to Discord field limits.
        embed.add_field(name="Traceback", value=f"```py\n{tb[:980]}\n```", inline=False)

        try:
            await user.send(embed=embed)
        except Exception:
            logger.exception("Failed to DM owner error alert")
