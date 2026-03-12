from datetime import datetime, timedelta
import itertools
import re

import discord
from discord.ext import commands


def tr(lang: str, pt: str, en: str, es: str) -> str:
    return {"pt": pt, "en": en, "es": es}.get(lang, pt)


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_threshold = 5
        self.spam_cooldown = {}
        self.max_caps_ratio = 0.70
        self.max_emojis = 10
        self.invite_pattern = re.compile(r"discord\.gg/\w+|discordapp\.com/invite/\w+")
        self.emoji_pattern = re.compile(r"<a?:\w+:\d+>|[\U0001F600-\U0001F64F]|[\U0001F300-\U0001F5FF]|[\U0001F680-\U0001F6FF]|[\U0001F900-\U0001F9FF]|[\U0001FA70-\U0001FAFF]")

    async def _guild_lang(self, guild: discord.Guild | None) -> str:
        if guild is None:
            return "pt"
        return await self.bot.i18n.get_guild_language(self.bot.pool, guild.id)

    @commands.Cog.listener()
    async def on_ready(self):
        print("[DEBUG Events Cog] on_ready called")
        print(f"[EVENTS] Online: {self.bot.user}")

    async def _check_antiflood_enabled(self, guild_id: int) -> bool:
        async with self.bot.pool.acquire() as connection:
            result = await connection.fetchval("SELECT smart_antiflood FROM guilds WHERE guild_id = $1", guild_id)
            return result if result is not None else False

    async def _handle_automod_warn_limit(self, message: discord.Message):
        async with self.bot.pool.acquire() as connection:
            guild_settings = await connection.fetchrow(
                "SELECT auto_moderation, quant_warnings, acao FROM guilds WHERE guild_id = $1",
                message.guild.id,
            )
            if guild_settings is None or not guild_settings["auto_moderation"]:
                return

            warns = await connection.fetchrow(
                "SELECT warning_count FROM user_warnings WHERE user_id = $1 AND guild_id = $2",
                message.author.id,
                message.guild.id,
            )

            warning_count = warns["warning_count"] if warns else 0
            quant_warnings = guild_settings["quant_warnings"] or 3
            acao = (guild_settings["acao"] or "kick").lower()
            if warning_count < quant_warnings:
                return

            try:
                if acao == "kick":
                    await message.guild.kick(message.author, reason="Automod warn limit")
                    action_text = {"pt": "expulso(a)", "en": "kicked", "es": "expulsado(a)"}
                    color = discord.Color.orange()
                elif acao == "ban":
                    await message.guild.ban(message.author, reason="Automod warn limit", delete_message_days=0)
                    action_text = {"pt": "banido(a)", "en": "banned", "es": "baneado(a)"}
                    color = discord.Color.red()
                elif acao == "mute":
                    await message.author.timeout(discord.utils.utcnow() + timedelta(hours=1), reason="Automod warn limit")
                    action_text = {"pt": "silenciado(a)", "en": "timed out", "es": "silenciado(a)"}
                    color = discord.Color.yellow()
                else:
                    return

                await connection.execute(
                    "DELETE FROM user_warnings WHERE user_id = $1 AND guild_id = $2",
                    message.author.id,
                    message.guild.id,
                )

                lang = await self._guild_lang(message.guild)
                embed = discord.Embed(
                    title=tr(lang, "Limite de avisos atingido", "Warning limit reached", "Limite de avisos alcanzado"),
                    description=tr(
                        lang,
                        f"{message.author.mention} foi {action_text['pt']} por acumular avisos. Vamos manter tudo em paz por aqui.",
                        f"{message.author.mention} was {action_text['en']} for accumulating warnings. Let's keep things calm here.",
                        f"{message.author.mention} fue {action_text['es']} por acumular advertencias. Mantengamos el ambiente en calma.",
                    ),
                    color=color,
                    timestamp=datetime.utcnow(),
                )
                await message.channel.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass

    async def _handle_spam_messages(self, message: discord.Message):
        if not await self._check_antiflood_enabled(message.guild.id):
            return False

        lang = await self._guild_lang(message.guild)
        now = datetime.utcnow()
        key = (message.guild.id, message.author.id)

        timestamps = [ts for ts in self.spam_cooldown.get(key, []) if (now - ts).total_seconds() < 5]
        timestamps.append(now)
        self.spam_cooldown[key] = timestamps

        if self.invite_pattern.search(message.content):
            await message.channel.send(tr(lang, f"{message.author.mention}, convites nao sao permitidos aqui, ta bom?", f"{message.author.mention}, server invites are not allowed here, alright?", f"{message.author.mention}, las invitaciones no estan permitidas aqui, vale?"))
            return True

        if len(timestamps) > self.spam_threshold:
            await message.channel.send(tr(lang, f"{message.author.mention}, voce esta enviando mensagens muito rapido. Respira um pouquinho e tenta de novo.", f"{message.author.mention}, you are sending messages too fast. Take a breath and try again.", f"{message.author.mention}, estas enviando mensajes demasiado rapido. Respira un poquito e intenta otra vez."))
            return True

        return False

    async def _handle_message_quality(self, message: discord.Message):
        if not await self._check_antiflood_enabled(message.guild.id):
            return False

        lang = await self._guild_lang(message.guild)

        if len(message.content) > 10:
            caps_count = sum(1 for c in message.content if c.isupper())
            caps_ratio = caps_count / len(message.content)
            if caps_ratio > self.max_caps_ratio:
                await message.channel.send(tr(lang, f"{message.author.mention}, usa menos maiusculas para ficar mais facil de ler.", f"{message.author.mention}, please use less uppercase text so it is easier to read.", f"{message.author.mention}, usa menos mayusculas para que sea mas facil de leer."))
                return True

        if len(message.content) > 5:
            max_repeat = max([len(list(group)) for _, group in itertools.groupby(message.content)], default=0)
            if max_repeat > 10:
                await message.channel.send(tr(lang, f"{message.author.mention}, vamos evitar repeticoes exageradas, combinado?", f"{message.author.mention}, let's avoid excessive repetitions, okay?", f"{message.author.mention}, evitemos repeticiones excesivas, vale?"))
                return True

        emojis = self.emoji_pattern.findall(message.content)
        if len(emojis) > self.max_emojis:
            await message.channel.send(tr(lang, f"{message.author.mention}, muitos emojis de uma vez. Vamos dosar um pouquinho.", f"{message.author.mention}, too many emojis at once. Let's tone it down a bit.", f"{message.author.mention}, demasiados emojis de una vez. Vamos a bajarlo un poco."))
            return True

        mention_count = len(message.mentions) + len(message.role_mentions)
        if mention_count > 5:
            await message.channel.send(tr(lang, f"{message.author.mention}, evita mencionar muitas pessoas ao mesmo tempo, por favor.", f"{message.author.mention}, please avoid mentioning too many people at once.", f"{message.author.mention}, por favor evita mencionar a demasiadas personas al mismo tiempo."))
            return True

        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        await self._handle_automod_warn_limit(message)
        await self._handle_spam_messages(message)
        await self._handle_message_quality(message)

        await self.bot.process_commands(message)


async def setup(bot):
    print("[DEBUG] Carregando cog Events...")
    await bot.add_cog(Events(bot))
    print("[DEBUG] Cog Events carregado com sucesso!")
