from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SUPPORTED_LANGS = {"pt", "en", "es"}
LOCALE_TO_LANG = {
    "pt": "pt",
    "pt-br": "pt",
    "pt-pt": "pt",
    "en": "en",
    "en-us": "en",
    "en-gb": "en",
    "es": "es",
    "es-es": "es",
    "es-mx": "es",
}


@dataclass(frozen=True)
class LanguageOption:
    code: str
    label: str


LANGUAGE_OPTIONS = [
    LanguageOption(code="pt", label="Portugues"),
    LanguageOption(code="en", label="English"),
    LanguageOption(code="es", label="Espanol"),
]


class I18nService:
    def __init__(self, default_lang: str = "pt"):
        self.default_lang = default_lang
        self._guild_cache: dict[int, str] = {}

    def _normalize(self, language_code: str | None) -> str:
        if not language_code:
            return self.default_lang

        normalized = language_code.strip().lower().replace("_", "-")
        if normalized in SUPPORTED_LANGS:
            return normalized

        if normalized in LOCALE_TO_LANG:
            return LOCALE_TO_LANG[normalized]

        short = normalized.split("-", maxsplit=1)[0]
        return LOCALE_TO_LANG.get(short, self.default_lang)

    def from_locale(self, locale: str | None) -> str:
        return self._normalize(locale)

    async def get_guild_language(self, pool: Any, guild_id: int | None) -> str:
        if guild_id is None:
            return self.default_lang

        if guild_id in self._guild_cache:
            return self._guild_cache[guild_id]

        row = await pool.fetchrow("SELECT language_code FROM guilds WHERE guild_id = $1", guild_id)
        lang = self._normalize(row["language_code"]) if row and row["language_code"] else self.default_lang
        self._guild_cache[guild_id] = lang
        return lang

    async def set_guild_language(self, pool: Any, guild_id: int, language_code: str) -> str:
        normalized = self._normalize(language_code)
        await pool.execute(
            """
            INSERT INTO guilds (guild_id, language_code)
            VALUES ($1, $2)
            ON CONFLICT (guild_id)
            DO UPDATE SET language_code = $2, updated_at = CURRENT_TIMESTAMP
            """,
            guild_id,
            normalized,
        )
        self._guild_cache[guild_id] = normalized
        return normalized

    async def language_for_interaction(self, bot: Any, interaction: Any) -> str:
        guild_id = interaction.guild.id if interaction.guild else None
        guild_lang = await self.get_guild_language(bot.pool, guild_id)
        if guild_lang in SUPPORTED_LANGS:
            return guild_lang

        return self.from_locale(str(interaction.locale) if interaction.locale else None)

    def t(self, translations: dict[str, str], lang: str, **kwargs: Any) -> str:
        template = translations.get(lang) or translations.get(self.default_lang) or next(iter(translations.values()))
        return template.format(**kwargs)
