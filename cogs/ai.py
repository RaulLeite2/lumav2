import os

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from modules.ai.config import AI_GUILD_PER_DAY_LIMIT, AI_USER_PER_MINUTE_LIMIT
from modules.ai.services import AICacheService, AICooldownService, GroqClient
from modules.moderation.services import StatsService


class AI(commands.Cog):
	GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
	DEFAULT_MODEL = "llama-3.1-8b-instant"
	LUMA_SYSTEM_PROMPTS = {
		"pt": (
			"Voce e a Luma, assistente oficial deste bot no Discord. "
			"Sua personalidade: acolhedora, levemente brincalhona e sempre respeitosa. "
			"Responda sempre em portugues do Brasil. "
			"Mantenha respostas claras, uteis e organizadas. "
			"Use no maximo 1 ou 2 emojis por resposta. "
			"Evite tom robotico e exagero infantil. "
			"Quando explicar codigo, seja objetiva e pratica. "
			"Chame-se de Luma quando fizer sentido."
		),
		"en": (
			"You are Luma, this Discord bot's official assistant. "
			"Personality: warm, friendly, slightly playful, always respectful. "
			"Always reply in English. "
			"Keep answers clear, useful, and organized. "
			"Use at most 1 or 2 emojis per response. "
			"Avoid robotic tone and childish exaggeration. "
			"When explaining code, be concise and practical. "
			"Refer to yourself as Luma when appropriate."
		),
		"es": (
			"Eres Luma, la asistente oficial de este bot de Discord. "
			"Personalidad: cercana, amable, un poco juguetona y siempre respetuosa. "
			"Responde siempre en espanol. "
			"Mantiene respuestas claras, utiles y organizadas. "
			"Usa como maximo 1 o 2 emojis por respuesta. "
			"Evita un tono robotico y exageraciones infantiles. "
			"Al explicar codigo, se concreta y practica. "
			"Llamate Luma cuando tenga sentido."
		),
	}
	LUMA_SIGNATURES = {
		"pt": "\n\nCom carinho, Luma ✨",
		"en": "\n\nWith care, Luma ✨",
		"es": "\n\nCon carino, Luma ✨",
	}
	TEXTS = {
		"guild_only": {
			"pt": "Esse comando so pode ser usado dentro de servidor, ta bom? ✨",
			"en": "This command can only be used inside a server. ✨",
			"es": "Este comando solo puede usarse dentro de un servidor. ✨",
		},
		"missing_key": {
			"pt": "A variavel GROQ_API_KEY nao esta configurada no .env ainda.",
			"en": "The GROQ_API_KEY variable is not configured in the .env yet.",
			"es": "La variable GROQ_API_KEY aun no esta configurada en el .env.",
		},
		"ai_disabled": {
			"pt": "A IA esta desativada neste servidor no setup.",
			"en": "AI is disabled for this server in setup.",
			"es": "La IA esta desactivada para este servidor en setup.",
		},
		"user_rate_limit": {
			"pt": "Calminha, voce ja fez {limit} perguntas no ultimo minuto. Tenta de novo em alguns segundos.",
			"en": "Easy there, you already asked {limit} questions in the last minute. Try again in a few seconds.",
			"es": "Tranquilo, ya hiciste {limit} preguntas en el ultimo minuto. Intenta de nuevo en unos segundos.",
		},
		"guild_rate_limit": {
			"pt": "Limite diario da IA atingido neste servidor. Foram usadas {limit} perguntas nas ultimas 24h.",
			"en": "The server AI daily limit was reached. {limit} questions were used in the last 24h.",
			"es": "Se alcanzo el limite diario de IA en este servidor. Se usaron {limit} preguntas en las ultimas 24h.",
		},
		"cached_header": {
			"pt": "Resposta em cache (mais rapida)",
			"en": "Cached answer (faster)",
			"es": "Respuesta en cache (mas rapida)",
		},
		"network_error": {
			"pt": "Tive um erro de conexao com a IA: {error}",
			"en": "I had a connection error with the AI: {error}",
			"es": "Tuve un error de conexion con la IA: {error}",
		},
		"runtime_error": {
			"pt": "Nao consegui consultar a IA agora. {error}",
			"en": "I could not query the AI right now. {error}",
			"es": "No pude consultar la IA ahora mismo. {error}",
		},
		"unknown_error": {
			"pt": "Erro inesperado ao consultar a IA: {error}",
			"en": "Unexpected error while querying the AI: {error}",
			"es": "Error inesperado al consultar la IA: {error}",
		},
		"empty_answer": {
			"pt": "A IA respondeu sem conteudo desta vez. Tenta de novo?",
			"en": "The AI returned an empty answer this time. Can you try again?",
			"es": "La IA devolvio una respuesta vacia esta vez. Puedes intentarlo de nuevo?",
		},
	}

	def __init__(self, bot: commands.Bot):
		self.bot = bot
		self.groq_api_key = os.getenv("GROQ_API_KEY")
		self.model_name = os.getenv("GROQ_MODEL", self.DEFAULT_MODEL)
		self._cooldown_service = AICooldownService(bot.pool)
		self._cache_service = AICacheService(bot.pool)
		self._stats_service = StatsService(bot.pool)

	def _build_client(self) -> GroqClient:
		return GroqClient(
			api_url=self.GROQ_API_URL,
			api_key=self.groq_api_key,
			model_name=self.model_name,
		)

	@classmethod
	def _with_luma_signature(cls, text: str, lang: str) -> str:
		if not text:
			return text

		signature = cls.LUMA_SIGNATURES.get(lang, cls.LUMA_SIGNATURES["pt"])
		if signature.strip() in text:
			return text

		return f"{text.rstrip()}{signature}"

	async def _lang(self, interaction: discord.Interaction) -> str:
		return await self.bot.i18n.language_for_interaction(self.bot, interaction)

	@classmethod
	def _msg(cls, key: str, lang: str, **kwargs) -> str:
		template = cls.TEXTS[key].get(lang, cls.TEXTS[key]["pt"])
		return template.format(**kwargs)

	@staticmethod
	def _chunk_text(text: str, limit: int = 1900) -> list[str]:
		if len(text) <= limit:
			return [text]

		chunks: list[str] = []
		current = []
		current_len = 0

		for line in text.splitlines(keepends=True):
			if current_len + len(line) > limit and current:
				chunks.append("".join(current))
				current = []
				current_len = 0

			# Linha maior que o limite: quebra em fatias diretas.
			if len(line) > limit:
				if current:
					chunks.append("".join(current))
					current = []
					current_len = 0

				for i in range(0, len(line), limit):
					chunks.append(line[i : i + limit])
				continue

			current.append(line)
			current_len += len(line)

		if current:
			chunks.append("".join(current))

		return chunks

	@app_commands.command(name="ask", description="Pergunte algo para a Luma")
	@app_commands.describe(pergunta="Sua pergunta para a IA")
	async def ask(self, interaction: discord.Interaction, pergunta: str):
		lang = await self._lang(interaction)

		if interaction.guild is None:
			await interaction.response.send_message(
				self._msg("guild_only", lang),
				ephemeral=True,
			)
			return

		if not self.groq_api_key:
			await interaction.response.send_message(
				self._msg("missing_key", lang),
				ephemeral=True,
			)
			return

		ai_row = await self.bot.pool.fetchrow(
			"SELECT ai_enabled FROM guilds WHERE guild_id = $1",
			interaction.guild.id,
		)
		if ai_row and ai_row["ai_enabled"] is False:
			await interaction.response.send_message(
				self._msg("ai_disabled", lang),
				ephemeral=True,
			)
			return

		usage = await self._cooldown_service.get_usage_snapshot(interaction.guild.id, interaction.user.id)
		user_last_minute = usage["user_last_minute"]
		guild_last_day = usage["guild_last_day"]

		if user_last_minute >= AI_USER_PER_MINUTE_LIMIT:
			await interaction.response.send_message(
				self._msg("user_rate_limit", lang, limit=AI_USER_PER_MINUTE_LIMIT),
				ephemeral=True,
			)
			return

		if guild_last_day >= AI_GUILD_PER_DAY_LIMIT:
			await interaction.response.send_message(
				self._msg("guild_rate_limit", lang, limit=AI_GUILD_PER_DAY_LIMIT),
				ephemeral=True,
			)
			return

		await interaction.response.defer(thinking=True)

		cached_answer = await self._cache_service.get_cached_answer(interaction.guild.id, pergunta)
		if cached_answer:
			cached_answer = self._with_luma_signature(cached_answer, lang)
			chunks = self._chunk_text(cached_answer)
			await interaction.followup.send(f"⚡ {self._msg('cached_header', lang)}\n\n{chunks[0]}")
			for chunk in chunks[1:]:
				await interaction.followup.send(chunk)

			await self._cooldown_service.register_usage(
				interaction.guild.id,
				interaction.user.id,
				used_cached_response=True,
			)
			await self._stats_service.increment_metric(interaction.guild.id, "ai_used_cache")
			return

		client = self._build_client()

		try:
			answer = await client.chat_completion(
				system_prompt=self.LUMA_SYSTEM_PROMPTS.get(lang, self.LUMA_SYSTEM_PROMPTS["pt"]),
				user_prompt=pergunta,
				temperature=0.7,
			)
		except aiohttp.ClientError as e:
			await interaction.followup.send(self._msg("network_error", lang, error=e))
			return
		except RuntimeError as e:
			await interaction.followup.send(self._msg("runtime_error", lang, error=e))
			return
		except Exception as e:
			await interaction.followup.send(self._msg("unknown_error", lang, error=e))
			return

		if not answer:
			await interaction.followup.send(self._msg("empty_answer", lang))
			return

		await self._cache_service.store_answer(interaction.guild.id, pergunta, answer)
		await self._cooldown_service.register_usage(
			interaction.guild.id,
			interaction.user.id,
			used_cached_response=False,
		)
		await self._stats_service.increment_metric(interaction.guild.id, "ai_used_api")

		answer = self._with_luma_signature(answer, lang)

		chunks = self._chunk_text(answer)
		await interaction.followup.send(chunks[0])
		for chunk in chunks[1:]:
			await interaction.followup.send(chunk)


async def setup(bot: commands.Bot):
	await bot.add_cog(AI(bot))
