# main.py
import os
import discord
from discord.ext import commands
from discord import app_commands, Interaction, ButtonStyle, TextStyle
from discord.ui import Modal, TextInput, View, Button
import asyncio
import motor.motor_asyncio
import aiohttp

# ======= CONFIG =======
TOKEN = os.getenv("ROMA_TOKEN")
GROUP_ID = 5043872
TURISTA_ROLE_ID = 1400852869489496185
CITTADINO_ROLE_ID = 1400856967534215188
CANALE_RICHIESTE_ID = 1402403913826701442
CANALE_ESITI_ID = 1402374664659144897
ADMIN_ID = 1400852786236887252

intents = discord.Intents.default()
intents.members = True
client = commands.Bot(command_prefix="/", intents=intents)
db_client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"))
db = db_client["roma_bot"]
richieste = db["richieste"]

# ======= MODAL =======
class CittadinanzaModal(Modal, title="Richiesta Cittadinanza"):
    roblox_name = TextInput(label="Nome utente Roblox", style=TextStyle.short, required=True)

    async def on_submit(self, interaction: Interaction):
        username = self.roblox_name.value

        async with aiohttp.ClientSession() as session:
            async with session.post("https://users.roblox.com/v1/usernames/users", json={"usernames": [username]}) as resp:
                data = await resp.json()
                if not data["data"]:
                    await interaction.response.send_message("❌ Utente Roblox non trovato.", ephemeral=True)
                    return

                user_data = data["data"][0]
                user_id = user_data["id"]

async with session.get(f"https://groups.roblox.com/v1/users/{user_id}/groups/roles") as resp:
    data = await resp.json()
    if not any(group["group"]["id"] == GROUP_ID for group in data.get("data", [])):
        await interaction.response.send_message("❌ Non fai parte del gruppo Roblox.", ephemeral=True)
        return


        embed = discord.Embed(title="📥 Richiesta Cittadinanza", color=discord.Color.blue())
        embed.add_field(name="Discord", value=f"{interaction.user.mention} ({interaction.user.id})")
        embed.add_field(name="Roblox", value=f"{username} (ID: {user_id})")

        view = View()
        view.add_item(Button(label="Accetta", style=ButtonStyle.success, custom_id=f"accetta:{interaction.user.id}:{user_id}:{username}"))
        view.add_item(Button(label="Rifiuta", style=ButtonStyle.danger, custom_id=f"rifiuta:{interaction.user.id}:{user_id}:{username}"))

        channel = client.get_channel(CANALE_RICHIESTE_ID)
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Richiesta inviata.", ephemeral=True)

# ======= BOT READY =======
@client.event
async def on_ready():
    await client.tree.sync()
    print(f"Bot connesso come {client.user}")

# ======= COMANDI =======
@client.tree.command(name="richiesta_cittadinanza", description="Richiedi la cittadinanza")
async def richiesta(interaction: Interaction):
    await interaction.response.send_modal(CittadinanzaModal())

@client.tree.command(name="cerca_soggetto", description="Cerca soggetto per nome roblox")
async def cerca(interaction: Interaction, roblox_username: str):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("Non hai il permesso.", ephemeral=True)
        return
    user = await richieste.find_one({"roblox_username": roblox_username})
    if user:
        embed = discord.Embed(title="👤 Soggetto Trovato")
        embed.add_field(name="Discord", value=f"<@{user['discord_id']}> ({user['discord_tag']})")
        embed.add_field(name="Roblox", value=f"{user['roblox_username']} ({user['roblox_id']})")
        embed.add_field(name="Data", value=str(user['data']))
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Nessun soggetto trovato.", ephemeral=True)

@client.tree.command(name="elimina_soggetto", description="Elimina soggetto dal database")
async def elimina(interaction: Interaction, roblox_username: str):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("Non hai il permesso.", ephemeral=True)
        return
    result = await richieste.delete_one({"roblox_username": roblox_username})
    if result.deleted_count:
        await interaction.response.send_message("✅ Soggetto eliminato.")
    else:
        await interaction.response.send_message("❌ Nessun soggetto trovato.", ephemeral=True)

# ======= GESTIONE BUTTON =======
@client.event
async def on_interaction(interaction):
    if not interaction.type == discord.InteractionType.component:
        return

    parts = interaction.data['custom_id'].split(":")
    if len(parts) != 4:
        return

    action, discord_id, roblox_id, roblox_username = parts
    member = interaction.guild.get_member(int(discord_id))

    if action == "accetta":
        await member.remove_roles(discord.Object(id=TURISTA_ROLE_ID))
        await member.add_roles(discord.Object(id=CITTADINO_ROLE_ID))

        await richieste.insert_one({
            "discord_id": discord_id,
            "discord_tag": member.name,
            "roblox_id": roblox_id,
            "roblox_username": roblox_username,
            "data": discord.utils.utcnow()
        })

        canale_esiti = client.get_channel(CANALE_ESITI_ID)
        await canale_esiti.send(f"✅ Richiesta approvata: {member.mention} è ora cittadino.")
        await interaction.response.send_message("Richiesta approvata.", ephemeral=True)

    elif action == "rifiuta":
        class RifiutoModal(Modal, title="Motivazione Rifiuto"):
            motivo = TextInput(label="Motivazione", style=TextStyle.paragraph)

            async def on_submit(self, modal_interaction: Interaction):
                canale_esiti = client.get_channel(CANALE_ESITI_ID)
                await canale_esiti.send(f"❌ Richiesta rifiutata per {member.mention}. Motivo: {self.motivo.value}")
                await modal_interaction.response.send_message("Richiesta rifiutata.", ephemeral=True)

        await interaction.response.send_modal(RifiutoModal())

# ======= AVVIO =======
client.run(TOKEN)
