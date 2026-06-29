from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from scripts.db import Database


def tr(lang: str, pt: str, en: str, es: str) -> str:
	return {"pt": pt, "en": en, "es": es}.get(lang, pt)


@dataclass(slots=True)
class ShopItem:
	key: str
	name: str
	description: str
	price: int
	category: str = "geral"
	currency_type: str = "lumicoins"
	is_active: bool = True


DEFAULT_RANDOM_ITEMS: list[ShopItem] = [
	ShopItem("cafe_quentinho", "Cafe Quentinho", "Aquece a alma e melhora em 200% sua vontade de farmar.", 90, "consumivel"),
	ShopItem("meia_da_sorte", "Meia da Sorte", "Uma meia misteriosa que supostamente aumenta sua sorte em partidas.", 180, "cosmetico"),
	ShopItem("pato_de_borracha", "Pato de Borracha", "Nao faz nada util, mas faz quack no seu coracao.", 75, "colecionavel"),
	ShopItem("energia_duvidosa", "Energia Duvidosa", "Nao pergunte os ingredientes. Apenas beba e confie.", 140, "consumivel"),
	ShopItem("teclado_rgb_invisivel", "Teclado RGB Invisivel", "Para digitar no escuro com estilo que so voce enxerga.", 320, "cosmetico"),
	ShopItem("capa_anti_cringe", "Capa Anti-Cringe", "Reduz danos de vergonhas alheias em areas movimentadas.", 260, "equipamento"),
	ShopItem("banana_epica", "Banana Epica", "Banana lendaria forjada por monges do grind infinito.", 210, "consumivel"),
	ShopItem("pedra_premium", "Pedra Premium", "E uma pedra. Mas premium.", 500, "colecionavel"),
	ShopItem("wifi_portatil", "Wi-Fi Portatil", "Conexao mental de alta velocidade para brainstorm noturno.", 380, "utilidade"),
	ShopItem("filtro_de_caos", "Filtro de Caos", "Transforma confusao em oportunidades (as vezes).", 430, "utilidade"),
	ShopItem("oculos_3d_sem_lente", "Oculos 3D sem Lente", "Veja o mundo em duas dimensoes e meia.", 110, "cosmetico"),
	ShopItem("cueca_da_coragem", "Cueca da Coragem", "+10 de confianca em reunioes importantes.", 290, "equipamento"),
	ShopItem("cookie_quantico", "Cookie Quantico", "Existe e nao existe ate voce abrir o inventario.", 640, "consumivel"),
	ShopItem("kit_sobrevivencia_segunda", "Kit Sobrevivencia de Segunda", "Cafe, paciencia e memes em doses industriais.", 230, "utilidade"),
	ShopItem("sabre_de_luz_imaginario", "Sabre de Luz Imaginario", "Extremamente poderoso no campo da imaginacao.", 470, "equipamento"),
	ShopItem("ramen_lendario", "Ramen Lendario", "Recupera HP emocional apos call longa.", 155, "consumivel"),
	ShopItem("controle_sem_pilha", "Controle sem Pilha", "Ideal para jogos de faz de conta competitivos.", 95, "colecionavel"),
	ShopItem("patins_do_vacilo", "Patins do Vacilo", "Acelera seu deslocamento rumo a decisoes questionaveis.", 275, "equipamento"),
	ShopItem("camisa_do_admin", "Camisa do Admin", "Nao da permissao, mas intimida visualmente.", 520, "cosmetico"),
	ShopItem("mini_ventilador_gamer", "Mini Ventilador Gamer", "Esfria o setup e o temperamento em ranqueadas.", 340, "utilidade"),
]


class Shop(commands.Cog):
	"""Template de cog de loja para economia.

	Este arquivo e um modelo base. Ajuste nomes de tabela/colunas
	conforme seu schema atual.
	"""

	shop_group = app_commands.Group(
		name="shop",
		description="Comandos extras da loja da comunidade",
	)

	def __init__(self, bot: commands.Bot):
		self.bot = bot

	def _db(self) -> Database:
		return Database(self.bot.pool)

	async def _reply(
		self,
		interaction: discord.Interaction,
		*,
		content: str | None = None,
		embed: discord.Embed | None = None,
		ephemeral: bool = False,
	) -> None:
		if interaction.response.is_done():
			await interaction.followup.send(content=content, embed=embed, ephemeral=ephemeral)
			return
		await interaction.response.send_message(content=content, embed=embed, ephemeral=ephemeral)

	async def _lang(self, interaction: discord.Interaction) -> str:
		return await self.bot.i18n.language_for_interaction(self.bot, interaction)

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

	async def _fetch_item(self, item_key: str) -> dict[str, Any] | None:
		db = self._db()
		row = await db.fetchrow(
			"""
			SELECT item_key, item_name, item_description, price, category, COALESCE(currency_type, 'lumicoins') AS currency_type, is_active
			FROM shop_items
			WHERE LOWER(item_key) = LOWER($1)
			""",
			item_key,
		)
		return dict(row) if row else None

	async def _fetch_shop_items(self) -> list[dict[str, Any]]:
		db = self._db()
		rows = await db.fetch(
			"""
			SELECT item_key, item_name, item_description, price, category, COALESCE(currency_type, 'lumicoins') AS currency_type
			FROM shop_items
			WHERE is_active = TRUE
			ORDER BY category ASC, price ASC
			"""
		)
		return [dict(r) for r in rows]

	async def _ensure_random_items(self) -> None:
		db = self._db()
		payload = [
			(
				item.key,
				item.name,
				item.description,
				int(item.price),
				item.category,
				item.currency_type,
				bool(item.is_active),
			)
			for item in DEFAULT_RANDOM_ITEMS
		]
		await db.executemany(
			"""
			INSERT INTO shop_items (item_key, item_name, item_description, price, category, currency_type, is_active)
			VALUES ($1, $2, $3, $4, $5, $6, $7)
			ON CONFLICT (item_key) DO NOTHING
			""",
			payload,
		)

	async def _fetch_balance(self, user_id: int) -> int:
		await self._ensure_account(user_id)
		db = self._db()
		value = await db.fetchval("SELECT balance FROM economy WHERE user_id = $1", user_id)
		return int(value or 0)

	@shop_group.command(name="listar", description="Mostra os itens da loja")
	async def list_items(self, interaction: discord.Interaction) -> None:
		await interaction.response.defer(thinking=False)
		lang = await self._lang(interaction)
		await self._ensure_random_items()
		items = await self._fetch_shop_items()

		if not items:
			await self._reply(
				interaction,
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
			title=tr(lang, "Loja da Comunidade", "Community Shop", "Tienda de la Comunidad"),
			description=tr(
				lang,
				"Use `/shop comprar item_key quantidade` para adquirir itens.",
				"Use `/shop comprar item_key quantity` to buy items.",
				"Usa `/shop comprar item_key cantidad` para comprar items.",
			),
			color=discord.Color.green(),
		)

		for item in items[:25]:
			currency_type = str(item.get("currency_type") or "lumicoins").lower()
			currency_label = "Drops" if currency_type == "drops" else "Lumicoins"
			embed.add_field(
				name=f"{item['item_name']} ({item['item_key']})",
				value=f"{item['item_description']}\n**{int(item['price'])} {currency_label}** • {item['category']}",
				inline=False,
			)

		await self._reply(interaction, embed=embed)

	@shop_group.command(name="comprar", description="Compra um item da loja")
	@app_commands.describe(item_key="Chave do item", quantity="Quantidade")
	async def buy_item(
		self,
		interaction: discord.Interaction,
		item_key: str,
		quantity: app_commands.Range[int, 1, 50] = 1,
	) -> None:
		await interaction.response.defer(ephemeral=True, thinking=False)
		lang = await self._lang(interaction)
		await self._ensure_account(interaction.user.id)
		await self._ensure_random_items()

		item = await self._fetch_item(item_key)
		if not item or not bool(item.get("is_active")):
			await self._reply(
				interaction,
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
		currency_type = str(item.get("currency_type") or "lumicoins").lower()
		wallet_column = "drop_balance" if currency_type == "drops" else "balance"
		currency_label = "Drops" if currency_type == "drops" else "Lumicoins"

		async with self.bot.pool.acquire() as connection:
			async with connection.transaction():
				current_balance = await connection.fetchval(
					f"SELECT {wallet_column} FROM economy WHERE user_id = $1 FOR UPDATE",
					interaction.user.id,
				)
				current_balance = int(current_balance or 0)

				if current_balance < total_cost:
					await self._reply(
						interaction,
						tr(
							lang,
							f"Saldo insuficiente. Voce precisa de **{total_cost}** e tem **{current_balance}** {currency_label}.",
							f"Insufficient balance. You need **{total_cost}** and have **{current_balance}** {currency_label}.",
							f"Saldo insuficiente. Necesitas **{total_cost}** y tienes **{current_balance}** {currency_label}.",
						),
						ephemeral=True,
					)
					return

				new_balance = await connection.fetchval(
					f"""
					UPDATE economy
					SET {wallet_column} = {wallet_column} - $1,
						updated_at = CURRENT_TIMESTAMP
					WHERE user_id = $2
					RETURNING {wallet_column}
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
					-int(total_cost) if currency_type != "drops" else 0,
					int(new_balance or 0) if currency_type != "drops" else None,
					"shop_buy_drops" if currency_type == "drops" else "shop_buy",
					json.dumps({"currency": currency_type, "item_key": str(item["item_key"]), "quantity": int(quantity), "unit_price": int(unit_price), "wallet_after": int(new_balance or 0)}),
				)

		await self._reply(
			interaction,
			tr(
				lang,
				f"Compra realizada: **{quantity}x {item['item_name']}** por **{total_cost} {currency_label}**. Saldo: **{int(new_balance or 0)} {currency_label}**. Inventario: **{int(new_quantity or 0)}**.",
				f"Purchase completed: **{quantity}x {item['item_name']}** for **{total_cost} {currency_label}**. Balance: **{int(new_balance or 0)} {currency_label}**. Inventory: **{int(new_quantity or 0)}**.",
				f"Compra completada: **{quantity}x {item['item_name']}** por **{total_cost} {currency_label}**. Saldo: **{int(new_balance or 0)} {currency_label}**. Inventario: **{int(new_quantity or 0)}**.",
			),
			ephemeral=True,
		)

	@shop_group.command(name="inventario", description="Mostra seu inventario")
	async def inventory(self, interaction: discord.Interaction, member: discord.Member | None = None) -> None:
		await interaction.response.defer(ephemeral=True, thinking=False)
		lang = await self._lang(interaction)
		db = self._db()
		target = member or interaction.user

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
			await self._reply(
				interaction,
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
		for row in rows[:25]:
			embed.add_field(name=row["item_name"], value=f"{row['quantity']}x ({row['item_key']})", inline=False)

		await self._reply(interaction, embed=embed, ephemeral=True)

	@shop_group.command(name="usar", description="Usa um item do seu inventario")
	async def use_item(self, interaction: discord.Interaction, item_key: str) -> None:
		await interaction.response.defer(ephemeral=True, thinking=False)
		lang = await self._lang(interaction)
		# Modelo base: implemente efeitos customizados aqui.
		await self._reply(
			interaction,
			tr(
				lang,
				f"Uso de item ainda em construcao para `{item_key}`.",
				f"Item usage is still under construction for `{item_key}`.",
				f"El uso del item aun esta en construccion para `{item_key}`.",
			),
			ephemeral=True,
		)


async def setup(bot: commands.Bot):
	await bot.add_cog(Shop(bot))
