# FINALMENTE ESSA PORCARIA VAI TER ECONOMIA!!!!!!!!!! AYRTON AYRTON AYRRRRRRRTOOOOOOON SENNA DO BRASIL!!!
# eu tenho que para com isso kk
import discord
from discord import app_commands
from discord.ext import commands
import random
from datetime import datetime, timedelta, timezone

from scripts.db import Database

def tr(lang: str, pt: str, en: str, es: str) -> str:
    return {"pt": pt, "en": en, "es": es}.get(lang, pt)

class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _db(self) -> Database:
        return Database(self.bot.pool)

    async def _ensure_account(self, user_id: int) -> None:
        db = self._db()
        await db.execute(
            """
            INSERT INTO economy (user_id, balance)
            VALUES ($1, 0)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
        )

    async def _fetch_balance(self, user_id: int) -> int:
        await self._ensure_account(user_id)
        db = self._db()
        balance = await db.fetchval("SELECT balance FROM economy WHERE user_id = $1", user_id)
        return int(balance or 0)

    async def _member_name_for_leaderboard(self, guild: discord.Guild | None, user_id: int) -> str:
        if guild is not None:
            member = guild.get_member(user_id)
            if member:
                return member.display_name
            try:
                member = await guild.fetch_member(user_id)
                return member.display_name
            except Exception:
                pass

        user = self.bot.get_user(user_id)
        if user:
            return user.name

        try:
            user = await self.bot.fetch_user(user_id)
            return user.name
        except Exception:
            return f"User ID {user_id}"
    
    async def _lang(self, interaction: discord.Interaction) -> str:
        return await self.bot.i18n.language_for_interaction(self.bot, interaction)
    
    @app_commands.command(name="balance", description="Mostra o saldo de Lumicoins do usuario")
    async def balance(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        dbalance = await self._fetch_balance(interaction.user.id)

        await interaction.response.send_message(
            tr(
                lang,
                f"Seu saldo atual é de **{dbalance} Lumicoins**.",
                f"Your current balance is **{dbalance} Lumicoins**.",
                f"Tu saldo actual es de **{dbalance} Lumicoins**.",
            ),
        )
    
    # Sugestão aleatória para o futuro:
    # Colocar no Front-End a Possibilidade de resgatar a recompensa diária, semanal e mensal, cada uma com uma chance diferente de raridade e valor diferente de recompensa, e um cooldown para cada uma delas (24h para diária, 7 dias para semanal e 30 dias para mensal)
    @app_commands.command(name="daily", description="Resgata sua recompensa diária de Lumicoins")
    async def daily(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        db = self._db()

        await self._ensure_account(interaction.user.id)
        row = await db.fetchrow(
            "SELECT balance, last_daily FROM economy WHERE user_id = $1",
            interaction.user.id,
        )

        last_daily = row["last_daily"] if row else None
        now = datetime.now(timezone.utc)
        cooldown = timedelta(hours=24)

        if last_daily is not None:
            last_daily_utc = last_daily.replace(tzinfo=timezone.utc) if last_daily.tzinfo is None else last_daily.astimezone(timezone.utc)
            remaining = (last_daily_utc + cooldown) - now
            if remaining.total_seconds() > 0:
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes = remainder // 60
                await interaction.response.send_message(
                    tr(
                        lang,
                        f"Você já resgatou sua recompensa diária. Tente novamente em **{hours}h {minutes}min**.",
                        f"You already claimed your daily reward. Try again in **{hours}h {minutes}m**.",
                        f"Ya reclamaste tu recompensa diaria. Inténtalo de nuevo en **{hours}h {minutes}min**.",
                    ),
                    ephemeral=True,
                )
                return

        rarity_options = [
            ("Comum", "Common", "Común", 1),
            ("Raro", "Rare", "Raro", 2),
            ("Épico", "Epic", "Épico", 5),
            ("Lendário", "Legendary", "Legendario", 10),
        ]
        rarity = random.choices(rarity_options, weights=[70, 20, 9, 1], k=1)[0]

        base_reward = 100
        reward = base_reward * rarity[3]

        new_balance = await db.fetchval(
            """
            UPDATE economy
            SET balance = balance + $1,
                last_daily = CURRENT_TIMESTAMP
            WHERE user_id = $2
            RETURNING balance
            """,
            reward,
            interaction.user.id,
        )

        rarity_label = tr(lang, rarity[0], rarity[1], rarity[2])
        embed = discord.Embed(
            title=tr(
                lang,
                "Recompensa Diária Resgatada!",
                "Daily Reward Claimed!",
                "¡Recompensa Diaria Reclamada!",
            ),
            description=tr(
                lang,
                f"Você resgatou uma recompensa **{rarity_label}** e ganhou **{reward} Lumicoins**!\nSaldo atual: **{new_balance} Lumicoins**.",
                f"You claimed a **{rarity_label}** reward and earned **{reward} Lumicoins**!\nCurrent balance: **{new_balance} Lumicoins**.",
                f"¡Has reclamado una recompensa **{rarity_label}** y ganado **{reward} Lumicoins**!\nSaldo actual: **{new_balance} Lumicoins**.",
            ),
            color=discord.Color.gold(),
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="transfer", description="Transfere Lumicoins para outro usuário")
    async def transfer(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        class ConfirmTransferView(discord.ui.View):
            def __init__(self, author_id: int, timeout=30):
                super().__init__(timeout=timeout)
                self.value = None
                self.author_id = author_id

            @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.green)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.author_id:
                    await interaction.response.send_message("Você não pode confirmar esta transferência.", ephemeral=True)
                    return
                await interaction.response.defer()
                self.value = True
                self.stop()

            @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.red)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.author_id:
                    await interaction.response.send_message("Você não pode cancelar esta transferência.", ephemeral=True)
                    return
                await interaction.response.defer()
                self.value = False
                self.stop()

        lang = await self._lang(interaction)
        db = self._db()

        if amount <= 0:
            await interaction.response.send_message(
                tr(
                    lang,
                    "O valor da transferência deve ser maior que zero.",
                    "Transfer amount must be greater than zero.",
                    "La cantidad de transferencia debe ser mayor que cero.",
                ),
                ephemeral=True,
            )
            return

        if member.id == interaction.user.id:
            await interaction.response.send_message(
                tr(
                    lang,
                    "Você não pode transferir para si mesmo.",
                    "You cannot transfer to yourself.",
                    "No puedes transferirte a ti mismo.",
                ),
                ephemeral=True,
            )
            return

        if member.bot:
            await interaction.response.send_message(
                tr(
                    lang,
                    "Você não pode transferir para bots.",
                    "You cannot transfer to bots.",
                    "No puedes transferir a bots.",
                ),
                ephemeral=True,
            )
            return

        await self._ensure_account(interaction.user.id)
        await self._ensure_account(member.id)

        sender_balance = await db.fetchval("SELECT balance FROM economy WHERE user_id = $1", interaction.user.id)

        if sender_balance < amount:
            await interaction.response.send_message(
                tr(
                    lang,
                    "Você não tem saldo suficiente para essa transferência.",
                    "You do not have enough balance for this transfer.",
                    "No tienes suficiente saldo para esta transferencia.",
                ),
                ephemeral=True,
            )
            return

        view = ConfirmTransferView(author_id=interaction.user.id)
        await interaction.response.send_message(
            tr(
                lang,
                f"Você está prestes a transferir **{amount} Lumicoins** para {member.mention}. Deseja confirmar?",
                f"You are about to transfer **{amount} Lumicoins** to {member.mention}. Do you want to confirm?",
                f"Estás a punto de transferir **{amount} Lumicoins** a {member.mention}. ¿Deseas confirmar?",
            ),
            view=view,
            ephemeral=True,
        )

        await view.wait()

        if view.value is None:
            await interaction.followup.send(
                tr(
                    lang,
                    "Tempo esgotado. A transferência foi cancelada.",
                    "Time's up. The transfer has been cancelled.",
                    "Se acabó el tiempo. La transferencia ha sido cancelada.",
                ),
                ephemeral=True,
            )
            return

        if not view.value:
            await interaction.followup.send(
                tr(
                    lang,
                    "A transferência foi cancelada.",
                    "The transfer has been cancelled.",
                    "La transferencia ha sido cancelada.",
                ),
                ephemeral=True,
            )
            return

        async with self.bot.pool.acquire() as connection:
            async with connection.transaction():
                sender_row = await connection.fetchrow(
                    """
                    UPDATE economy
                    SET balance = balance - $1
                    WHERE user_id = $2 AND balance >= $1
                    RETURNING balance
                    """,
                    amount,
                    interaction.user.id,
                )

                if sender_row is None:
                    await interaction.followup.send(
                        tr(
                            lang,
                            "Seu saldo mudou durante a confirmação e ficou insuficiente.",
                            "Your balance changed during confirmation and is now insufficient.",
                            "Tu saldo cambió durante la confirmación y ahora es insuficiente.",
                        ),
                        ephemeral=True,
                    )
                    return

                recipient_row = await connection.fetchrow(
                    """
                    UPDATE economy
                    SET balance = balance + $1
                    WHERE user_id = $2
                    RETURNING balance
                    """,
                    amount,
                    member.id,
                )

        new_sender_balance = sender_row["balance"]
        new_recipient_balance = recipient_row["balance"] if recipient_row else 0

        await interaction.followup.send(
            tr(
                lang,
                f"Você transferiu **{amount} Lumicoins** para {member.mention}. Seu novo saldo é **{new_sender_balance} Lumicoins**.\nSaldo de {member.mention}: **{new_recipient_balance} Lumicoins**.",
                f"You transferred **{amount} Lumicoins** to {member.mention}. Your new balance is **{new_sender_balance} Lumicoins**.\n{member.mention}'s balance: **{new_recipient_balance} Lumicoins**.",
                f"Has transferido **{amount} Lumicoins** a {member.mention}. Tu nuevo saldo es **{new_sender_balance} Lumicoins**.\nSaldo de {member.mention}: **{new_recipient_balance} Lumicoins**.",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="leaderboard", description="Mostra a leaderboard de Lumicoins do servidor ou globalmente.")
    async def leaderboard(self, interaction: discord.Interaction, scope: str = "server"):
        lang = await self._lang(interaction)
        db = self._db()

        if scope not in {"server", "global"}:
            await interaction.response.send_message(
                tr(
                    lang,
                    "Escopo inválido. Use `server` ou `global`.",
                    "Invalid scope. Use `server` or `global`.",
                    "Ámbito inválido. Usa `server` o `global`.",
                ),
                ephemeral=True,
            )
            return

        if scope == "server":
            rows = await db.fetch(
                """
                SELECT user_id, balance
                FROM economy
                ORDER BY balance DESC
                LIMIT 100
                """,
            )
            server_rows = []
            for row in rows:
                if interaction.guild is None:
                    break

                member = interaction.guild.get_member(row["user_id"])
                if member is None:
                    try:
                        member = await interaction.guild.fetch_member(row["user_id"])
                    except Exception:
                        member = None

                if member is not None:
                    server_rows.append(row)
                if len(server_rows) >= 10:
                    break
            rows = server_rows
            title = tr(
                lang,
                "Leaderboard de Lumicoins - Servidor",
                "Lumicoins Leaderboard - Server",
                "Tabla de Clasificación de Lumicoins - Servidor",
            )
        else:
            rows = await db.fetch(
                """
                SELECT user_id, balance
                FROM economy
                ORDER BY balance DESC
                LIMIT 10
                """,
            )
            title = tr(
                lang,
                "Leaderboard de Lumicoins - Global",
                "Lumicoins Leaderboard - Global",
                "Tabla de Clasificación de Lumicoins - Global",
            )

        if not rows:
            await interaction.response.send_message(
                tr(
                    lang,
                    "Ainda não há dados suficientes para montar a leaderboard.",
                    "There is not enough data to build the leaderboard yet.",
                    "Aún no hay datos suficientes para mostrar la clasificación.",
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(title=title, color=discord.Color.blue())
        for i, row in enumerate(rows, start=1):
            username = await self._member_name_for_leaderboard(interaction.guild if scope == "server" else None, row["user_id"])
            embed.add_field(name=f"{i}. {username}", value=f"{row['balance']} Lumicoins", inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
