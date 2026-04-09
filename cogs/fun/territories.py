import discord
from discord.ext import commands
from discord import app_commands
from scripts.db import Database
import random
import datetime

db = Database()


async def get_territory(territory_id: int):
    return await db.fetchrow("SELECT * FROM territories WHERE id = $1", territory_id)


async def ensure_economy(user_id: int):
    economy = await db.fetchrow("SELECT * FROM economy WHERE user_id = $1", user_id)
    if not economy:
        await db.execute(
            "INSERT INTO economy (user_id, balance) VALUES ($1, 0) ON CONFLICT DO NOTHING",
            user_id
        )
        economy = await db.fetchrow("SELECT * FROM economy WHERE user_id = $1", user_id)
    return economy


class Territories(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    terri = app_commands.Group(name="territories", description="Comandos relacionados a territórios")

    # ── list ──────────────────────────────────────────────────────────────────

    @terri.command(name="list", description="Lista todos os territórios disponíveis")
    async def list_territories(self, interaction: discord.Interaction):
        await interaction.response.defer()
        territories = await db.fetch("SELECT * FROM territories ORDER BY id")
        if not territories:
            await interaction.followup.send("Nenhum território encontrado.")
            return

        embed = discord.Embed(title="🗺️ Territórios", color=discord.Color.blue())
        for t in territories:
            owner = f"<@{t['owner_id']}>" if t['owner_id'] else "Sem dono"
            embed.add_field(
                name=f"`#{t['id']}` {t['name']}",
                value=f"Dono: {owner} | Defesa: **{t['defense_level']}** | Prêmio: **{t['luma_coins']}** coins",
                inline=False
            )
        await interaction.followup.send(embed=embed)

    # ── mine ──────────────────────────────────────────────────────────────────

    @terri.command(name="mine", description="Lista os territórios que você possui")
    async def my_territories(self, interaction: discord.Interaction):
        await interaction.response.defer()
        territories = await db.fetch(
            "SELECT * FROM territories WHERE owner_id = $1 ORDER BY id",
            interaction.user.id
        )
        if not territories:
            await interaction.followup.send(
                "Você não possui nenhum território. Use `/territories claim` para reivindicar um sem dono "
                "ou `/territories attack` para conquistar um inimigo."
            )
            return

        embed = discord.Embed(title="🏰 Seus Territórios", color=discord.Color.gold())
        for t in territories:
            embed.add_field(
                name=f"`#{t['id']}` {t['name']}",
                value=f"Defesa: **{t['defense_level']}** | Recompensa passiva: **{t['owner_reward_coins']}** coins/coleta",
                inline=False
            )
        await interaction.followup.send(embed=embed)

    # ── info ──────────────────────────────────────────────────────────────────

    @terri.command(name="info", description="Mostra informações sobre um território específico")
    @app_commands.describe(territory_id="ID do território")
    async def info_territory(self, interaction: discord.Interaction, territory_id: int):
        await interaction.response.defer()
        territory = await get_territory(territory_id)
        if not territory:
            await interaction.followup.send("Território não encontrado.")
            return

        embed = discord.Embed(title=f"🏯 {territory['name']}", color=discord.Color.green())
        embed.add_field(name="ID", value=territory['id'], inline=True)
        embed.add_field(
            name="Dono",
            value=f"<@{territory['owner_id']}>" if territory['owner_id'] else "Sem dono",
            inline=True
        )
        embed.add_field(name="Nível de defesa", value=territory['defense_level'], inline=True)
        embed.add_field(name="Prêmio por conquista", value=f"{territory['luma_coins']} Luma Coins", inline=True)
        embed.add_field(name="Recompensa passiva", value=f"{territory['owner_reward_coins']} coins/coleta", inline=True)
        embed.add_field(
            name="Última coleta",
            value=discord.utils.format_dt(territory['called_at'], 'R') if territory['called_at'] else "Nunca",
            inline=True
        )
        embed.add_field(
            name="Último ataque",
            value=discord.utils.format_dt(territory['attack_time'], 'R') if territory['attack_time'] else "Nunca",
            inline=True
        )
        await interaction.followup.send(embed=embed)

    # ── claim ─────────────────────────────────────────────────────────────────

    @terri.command(name="claim", description="Reivindica um território sem dono (custa 50 Luma Coins)")
    @app_commands.describe(territory_id="ID do território")
    async def claim_territory(self, interaction: discord.Interaction, territory_id: int):
        await interaction.response.defer()
        territory = await get_territory(territory_id)
        if not territory:
            await interaction.followup.send("Território não encontrado.")
            return

        if territory['owner_id']:
            await interaction.followup.send(
                f"Esse território já pertence a <@{territory['owner_id']}>. "
                "Use `/territories attack` para tentar conquistá-lo."
            )
            return

        claim_cost = 50
        economy = await ensure_economy(interaction.user.id)
        if economy['balance'] < claim_cost:
            await interaction.followup.send(
                f"Você precisa de **{claim_cost} Luma Coins** para reivindicar um território. "
                f"Seu saldo atual: **{economy['balance']}**."
            )
            return

        await db.execute(
            "UPDATE economy SET balance = balance - $1, updated_at = NOW() WHERE user_id = $2",
            claim_cost, interaction.user.id
        )
        await db.execute(
            "UPDATE territories SET owner_id = $1, called_at = NOW() WHERE id = $2",
            interaction.user.id, territory_id
        )

        embed = discord.Embed(
            title="✅ Território Reivindicado!",
            description=f"Você agora é o dono de **{territory['name']}**!",
            color=discord.Color.green()
        )
        embed.add_field(name="Custo", value=f"{claim_cost} Luma Coins", inline=True)
        embed.add_field(name="Recompensa passiva", value=f"{territory['owner_reward_coins']} coins/coleta", inline=True)
        await interaction.followup.send(embed=embed)

    # ── collect ───────────────────────────────────────────────────────────────

    @terri.command(name="collect", description="Coleta a recompensa passiva do seu território (1x por hora)")
    @app_commands.describe(territory_id="ID do território")
    async def collect_territory(self, interaction: discord.Interaction, territory_id: int):
        await interaction.response.defer()
        territory = await get_territory(territory_id)
        if not territory:
            await interaction.followup.send("Território não encontrado.")
            return

        if territory['owner_id'] != interaction.user.id:
            await interaction.followup.send("Você só pode coletar recompensas de territórios que você possui.")
            return

        cooldown_seconds = 3600
        if territory['called_at']:
            last = territory['called_at']
            if last.tzinfo is None:
                last = last.replace(tzinfo=datetime.timezone.utc)
            elapsed = (datetime.datetime.now(datetime.timezone.utc) - last).total_seconds()
            if elapsed < cooldown_seconds:
                remaining = int(cooldown_seconds - elapsed)
                m, s = divmod(remaining, 60)
                await interaction.followup.send(
                    f"Você já coletou recentemente. Próxima coleta disponível em **{m}m {s}s**."
                )
                return

        reward = territory['owner_reward_coins']
        await db.execute(
            "UPDATE economy SET balance = balance + $1, updated_at = NOW() WHERE user_id = $2",
            reward, interaction.user.id
        )
        await db.execute(
            "UPDATE territories SET called_at = NOW() WHERE id = $1",
            territory_id
        )

        embed = discord.Embed(
            title="💰 Recompensa Coletada!",
            description=f"Você coletou **{reward} Luma Coins** do território **{territory['name']}**!",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Próxima coleta disponível em 1 hora.")
        await interaction.followup.send(embed=embed)

    # ── attack ────────────────────────────────────────────────────────────────

    @terri.command(name="attack", description="Ataca um território para conquistá-lo (custa 100 Luma Coins)")
    @app_commands.describe(territory_id="ID do território")
    async def attack_territory(self, interaction: discord.Interaction, territory_id: int):
        await interaction.response.defer()
        territory = await get_territory(territory_id)
        if not territory:
            await interaction.followup.send("Território não encontrado.")
            return

        if territory['owner_id'] == interaction.user.id:
            await interaction.followup.send("Você não pode atacar seu próprio território.")
            return

        attack_cost = 100
        economy = await ensure_economy(interaction.user.id)
        if economy['balance'] < attack_cost:
            await interaction.followup.send(
                f"Você precisa de **{attack_cost} Luma Coins** para atacar. Seu saldo: **{economy['balance']}**."
            )
            return

        await db.execute(
            "UPDATE economy SET balance = balance - $1, updated_at = NOW() WHERE user_id = $2",
            attack_cost, interaction.user.id
        )

        # Chance base 70%, reduz 5% por nível de defesa, mínimo 20%
        defense = territory['defense_level']
        success_chance = max(0.20, 0.70 - (defense * 0.05))
        attack_success = random.random() < success_chance

        if attack_success:
            prev_owner = territory['owner_id']
            conquest_reward = territory['luma_coins']

            await db.execute(
                "UPDATE territories SET owner_id = $1, called_at = NOW(), attack_time = NOW(), defense_level = 1 WHERE id = $2",
                interaction.user.id, territory_id
            )
            await db.execute(
                "UPDATE economy SET balance = balance + $1, updated_at = NOW() WHERE user_id = $2",
                conquest_reward, interaction.user.id
            )

            embed = discord.Embed(
                title="⚔️ Ataque bem-sucedido!",
                description=f"Você conquistou **{territory['name']}**!",
                color=discord.Color.green()
            )
            embed.add_field(name="Recompensa", value=f"{conquest_reward} Luma Coins", inline=True)
            embed.add_field(
                name="Dono anterior",
                value=f"<@{prev_owner}>" if prev_owner else "Ninguém",
                inline=True
            )
            embed.add_field(name="Defesa resetada", value="Nível 1", inline=True)
        else:
            embed = discord.Embed(
                title="🛡️ Ataque frustrado!",
                description=f"Sua investida contra **{territory['name']}** foi repelida.",
                color=discord.Color.red()
            )
            embed.add_field(name="Custo", value=f"{attack_cost} Luma Coins perdidos", inline=True)
            embed.add_field(name="Defesa inimiga", value=f"Nível {defense}", inline=True)
            embed.add_field(name="Chance de sucesso", value=f"{int(success_chance * 100)}%", inline=True)

        await interaction.followup.send(embed=embed)

    # ── defend ────────────────────────────────────────────────────────────────

    @terri.command(name="defend", description="Adiciona +1 nível de defesa ao seu território (gratuito)")
    @app_commands.describe(territory_id="ID do território")
    async def defend_territory(self, interaction: discord.Interaction, territory_id: int):
        await interaction.response.defer()
        territory = await get_territory(territory_id)
        if not territory:
            await interaction.followup.send("Território não encontrado.")
            return

        if territory['owner_id'] != interaction.user.id:
            await interaction.followup.send("Você só pode defender territórios que você possui.")
            return

        await db.execute(
            "UPDATE territories SET defense_level = defense_level + 1 WHERE id = $1",
            territory_id
        )
        new_level = territory['defense_level'] + 1
        await interaction.followup.send(
            f"🛡️ Nível de defesa de **{territory['name']}** aumentado para **{new_level}**."
        )

    # ── upgrade ───────────────────────────────────────────────────────────────

    @terri.command(name="upgrade", description="Melhora o nível de defesa do seu território via menu")
    @app_commands.describe(territory_id="ID do território")
    async def upgrade_defense(self, interaction: discord.Interaction, territory_id: int):
        await interaction.response.defer()
        territory = await get_territory(territory_id)
        if not territory:
            await interaction.followup.send("Território não encontrado.")
            return

        if territory['owner_id'] != interaction.user.id:
            await interaction.followup.send("Você só pode melhorar a defesa de territórios que você possui.")
            return

        economy = await ensure_economy(interaction.user.id)
        defense_level = territory['defense_level']

        class UpgradeSelection(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label="Taxa 1: +1 Defesa (200 Luma Coins)", value="1"),
                    discord.SelectOption(label="Taxa 2: +3 Defesa (500 Luma Coins)", value="2"),
                    discord.SelectOption(label="Taxa 3: +5 Defesa (1000 Luma Coins)", value="3"),
                ]
                super().__init__(placeholder="Selecione a taxa de upgrade", options=options)

            async def callback(self, interaction: discord.Interaction):
                tiers = {"1": (200, 1), "2": (500, 3), "3": (1000, 5)}
                cost, defense_increase = tiers[self.values[0]]

                current_economy = await db.fetchrow(
                    "SELECT * FROM economy WHERE user_id = $1", interaction.user.id
                )
                current_balance = current_economy['balance'] if current_economy else 0
                if not current_economy or current_balance < cost:
                    await interaction.response.send_message(
                        f"Saldo insuficiente. Necessário: **{cost}**, seu saldo: **{current_balance}**.",
                        ephemeral=True
                    )
                    return

                await db.execute(
                    "UPDATE economy SET balance = balance - $1, updated_at = NOW() WHERE user_id = $2",
                    cost, interaction.user.id
                )
                await db.execute(
                    "UPDATE territories SET defense_level = defense_level + $1 WHERE id = $2",
                    defense_increase, territory_id
                )
                new_level = defense_level + defense_increase
                await interaction.response.send_message(
                    f"⚙️ Defesa de **{territory['name']}** aumentada para nível **{new_level}**! "
                    f"Custo: {cost} Luma Coins."
                )

        view = discord.ui.View()
        view.add_item(UpgradeSelection())
        embed = discord.Embed(
            title=f"⚙️ Upgrade de Defesa — {territory['name']}",
            description=f"Nível atual: **{defense_level}** | Seu saldo: **{economy['balance']} Luma Coins**",
            color=discord.Color.purple()
        )
        embed.add_field(name="Taxa 1", value="+1 defesa por **200** Luma Coins", inline=False)
        embed.add_field(name="Taxa 2", value="+3 defesa por **500** Luma Coins", inline=False)
        embed.add_field(name="Taxa 3", value="+5 defesa por **1000** Luma Coins", inline=False)
        await interaction.followup.send(embed=embed, view=view)

    # ── abandon ───────────────────────────────────────────────────────────────

    @terri.command(name="abandon", description="Abandona um território que você possui")
    @app_commands.describe(territory_id="ID do território")
    async def abandon_territory(self, interaction: discord.Interaction, territory_id: int):
        await interaction.response.defer()
        territory = await get_territory(territory_id)
        if not territory:
            await interaction.followup.send("Território não encontrado.")
            return

        if territory['owner_id'] != interaction.user.id:
            await interaction.followup.send("Você só pode abandonar territórios que você possui.")
            return

        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)

            @discord.ui.button(label="Confirmar abandono", style=discord.ButtonStyle.danger)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.stop()
                await db.execute(
                    "UPDATE territories SET owner_id = NULL, defense_level = 1, called_at = NULL WHERE id = $1",
                    territory_id
                )
                await interaction.response.edit_message(
                    content=f"🚪 Você abandonou **{territory['name']}**. O território está livre novamente.",
                    embed=None, view=None
                )

            @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.stop()
                await interaction.response.edit_message(content="Ação cancelada.", embed=None, view=None)

        embed = discord.Embed(
            title="⚠️ Abandonar Território",
            description=(
                f"Tem certeza que deseja abandonar **{territory['name']}**?\n"
                "O nível de defesa será resetado e qualquer um poderá reivindicá-lo."
            ),
            color=discord.Color.orange()
        )
        await interaction.followup.send(embed=embed, view=ConfirmView())


async def setup(bot: commands.Bot):
    await bot.add_cog(Territories(bot))
