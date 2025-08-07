import os
import discord
from discord.ext import commands
from discord import app_commands, Interaction, ButtonStyle, TextStyle
from discord.ui import Modal, TextInput, View, Button
import motor.motor_asyncio
import aiohttp
from pymongo import MongoClient
from discord import app_commands, Interaction
from discord.app_commands import check

# ===== CONFIG =====
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

# Check per ruolo admin
def has_admin_role():
    async def predicate(interaction: Interaction) -> bool:
        guild = interaction.guild
        if guild is None:
            return False
        member = guild.get_member(interaction.user.id)
        if member is None:
            return False
        return any(role.id == ADMIN_ID for role in member.roles)
    return app_commands.check(predicate)

# Check per ID admin singolo
def has_admin_ID():
    async def predicate(interaction: Interaction) -> bool:
        return interaction.user.id == ADMIN_ID
    return app_commands.check(predicate)

# ===== MODAL CITTADINANZA =====
class CittadinanzaModal(Modal, title="Richiesta Cittadinanza"):
    roblox_name = TextInput(label="Nome utente Roblox", style=TextStyle.short, required=True)

    async def on_submit(self, interaction: Interaction):
        username = self.roblox_name.value

        async with aiohttp.ClientSession() as session:
            async with session.post("https://users.roblox.com/v1/usernames/users", json={"usernames": [username]}) as resp:
                data = await resp.json()
                if not data.get("data"):
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
        embed.set_footer(text="In attesa di revisione")

        view = RichiestaView(
            discord_user=interaction.user,
            roblox_id=user_id,
            roblox_username=username
        )

        canale = client.get_channel(CANALE_RICHIESTE_ID)
        if canale is None:
            canale = await client.fetch_channel(CANALE_RICHIESTE_ID)

        messaggio = await canale.send(embed=embed, view=view)
        view.message = messaggio  # salva per modifica dopo

        if interaction.message:
            try:
                await interaction.message.delete()
            except:
                pass

        await interaction.response.send_message("✅ Richiesta inviata con successo.", ephemeral=True)

# ===== VIEW CON PULSANTI =====
class RichiestaView(View):
    def __init__(self, discord_user, roblox_id, roblox_username):
        super().__init__(timeout=None)
        self.discord_user = discord_user
        self.roblox_id = roblox_id
        self.roblox_username = roblox_username
        self.message = None

    @discord.ui.button(label="✅ Accetta", style=ButtonStyle.success)
    async def accetta(self, interaction: Interaction, button: Button):
        member = interaction.guild.get_member(self.discord_user.id)
        if not member:
            await interaction.response.send_message("❌ Utente non trovato nel server.", ephemeral=True)
            return

        await member.remove_roles(discord.Object(id=TURISTA_ROLE_ID), reason="Accettato come cittadino")
        await member.add_roles(discord.Object(id=CITTADINO_ROLE_ID), reason="Accettato come cittadino")

        await richieste.insert_one({
            "discord_id": str(member.id),
            "discord_tag": str(member),
            "roblox_id": str(self.roblox_id),
            "roblox_username": self.roblox_username,
            "data": discord.utils.utcnow()
        })

        esiti = client.get_channel(CANALE_ESITI_ID)
        if esiti is None:
            esiti = await client.fetch_channel(CANALE_ESITI_ID)

        avatar_url = f"https://www.roblox.com/headshot-thumbnail/image?userId={self.roblox_id}&width=48&height=48&format=png"

        embed = discord.Embed(
            title="✅ Richiesta Cittadinanza Approvata",
            description=f"{member.mention} è stato accettato come cittadino.",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text=f"Gestito da: {interaction.user}", icon_url=interaction.user.display_avatar.url)

        await esiti.send(embed=embed)

        # modifica embed della richiesta
        embed = self.message.embeds[0]
        embed.color = discord.Color.green()
        embed.set_footer(text="Esito: ACCETTATO ✅")
        await self.message.edit(embed=embed, view=None)

        try:
            embed_dm = discord.Embed(
                title="✅ Cittadinanza Approvata",
                description="La tua richiesta è stata approvata. Benvenuto!",
                color=discord.Color.green()
            )
            embed_dm.set_thumbnail(url=avatar_url)
            embed_dm.set_footer(text=f"Gestito da: {interaction.user}", icon_url=interaction.user.display_avatar.url)
            await self.discord_user.send(embed=embed_dm)
        except:
            pass

        await interaction.response.send_message("Richiesta approvata.", ephemeral=True)

    @discord.ui.button(label="❌ Rifiuta", style=ButtonStyle.danger)
    async def rifiuta(self, interaction: Interaction, button: Button):
        # Passa self.message e altre info al Modal tramite closure
        view = self

        class MotivoRifiutoModal(Modal, title="Motivazione Rifiuto"):
            motivo = TextInput(label="Motivazione", style=TextStyle.paragraph, required=True)

            async def on_submit(self, modal_interaction: Interaction):
                embed = view.message.embeds[0]
                embed.color = discord.Color.red()
                embed.set_footer(text=f"Esito: RIFIUTATO ❌ — Motivo: {self.motivo.value}")
                await view.message.edit(embed=embed, view=None)

                esiti = client.get_channel(CANALE_ESITI_ID)
                if esiti is None:
                    esiti = await client.fetch_channel(CANALE_ESITI_ID)

                avatar_url = f"https://www.roblox.com/headshot-thumbnail/image?userId={view.roblox_id}&width=48&height=48&format=png"
                embed_esiti = discord.Embed(
                    title="❌ Richiesta Rifiutata",
                    description=f"Richiesta rifiutata per {view.discord_user.mention}.\n**Motivo:** {self.motivo.value}",
                    color=discord.Color.red()
                )
                embed_esiti.set_thumbnail(url=avatar_url)
                embed_esiti.set_footer(text=f"Gestito da: {interaction.user}", icon_url=interaction.user.display_avatar.url)
                await esiti.send(embed=embed_esiti)

                try:
                    embed_dm = discord.Embed(
                        title="❌ Cittadinanza Rifiutata",
                        description=f"Motivo del rifiuto:\n```{self.motivo.value}```",
                        color=discord.Color.red()
                    )
                    embed_dm.set_thumbnail(url=avatar_url)
                    embed_dm.set_footer(text=f"Gestito da: {interaction.user}", icon_url=interaction.user.display_avatar.url)
                    await view.discord_user.send(embed=embed_dm)
                except:
                    pass

                await modal_interaction.response.send_message("Richiesta rifiutata.", ephemeral=True)

        await interaction.response.send_modal(MotivoRifiutoModal())

# ===== COMANDI =====
@client.tree.command(name="richiesta_cittadinanza", description="Invia richiesta cittadinanza Roblox")
async def richiesta(interaction: Interaction):
    await interaction.response.send_modal(CittadinanzaModal())

# ===== COMANDO CERCA SOGGETTO =====
@app_commands.command(name="cerca_soggetto", description="Cerca un soggetto nel database")
@has_admin_ID()
async def cerca_soggetto(interaction: Interaction, nome: str):
    # Modifica il campo di ricerca se vuoi cambiare (ad es. discord_tag o roblox_username)
    soggetto = await richieste.find_one({"discord_tag": {"$regex": nome, "$options": "i"}})
    if soggetto:
        embed = discord.Embed(title="📄 Soggetto

# ===== AVVIO =====
client.run(TOKEN)
