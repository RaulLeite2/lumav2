import datetime
import random

import discord
from discord import app_commands
from discord.ext import commands

from scripts.db import Database

TERRITORY_LEAGUES = [
    ("Celestial", 1000),
    ("Eclipse", 550),
    ("Tempestade", 220),
    ("Abismo", 0),
]

UPGRADE_TIERS = {
    "1": {"cost": 200, "defense": 1},
    "2": {"cost": 500, "defense": 3},
    "3": {"cost": 1000, "defense": 5},
}


def territory_score(owned_count: int, total_defense: int, reward_rate: int, conquest_pot: int) -> int:
    return (owned_count * 180) + (total_defense * 35) + (reward_rate * 4) + (conquest_pot // 10)


def league_for_score(score: int) -> str:
    for league_name, minimum_score in TERRITORY_LEAGUES:
        if score >= minimum_score:
            return league_name
    return "Abismo"


def format_owner(guild: discord.Guild | None, owner_id: int | None) -> str:
    if not owner_id:
        return "Sem dono"
    if guild:
        member = guild.get_member(owner_id)
        if member:
            return member.mention
    return f"<@{owner_id}>"


class UpgradeView(discord.ui.View):
    def __init__(self, cog: "Territories", territory_id: int, territory_name: str, current_defense: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.territory_id = territory_id
        self.territory_name = territory_name
        self.current_defense = current_defense

    @discord.ui.select(
        placeholder="Selecione um upgrade",
        options=[
            discord.SelectOption(label="Taxa 1", description="+1 defesa por 200 Luma Coins", value="1"),
            discord.SelectOption(label="Taxa 2", description="+3 defesa por 500 Luma Coins", value="2"),
            discord.SelectOption(label="Taxa 3", description="+5 defesa por 1000 Luma Coins", value="3"),
        ],
    )
    async def select_upgrade(self, interaction: discord.Interaction, select: discord.ui.Select):
        tier = UPGRADE_TIERS[select.values[0]]
        database = self.cog._db()
        territory = await self.cog._get_territory(self.territory_id)
        if not territory:
            await interaction.response.send_message("Território não encontrado.", ephemeral=True)
            return
        if territory["owner_id"] != interaction.user.id:
            await interaction.response.send_message("Você não é o dono desse território.", ephemeral=True)
            return
        if int(territory["defense_level"] or 1) >= 5:
            await interaction.response.send_message("Esse território já está no nível máximo.", ephemeral=True)
            return

        economy = await self.cog._ensure_economy(interaction.user.id)
        if int(economy["balance"] or 0) < int(tier["cost"]):
            await interaction.response.send_message(
                f"Saldo insuficiente. Você precisa de {tier['cost']} Luma Coins.",
                ephemeral=True,
            )
            return

        new_balance = await database.fetchval(
            """
            UPDATE economy
            SET balance = balance - $1,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $2
            RETURNING balance
            """,
            int(tier["cost"]),
            interaction.user.id,
        )
        new_defense = await database.fetchval(
            """
            UPDATE territories
            SET defense_level = LEAST(defense_level + $1, 5)
            WHERE id = $2
            RETURNING defense_level
            """,
            int(tier["defense"]),
            self.territory_id,
        )

        embed = discord.Embed(
            title="⚙️ Upgrade aplicado",
            description=f"A defesa de **{self.territory_name}** agora está no nível **{int(new_defense or 1)}**.",
            color=discord.Color.purple(),
        )
        embed.add_field(name="Custo", value=f"{tier['cost']} Luma Coins", inline=True)
        embed.add_field(name="Novo saldo", value=f"{int(new_balance or 0)}", inline=True)
        await interaction.response.send_message(embed=embed)
        self.stop()


class Territories(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _db(self) -> Database:
        return Database(self.bot.pool)

    async def _get_territory(self, territory_id: int):
        return await self._db().fetchrow("SELECT * FROM territories WHERE id = $1", territory_id)

    async def _ensure_economy(self, user_id: int):
        database = self._db()
        economy = await database.fetchrow("SELECT * FROM economy WHERE user_id = $1", user_id)
        if not economy:
            await database.execute(
                "INSERT INTO economy (user_id, balance) VALUES ($1, 0) ON CONFLICT (user_id) DO NOTHING",
                user_id,
            )
            economy = await database.fetchrow("SELECT * FROM economy WHERE user_id = $1", user_id)
        return economy

    terri = app_commands.Group(name="territories", description="Comandos relacionados a territórios")

    @terri.command(name="list", description="Lista todos os territórios disponíveis")
    async def list_territories(self, interaction: discord.Interaction):
        await interaction.response.defer()
        territories = await self._db().fetch("SELECT * FROM territories ORDER BY id ASC")
        if not territories:
            await interaction.followup.send("Nenhum território encontrado.")
            return

        embed = discord.Embed(title="🗺️ Territórios", color=discord.Color.blue())
        for territory in territories:
            owner = format_owner(interaction.guild, territory["owner_id"])
            embed.add_field(
                name=f"#{territory['id']} • {territory['name']}",
                value=(
                    f"Dono: {owner}\n"
                    f"Defesa: {int(territory['defense_level'] or 1)}/5\n"
                    f"Prêmio: {int(territory['luma_coins'] or 100)} coins"
                ),
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    @terri.command(name="mine", description="Mostra os territórios que você possui")
    async def my_territories(self, interaction: discord.Interaction):
        await interaction.response.defer()
        territories = await self._db().fetch(
            "SELECT * FROM territories WHERE owner_id = $1 ORDER BY id ASC",
            interaction.user.id,
        )
        if not territories:
            await interaction.followup.send("Você ainda não possui territórios.")
            return

        total_defense = sum(int(territory["defense_level"] or 1) for territory in territories)
        reward_rate = sum(int(territory["owner_reward_coins"] or 25) for territory in territories)
        conquest_pot = sum(int(territory["luma_coins"] or 100) for territory in territories)
        score = territory_score(len(territories), total_defense, reward_rate, conquest_pot)
        league = league_for_score(score)

        embed = discord.Embed(title="🏰 Seus Territórios", color=discord.Color.gold())
        embed.description = f"Liga atual: **{league}** • Score: **{score}**"
        for territory in territories:
            embed.add_field(
                name=f"#{territory['id']} • {territory['name']}",
                value=(
                    f"Defesa: {int(territory['defense_level'] or 1)}/5\n"
                    f"Coleta: {int(territory['owner_reward_coins'] or 25)} coins/h"
                ),
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    @terri.command(name="info", description="Mostra informações de um território")
    @app_commands.describe(territory_id="ID do território")
    async def info_territory(self, interaction: discord.Interaction, territory_id: int):
        await interaction.response.defer()
        territory = await self._get_territory(territory_id)
        if not territory:
            await interaction.followup.send("Território não encontrado.")
            return

        score = territory_score(
            1 if territory["owner_id"] else 0,
            int(territory["defense_level"] or 1),
            int(territory["owner_reward_coins"] or 25),
            int(territory["luma_coins"] or 100),
        ) if territory["owner_id"] else 0
        league = league_for_score(score)

        embed = discord.Embed(title=f"🏯 {territory['name']}", color=discord.Color.green())
        embed.add_field(name="ID", value=str(territory["id"]), inline=True)
        embed.add_field(name="Dono", value=format_owner(interaction.guild, territory["owner_id"]), inline=True)
        embed.add_field(name="Defesa", value=f"{int(territory['defense_level'] or 1)}/5", inline=True)
        embed.add_field(name="Prêmio de conquista", value=f"{int(territory['luma_coins'] or 100)}", inline=True)
        embed.add_field(name="Coleta por hora", value=f"{int(territory['owner_reward_coins'] or 25)}", inline=True)
        embed.add_field(name="Liga", value=league if territory["owner_id"] else "Abismo", inline=True)
        await interaction.followup.send(embed=embed)

    @terri.command(name="claim", description="Reivindica um território sem dono")
    @app_commands.describe(territory_id="ID do território")
    async def claim_territory(self, interaction: discord.Interaction, territory_id: int):
        await interaction.response.defer()
        territory = await self._get_territory(territory_id)
        if not territory:
            await interaction.followup.send("Território não encontrado.")
            return
        if territory["owner_id"]:
            await interaction.followup.send("Esse território já possui dono. Ataque para tentar conquistá-lo.")
            return

        claim_cost = 50
        economy = await self._ensure_economy(interaction.user.id)
        if int(economy["balance"] or 0) < claim_cost:
            await interaction.followup.send(f"Você precisa de {claim_cost} Luma Coins para reivindicar esse território.")
            return

        new_balance = await self._db().fetchval(
            """
            UPDATE economy
            SET balance = balance - $1,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $2
            RETURNING balance
            """,
            claim_cost,
            interaction.user.id,
        )
        await self._db().execute(
            "UPDATE territories SET owner_id = $1, called_at = CURRENT_TIMESTAMP WHERE id = $2",
            interaction.user.id,
            territory_id,
        )

        embed = discord.Embed(title="✅ Território reivindicado", color=discord.Color.green())
        embed.description = f"Você agora controla **{territory['name']}**."
        embed.add_field(name="Saldo restante", value=str(int(new_balance or 0)), inline=True)
        await interaction.followup.send(embed=embed)

    @terri.command(name="collect", description="Coleta a recompensa do seu território")
    @app_commands.describe(territory_id="ID do território")
    async def collect_territory(self, interaction: discord.Interaction, territory_id: int):
        await interaction.response.defer()
        territory = await self._get_territory(territory_id)
        if not territory:
            await interaction.followup.send("Território não encontrado.")
            return
        if territory["owner_id"] != interaction.user.id:
            await interaction.followup.send("Você só pode coletar de territórios seus.")
            return

        cooldown_seconds = 3600
        called_at = territory["called_at"]
        if called_at:
            called_at_utc = called_at.replace(tzinfo=datetime.timezone.utc) if called_at.tzinfo is None else called_at
            remaining = cooldown_seconds - int((datetime.datetime.now(datetime.timezone.utc) - called_at_utc).total_seconds())
            if remaining > 0:
                minutes, seconds = divmod(remaining, 60)
                await interaction.followup.send(f"Coleta em cooldown. Aguarde {minutes}m {seconds}s.")
                return

        reward = int(territory["owner_reward_coins"] or 25)
        new_balance = await self._db().fetchval(
            """
            UPDATE economy
            SET balance = balance + $1,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $2
            RETURNING balance
            """,
            reward,
            interaction.user.id,
        )
        await self._db().execute("UPDATE territories SET called_at = CURRENT_TIMESTAMP WHERE id = $1", territory_id)

        embed = discord.Embed(title="💰 Recompensa coletada", color=discord.Color.gold())
        embed.description = f"Você recebeu **{reward}** Luma Coins de **{territory['name']}**."
        embed.add_field(name="Saldo atual", value=str(int(new_balance or 0)), inline=True)
        await interaction.followup.send(embed=embed)

    @terri.command(name="attack", description="Ataca um território inimigo")
    @app_commands.describe(territory_id="ID do território")
    async def attack_territory(self, interaction: discord.Interaction, territory_id: int):
        await interaction.response.defer()
        territory = await self._get_territory(territory_id)
        if not territory:
            await interaction.followup.send("Território não encontrado.")
            return
        if territory["owner_id"] == interaction.user.id:
            await interaction.followup.send("Você não pode atacar seu próprio território.")
            return

        attack_cost = 100
        economy = await self._ensure_economy(interaction.user.id)
        if int(economy["balance"] or 0) < attack_cost:
            await interaction.followup.send(f"Você precisa de {attack_cost} Luma Coins para atacar.")
            return

        balance_after_cost = await self._db().fetchval(
            """
            UPDATE economy
            SET balance = balance - $1,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $2
            RETURNING balance
            """,
            attack_cost,
            interaction.user.id,
        )

        defense = max(1, int(territory["defense_level"] or 1))
        success_chance = max(0.20, 0.70 - (defense * 0.05))
        if random.random() >= success_chance:
            await self._db().execute("UPDATE territories SET attack_time = CURRENT_TIMESTAMP WHERE id = $1", territory_id)
            embed = discord.Embed(title="🛡️ Ataque frustrado", color=discord.Color.red())
            embed.description = (
                f"**{territory['name']}** resistiu ao ataque. "
                f"Chance de sucesso: **{int(success_chance * 100)}%**."
            )
            embed.add_field(name="Saldo atual", value=str(int(balance_after_cost or 0)), inline=True)
            await interaction.followup.send(embed=embed)
            return

        reward = int(territory["luma_coins"] or 100)
        balance_after_win = await self._db().fetchval(
            """
            UPDATE economy
            SET balance = balance + $1,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $2
            RETURNING balance
            """,
            reward,
            interaction.user.id,
        )
        await self._db().execute(
            """
            UPDATE territories
            SET owner_id = $1,
                called_at = CURRENT_TIMESTAMP,
                attack_time = CURRENT_TIMESTAMP,
                defense_level = 1
            WHERE id = $2
            """,
            interaction.user.id,
            territory_id,
        )

        embed = discord.Embed(title="⚔️ Conquista realizada", color=discord.Color.green())
        embed.description = f"Você conquistou **{territory['name']}** e saqueou **{reward}** Luma Coins."
        embed.add_field(name="Saldo atual", value=str(int(balance_after_win or 0)), inline=True)
        await interaction.followup.send(embed=embed)

    @terri.command(name="defend", description="Aumenta em 1 o nível de defesa do seu território")
    @app_commands.describe(territory_id="ID do território")
    async def defend_territory(self, interaction: discord.Interaction, territory_id: int):
        await interaction.response.defer()
        territory = await self._get_territory(territory_id)
        if not territory:
            await interaction.followup.send("Território não encontrado.")
            return
        if territory["owner_id"] != interaction.user.id:
            await interaction.followup.send("Você só pode defender territórios que você possui.")
            return
        if int(territory["defense_level"] or 1) >= 5:
            await interaction.followup.send("Esse território já está no nível máximo de defesa.")
            return

        new_defense = await self._db().fetchval(
            "UPDATE territories SET defense_level = LEAST(defense_level + 1, 5) WHERE id = $1 RETURNING defense_level",
            territory_id,
        )
        embed = discord.Embed(title="🛡️ Defesa reforçada", color=discord.Color.teal())
        embed.description = f"**{territory['name']}** agora está no nível **{int(new_defense or 1)}**."
        await interaction.followup.send(embed=embed)

    @terri.command(name="upgrade", description="Abre o menu de upgrade de defesa")
    @app_commands.describe(territory_id="ID do território")
    async def upgrade_defense(self, interaction: discord.Interaction, territory_id: int):
        await interaction.response.defer()
        territory = await self._get_territory(territory_id)
        if not territory:
            await interaction.followup.send("Território não encontrado.")
            return
        if territory["owner_id"] != interaction.user.id:
            await interaction.followup.send("Você só pode evoluir territórios que você possui.")
            return

        economy = await self._ensure_economy(interaction.user.id)
        embed = discord.Embed(title=f"⚙️ Upgrade de Defesa — {territory['name']}", color=discord.Color.purple())
        embed.description = (
            f"Defesa atual: **{int(territory['defense_level'] or 1)}/5**\n"
            f"Seu saldo: **{int(economy['balance'] or 0)}** Luma Coins"
        )
        view = UpgradeView(self, int(territory_id), str(territory["name"]), int(territory["defense_level"] or 1))
        await interaction.followup.send(embed=embed, view=view)

    @terri.command(name="leaderboard", description="Mostra o ranking de territórios e ligas")
    async def leaderboard_territories(self, interaction: discord.Interaction):
        await interaction.response.defer()
        rows = await self._db().fetch(
            """
            SELECT
                owner_id,
                COUNT(*) AS owned_count,
                COALESCE(SUM(defense_level), 0) AS total_defense,
                COALESCE(SUM(owner_reward_coins), 0) AS reward_rate,
                COALESCE(SUM(luma_coins), 0) AS conquest_pot
            FROM territories
            WHERE owner_id IS NOT NULL
            GROUP BY owner_id
            ORDER BY owned_count DESC, total_defense DESC, conquest_pot DESC
            LIMIT 10
            """
        )
        if not rows:
            await interaction.followup.send("Ainda não há donos de territórios suficientes para formar um ranking.")
            return

        embed = discord.Embed(title="👑 Territory Leaderboard", color=discord.Color.blurple())
        for index, row in enumerate(rows, start=1):
            score = territory_score(
                int(row["owned_count"] or 0),
                int(row["total_defense"] or 0),
                int(row["reward_rate"] or 0),
                int(row["conquest_pot"] or 0),
            )
            league = league_for_score(score)
            embed.add_field(
                name=f"#{index} • {format_owner(interaction.guild, int(row['owner_id']))}",
                value=(
                    f"Liga: **{league}**\n"
                    f"Territórios: **{int(row['owned_count'] or 0)}** • Defesa: **{int(row['total_defense'] or 0)}**\n"
                    f"Score: **{score}**"
                ),
                inline=False,
            )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Territories(bot))
