from discord import app_commands
import discord
from discord.ext import commands

CRIADOR_ID = 947849382278094880  # coloca seu ID aqui

class Memes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="criador", description="Descubra quem criou o bot")
    async def criador(self, interaction: discord.Interaction):
        lang = await self.bot.i18n.language_for_interaction(self.bot, interaction)
        texts = {
            "pt": {
                "creator": "Ola Pai, tudo bem? Sinto falta de um update...",
                "shelly": "Ola Sellly, tudo bem? Te amo muito!",
                "other": "Error 401: Meu criador e o Milky, nao voce!",
            },
            "en": {
                "creator": "Hi Boss, I miss the next update...",
                "shelly": "Hi Sellly, sending lots of love!",
                "other": "Error 401: My creator is Milky, not you!",
            },
            "es": {
                "creator": "Hola Jefe, ya extrano la proxima actualizacion...",
                "shelly": "Hola Sellly, te quiero mucho!",
                "other": "Error 401: Mi creador es Milky, no tu!",
            },
        }
        msg = texts[lang]

        if interaction.user.id == CRIADOR_ID:
            await interaction.response.send_message(msg["creator"])
        elif interaction.user.id == 928433630093656154:
            await interaction.response.send_message(msg["shelly"])
        else:
            await interaction.response.send_message(msg["other"])


async def setup(bot):
    await bot.add_cog(Memes(bot))