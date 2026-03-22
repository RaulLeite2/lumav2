# FINALMENTE ESSA PORCARIA VAI TER ECONOMIA!!!!!!!!!! AYRTON AYRTON AYRRRRRRRTOOOOOOON SENNA DO BRASIL!!!
# eu tenho que para com isso kk
import discord
from discord import app_commands
from discord.ext import commands
import random
import json
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

    async def _record_transaction(
        self,
        user_id: int,
        delta: int,
        balance_after: int | None,
        tx_type: str,
        guild_id: int | None = None,
        metadata: dict | None = None,
    ) -> None:
        db = self._db()
        await db.execute(
            """
            INSERT INTO economy_transactions (user_id, guild_id, delta, balance_after, tx_type, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            """,
            user_id,
            guild_id,
            int(delta),
            balance_after,
            str(tx_type),
            json.dumps(metadata or {}),
        )

    def _season_window(self) -> tuple[str, datetime, datetime]:
        now = datetime.now(timezone.utc)
        season_key = now.strftime("%Y-%m")
        starts_at = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        if now.month == 12:
            ends_at = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            ends_at = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
        return season_key, starts_at, ends_at

    async def _ensure_current_season(self) -> tuple[str, datetime, datetime]:
        db = self._db()
        season_key, starts_at, ends_at = self._season_window()
        await db.execute(
            """
            INSERT INTO economy_seasons (season_key, starts_at, ends_at, is_active)
            VALUES ($1, $2, $3, TRUE)
            ON CONFLICT (season_key) DO UPDATE
            SET starts_at = EXCLUDED.starts_at,
                ends_at = EXCLUDED.ends_at,
                is_active = TRUE
            """,
            season_key,
            starts_at.replace(tzinfo=None),
            ends_at.replace(tzinfo=None),
        )
        await db.execute(
            """
            UPDATE economy_seasons
            SET is_active = FALSE
            WHERE season_key <> $1
            """,
            season_key,
        )
        return season_key, starts_at, ends_at

    async def _fetch_badges(self, user_id: int) -> list[str]:
        db = self._db()
        rows = await db.fetch(
            """
            SELECT badge_key
            FROM user_profile_badges
            WHERE user_id = $1
            ORDER BY unlocked_at ASC
            """,
            user_id,
        )
        return [str(row["badge_key"]) for row in rows]

    async def _ensure_shop_items(self) -> None:
        db = self._db()
        rows = await db.fetch("SELECT item_key FROM shop_items LIMIT 1")
        if rows:
            return

        await db.executemany(
            """
            INSERT INTO shop_items (item_key, item_name, item_description, price, category, is_active)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (item_key) DO NOTHING
            """,
            [
                ("xp_boost_1h", "XP Boost 1h", "Active your leveling journey: grants a personal XP bonus token for 1 hour.", 350, "boost", True),
                ("lucky_crate", "Lucky Crate", "A crate with random economy surprises (future expansion item).", 500, "crate", True),
                ("profile_badge", "Profile Badge", "Collectible profile badge to show your support in future profile cards.", 750, "cosmetic", True),
            ],
        )

    async def _fetch_shop_item(self, item_key: str):
        db = self._db()
        return await db.fetchrow(
            """
            SELECT item_key, item_name, item_description, price, category, is_active
            FROM shop_items
            WHERE LOWER(item_key) = LOWER($1)
            """,
            item_key,
        )

    async def _unlock_badge(self, user_id: int, badge_key: str) -> bool:
        db = self._db()
        value = await db.fetchval(
            """
            INSERT INTO user_profile_badges (user_id, badge_key)
            VALUES ($1, $2)
            ON CONFLICT (user_id, badge_key) DO NOTHING
            RETURNING badge_key
            """,
            user_id,
            badge_key,
        )
        return value is not None

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
        await self._record_transaction(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id if interaction.guild else None,
            delta=reward,
            balance_after=int(new_balance or 0),
            tx_type="daily",
            metadata={"rarity": rarity_label},
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

    @app_commands.command(name="shop", description="Mostra os itens disponiveis na loja de economia")
    async def shop(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        db = self._db()

        await self._ensure_shop_items()
        rows = await db.fetch(
            """
            SELECT item_key, item_name, item_description, price, category
            FROM shop_items
            WHERE is_active = TRUE
            ORDER BY price ASC
            """
        )

        if not rows:
            await interaction.response.send_message(
                tr(
                    lang,
                    "A loja esta vazia no momento.",
                    "The shop is empty right now.",
                    "La tienda esta vacia en este momento.",
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=tr(lang, "Loja de Economia", "Economy Shop", "Tienda de Economia"),
            description=tr(
                lang,
                "Use **/buy item_key quantidade** para comprar.",
                "Use **/buy item_key quantity** to purchase.",
                "Usa **/buy item_key cantidad** para comprar.",
            ),
            color=discord.Color.green(),
        )

        for row in rows:
            embed.add_field(
                name=f"{row['item_name']} ({row['item_key']})",
                value=f"{row['item_description']}\n**{row['price']} Lumicoins** - {row['category']}",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Compra um item na loja de economia")
    async def buy(self, interaction: discord.Interaction, item_key: str, quantity: app_commands.Range[int, 1, 50] = 1):
        lang = await self._lang(interaction)
        await self._ensure_account(interaction.user.id)
        await self._ensure_shop_items()

        item = await self._fetch_shop_item(item_key)
        if item is None or not bool(item.get("is_active")):
            await interaction.response.send_message(
                tr(
                    lang,
                    "Item nao encontrado ou indisponivel.",
                    "Item not found or unavailable.",
                    "Item no encontrado o no disponible.",
                ),
                ephemeral=True,
            )
            return

        unit_price = int(item["price"])
        total_cost = unit_price * int(quantity)

        async with self.bot.pool.acquire() as connection:
            async with connection.transaction():
                current_balance = await connection.fetchval(
                    "SELECT balance FROM economy WHERE user_id = $1 FOR UPDATE",
                    interaction.user.id,
                )
                current_balance = int(current_balance or 0)

                if current_balance < total_cost:
                    await interaction.response.send_message(
                        tr(
                            lang,
                            f"Saldo insuficiente. Voce precisa de **{total_cost}** e tem **{current_balance}** Lumicoins.",
                            f"Insufficient balance. You need **{total_cost}** and have **{current_balance}** Lumicoins.",
                            f"Saldo insuficiente. Necesitas **{total_cost}** y tienes **{current_balance}** Lumicoins.",
                        ),
                        ephemeral=True,
                    )
                    return

                new_balance = await connection.fetchval(
                    """
                    UPDATE economy
                    SET balance = balance - $1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $2
                    RETURNING balance
                    """,
                    total_cost,
                    interaction.user.id,
                )

                new_quantity = await connection.fetchval(
                    """
                    INSERT INTO user_inventory (user_id, item_key, quantity, updated_at)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id, item_key)
                    DO UPDATE SET
                        quantity = user_inventory.quantity + EXCLUDED.quantity,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING quantity
                    """,
                    interaction.user.id,
                    str(item["item_key"]),
                    int(quantity),
                )

                await connection.execute(
                    """
                    INSERT INTO economy_transactions (user_id, guild_id, delta, balance_after, tx_type, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                    """,
                    interaction.user.id,
                    interaction.guild.id if interaction.guild else None,
                    -int(total_cost),
                    int(new_balance or 0),
                    "shop_buy",
                    json.dumps({"item_key": str(item["item_key"]), "quantity": int(quantity), "unit_price": int(unit_price)}),
                )

        await interaction.response.send_message(
            tr(
                lang,
                f"Compra realizada: **{quantity}x {item['item_name']}** por **{total_cost} Lumicoins**.\nSaldo atual: **{int(new_balance or 0)}**\nNo inventario: **{int(new_quantity or 0)}**",
                f"Purchase completed: **{quantity}x {item['item_name']}** for **{total_cost} Lumicoins**.\nCurrent balance: **{int(new_balance or 0)}**\nInventory amount: **{int(new_quantity or 0)}**",
                f"Compra completada: **{quantity}x {item['item_name']}** por **{total_cost} Lumicoins**.\nSaldo actual: **{int(new_balance or 0)}**\nEn inventario: **{int(new_quantity or 0)}**",
            )
        )

    @app_commands.command(name="inventory", description="Mostra seu inventario de itens da loja")
    async def inventory(self, interaction: discord.Interaction, member: discord.Member | None = None):
        lang = await self._lang(interaction)
        db = self._db()

        target = member or interaction.user
        await self._ensure_shop_items()

        rows = await db.fetch(
            """
            SELECT i.item_key, s.item_name, i.quantity
            FROM user_inventory i
            JOIN shop_items s ON s.item_key = i.item_key
            WHERE i.user_id = $1
              AND i.quantity > 0
            ORDER BY i.quantity DESC, s.item_name ASC
            """,
            target.id,
        )

        if not rows:
            await interaction.response.send_message(
                tr(
                    lang,
                    f"{target.mention} ainda nao possui itens no inventario.",
                    f"{target.mention} does not have items in inventory yet.",
                    f"{target.mention} aun no tiene items en inventario.",
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=tr(lang, f"Inventario de {target.display_name}", f"{target.display_name}'s Inventory", f"Inventario de {target.display_name}"),
            color=discord.Color.blurple(),
        )
        for row in rows:
            embed.add_field(name=row["item_name"], value=f"{row['quantity']}x ({row['item_key']})", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="useitem", description="Usa um item do seu inventario")
    async def useitem(self, interaction: discord.Interaction, item_key: str):
        lang = await self._lang(interaction)
        await self._ensure_account(interaction.user.id)

        item = await self._fetch_shop_item(item_key)
        if item is None:
            await interaction.response.send_message(
                tr(
                    lang,
                    "Item nao encontrado.",
                    "Item not found.",
                    "Item no encontrado.",
                ),
                ephemeral=True,
            )
            return

        normalized_key = str(item["item_key"]).lower()

        async with self.bot.pool.acquire() as connection:
            async with connection.transaction():
                quantity = await connection.fetchval(
                    """
                    SELECT quantity
                    FROM user_inventory
                    WHERE user_id = $1 AND item_key = $2
                    FOR UPDATE
                    """,
                    interaction.user.id,
                    str(item["item_key"]),
                )
                quantity = int(quantity or 0)
                if quantity <= 0:
                    await interaction.response.send_message(
                        tr(
                            lang,
                            "Voce nao possui esse item no inventario.",
                            "You do not have this item in your inventory.",
                            "No tienes este item en tu inventario.",
                        ),
                        ephemeral=True,
                    )
                    return

                if normalized_key == "xp_boost_1h":
                    await connection.execute(
                        """
                        INSERT INTO user_item_effects (user_id, effect_key, expires_at, updated_at)
                        VALUES ($1, 'xp_boost', CURRENT_TIMESTAMP + INTERVAL '1 hour', CURRENT_TIMESTAMP)
                        ON CONFLICT (user_id, effect_key)
                        DO UPDATE SET
                            expires_at = CASE
                                WHEN user_item_effects.expires_at > CURRENT_TIMESTAMP
                                    THEN user_item_effects.expires_at + INTERVAL '1 hour'
                                ELSE CURRENT_TIMESTAMP + INTERVAL '1 hour'
                            END,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        interaction.user.id,
                    )
                    await connection.execute(
                        """
                        UPDATE user_inventory
                        SET quantity = quantity - 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = $1 AND item_key = $2
                        """,
                        interaction.user.id,
                        str(item["item_key"]),
                    )
                    await interaction.response.send_message(
                        tr(
                            lang,
                            "XP Boost ativado por 1 hora! Bonus aplicado no ganho de XP.",
                            "XP Boost activated for 1 hour! Bonus now applies to XP gain.",
                            "XP Boost activado por 1 hora! El bonus ahora se aplica al XP.",
                        ),
                        ephemeral=True,
                    )
                    return

                if normalized_key == "lucky_crate":
                    rarity = random.choices(
                        [("common", 120), ("rare", 250), ("epic", 500), ("legendary", 1000)],
                        weights=[70, 20, 9, 1],
                        k=1,
                    )[0]
                    reward = int(rarity[1])

                    await connection.execute(
                        """
                        UPDATE user_inventory
                        SET quantity = quantity - 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = $1 AND item_key = $2
                        """,
                        interaction.user.id,
                        str(item["item_key"]),
                    )
                    new_balance = await connection.fetchval(
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
                    await connection.execute(
                        """
                        INSERT INTO economy_transactions (user_id, guild_id, delta, balance_after, tx_type, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                        """,
                        interaction.user.id,
                        interaction.guild.id if interaction.guild else None,
                        int(reward),
                        int(new_balance or 0),
                        "crate_reward",
                        json.dumps({"rarity": str(rarity[0])}),
                    )
                    await interaction.response.send_message(
                        tr(
                            lang,
                            f"Lucky Crate aberta! Voce ganhou **{reward} Lumicoins**. Saldo atual: **{int(new_balance or 0)}**.",
                            f"Lucky Crate opened! You earned **{reward} Lumicoins**. Current balance: **{int(new_balance or 0)}**.",
                            f"Lucky Crate abierta! Ganaste **{reward} Lumicoins**. Saldo actual: **{int(new_balance or 0)}**.",
                        ),
                    )
                    return

                if normalized_key == "profile_badge":
                    await connection.execute(
                        """
                        UPDATE user_inventory
                        SET quantity = quantity - 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = $1 AND item_key = $2
                        """,
                        interaction.user.id,
                        str(item["item_key"]),
                    )

                else:
                    await interaction.response.send_message(
                        tr(
                            lang,
                            "Esse item ainda nao pode ser usado.",
                            "This item cannot be used yet.",
                            "Este item aun no se puede usar.",
                        ),
                        ephemeral=True,
                    )
                    return

        if normalized_key == "profile_badge":
            unlocked = await self._unlock_badge(interaction.user.id, "supporter_badge")
            await interaction.response.send_message(
                tr(
                    lang,
                    "Badge de perfil ativada!" if unlocked else "Voce ja tinha essa badge. Item consumido para efeito visual.",
                    "Profile badge activated!" if unlocked else "You already had this badge. Item consumed for visual effect.",
                    "Insignia de perfil activada!" if unlocked else "Ya tenias esta insignia. Item consumido para efecto visual.",
                ),
                ephemeral=True,
            )

    @app_commands.command(name="badges", description="Mostra suas badges de perfil")
    async def badges(self, interaction: discord.Interaction, member: discord.Member | None = None):
        lang = await self._lang(interaction)
        db = self._db()
        target = member or interaction.user

        rows = await db.fetch(
            """
            SELECT badge_key, unlocked_at
            FROM user_profile_badges
            WHERE user_id = $1
            ORDER BY unlocked_at ASC
            """,
            target.id,
        )
        if not rows:
            await interaction.response.send_message(
                tr(
                    lang,
                    f"{target.mention} ainda nao tem badges.",
                    f"{target.mention} does not have badges yet.",
                    f"{target.mention} aun no tiene insignias.",
                ),
                ephemeral=True,
            )
            return

        labels = {
            "supporter_badge": tr(lang, "Badge de Apoiador", "Supporter Badge", "Insignia de Apoyo"),
        }
        embed = discord.Embed(
            title=tr(lang, f"Badges de {target.display_name}", f"{target.display_name}'s badges", f"Insignias de {target.display_name}"),
            color=discord.Color.gold(),
        )
        for row in rows:
            key = str(row["badge_key"])
            embed.add_field(name=labels.get(key, key), value=f"{key}", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

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

                await connection.execute(
                    """
                    INSERT INTO economy_transactions (user_id, guild_id, delta, balance_after, tx_type, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                    """,
                    interaction.user.id,
                    interaction.guild.id if interaction.guild else None,
                    -int(amount),
                    int(sender_row["balance"]),
                    "transfer_out",
                    json.dumps({"target_user_id": member.id}),
                )
                await connection.execute(
                    """
                    INSERT INTO economy_transactions (user_id, guild_id, delta, balance_after, tx_type, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                    """,
                    member.id,
                    interaction.guild.id if interaction.guild else None,
                    int(amount),
                    int(recipient_row["balance"] if recipient_row else 0),
                    "transfer_in",
                    json.dumps({"source_user_id": interaction.user.id}),
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

    @app_commands.command(name="season", description="Mostra a temporada de economia atual e ranking mensal")
    async def season(self, interaction: discord.Interaction):
        lang = await self._lang(interaction)
        db = self._db()
        season_key, starts_at, ends_at = await self._ensure_current_season()

                if interaction.guild is None:
                        rows = await db.fetch(
                                """
                                SELECT user_id, COALESCE(SUM(delta), 0) AS season_score
                                FROM economy_transactions
                                WHERE created_at >= $1
                                    AND created_at < $2
                                GROUP BY user_id
                                ORDER BY season_score DESC
                                LIMIT 10
                                """,
                                starts_at.replace(tzinfo=None),
                                ends_at.replace(tzinfo=None),
                        )
                else:
                        rows = await db.fetch(
                                """
                                SELECT user_id, COALESCE(SUM(delta), 0) AS season_score
                                FROM economy_transactions
                                WHERE created_at >= $1
                                    AND created_at < $2
                                    AND guild_id = $3
                                GROUP BY user_id
                                ORDER BY season_score DESC
                                LIMIT 10
                                """,
                                starts_at.replace(tzinfo=None),
                                ends_at.replace(tzinfo=None),
                                interaction.guild.id,
                        )

        embed = discord.Embed(
            title=tr(lang, "Temporada de Economia", "Economy Season", "Temporada de Economia"),
            description=tr(
                lang,
                f"Temporada atual: **{season_key}**\nPeriodo: **{starts_at.strftime('%d/%m')} - {(ends_at - timedelta(days=1)).strftime('%d/%m')}**",
                f"Current season: **{season_key}**\nPeriod: **{starts_at.strftime('%Y-%m-%d')} to {(ends_at - timedelta(days=1)).strftime('%Y-%m-%d')}**",
                f"Temporada actual: **{season_key}**\nPeriodo: **{starts_at.strftime('%d/%m')} - {(ends_at - timedelta(days=1)).strftime('%d/%m')}**",
            ),
            color=discord.Color.orange(),
        )

        if not rows:
            embed.add_field(
                name=tr(lang, "Ranking", "Ranking", "Ranking"),
                value=tr(
                    lang,
                    "Ainda nao ha movimentacoes nesta temporada.",
                    "There are no transactions in this season yet.",
                    "Aun no hay movimientos en esta temporada.",
                ),
                inline=False,
            )
        else:
            lines = []
            for idx, row in enumerate(rows, start=1):
                username = await self._member_name_for_leaderboard(interaction.guild, int(row["user_id"]))
                lines.append(f"{idx}. {username} - {int(row['season_score'])} pts")
            embed.add_field(name=tr(lang, "Top 10", "Top 10", "Top 10"), value="\n".join(lines), inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profile", description="Mostra um perfil publico do usuario")
    async def profile(self, interaction: discord.Interaction, member: discord.Member | None = None):
        lang = await self._lang(interaction)
        db = self._db()

        target = member or interaction.user
        await self._ensure_account(target.id)

        balance = await self._fetch_balance(target.id)
        rep = await db.fetchval(
            """
            SELECT reputation
            FROM user_reputation
            WHERE user_id = $1
            """,
            target.id,
        )
        rep = int(rep or 0)

        level_row = await db.fetchrow(
            """
            SELECT level, xp
            FROM user_levels
            WHERE user_id = $1
            """,
            target.id,
        )
        level = int(level_row["level"]) if level_row else 1
        xp = int(level_row["xp"]) if level_row else 0

        badges = await self._fetch_badges(target.id)
        badge_labels = {
            "supporter_badge": tr(lang, "Apoiador", "Supporter", "Apoyo"),
        }
        badges_text = ", ".join(badge_labels.get(b, b) for b in badges[:6]) if badges else tr(
            lang,
            "Nenhuma badge ainda",
            "No badges yet",
            "Sin insignias por ahora",
        )

        embed = discord.Embed(
            title=tr(lang, f"Perfil de {target.display_name}", f"{target.display_name}'s Profile", f"Perfil de {target.display_name}"),
            description=tr(
                lang,
                "Resumo publico de economia e progressao.",
                "Public economy and progression snapshot.",
                "Resumen publico de economia y progreso.",
            ),
            color=discord.Color.from_rgb(34, 139, 230),
        )
        embed.add_field(name=tr(lang, "Lumicoins", "Lumicoins", "Lumicoins"), value=str(balance), inline=True)
        embed.add_field(name=tr(lang, "Reputacao", "Reputation", "Reputacion"), value=str(rep), inline=True)
        embed.add_field(name=tr(lang, "Nivel", "Level", "Nivel"), value=f"{level} ({xp} XP)", inline=True)
        embed.add_field(name=tr(lang, "Badges", "Badges", "Insignias"), value=badges_text, inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text=tr(lang, "Luma Profile Card", "Luma Profile Card", "Luma Profile Card"))

        await interaction.response.send_message(embed=embed)

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
