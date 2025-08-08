import os
import discord
from discord.ext import commands
from discord import app_commands, Interaction, ButtonStyle, TextStyle
from discord.ui import Modal, TextInput, View, Button
import motor.motor_asyncio
import aiohttp

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

# Definizione check per ruolo admin
def has_admin_role():
    async def predicate(interaction: Interaction) -> bool:
        admin_role_id = ADMIN_ID
        guild = interaction.guild
        if guild is None:
            return False
        member = guild.get_member(interaction.user.id)
        if member is None:
            return False
        return any(role.id == admin_role_id for role in member.roles)
    return app_commands.check(predicate)

# Definizione check per ID admin singolo
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
        embed.set_footer(text="In attesa di revisione")

        view = RichiestaView(
            discord_user=interaction.user,
            roblox_id=user_id,
            roblox_username=username
        )

        canale = client.get_channel(CANALE_RICHIESTE_ID)
        messaggio = await canale.send(embed=embed, view=view)
        view.message = messaggio  # salva per modifica dopo

        # interaction.message può essere None, quindi controllo
        if interaction.message:
            await interaction.message.delete()

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

        # Ruoli
        await member.remove_roles(discord.Object(id=TURISTA_ROLE_ID), reason="Accettato come cittadino")
        await member.add_roles(discord.Object(id=CITTADINO_ROLE_ID), reason="Accettato come cittadino")

        # Salvataggio nel DB
        await richieste.insert_one({
            "discord_id": str(member.id),
            "discord_tag": str(member),
            "roblox_id": str(self.roblox_id),
            "roblox_username": self.roblox_username,
            "data": discord.utils.utcnow(),
            "esito": "Accettato",
            "motivazione": None,
            "gestito_da": str(interaction.user)
        })

        esiti = client.get_channel(CANALE_ESITI_ID)
        avatar_url = f"https://www.roblox.com/headshot-thumbnail/image?userId={self.roblox_id}&width=150&height=150&format=png"

        # Embed log esiti
        embed = discord.Embed(
            title="Richiesta - Cittadinanza",
            description=(
                f" **Utente Discord:** {member.mention}\n"
                f" **Roblox ID:** `{self.roblox_id}`\n"
                f" **Username Roblox:** `{self.roblox_username}`\n\n"
                "**Esito:** ✅ **APPROVATO**"
            ),
            color=discord.Color.green()
        )
        embed.set_image(url="https://i.imgur.com/vzjYlCI.png")  # Immagine elegante aggiornata
        embed.set_thumbnail(url=avatar_url)  # Foto profilo Roblox di lato
        embed.set_footer(text=f"Gestito da {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await esiti.send(embed=embed)

        # Aggiorna embed messaggio originale
        embed_orig = self.message.embeds[0]
        embed_orig.color = discord.Color.green()
        embed_orig.set_footer(text="Esito: ACCETTATO ✅")
        await self.message.edit(embed=embed_orig, view=None)

        # DM utente
        try:
            embed_dm = discord.Embed(
                title="✅ Cittadinanza Approvata",
                description="La tua richiesta è stata **approvata**.\nBenvenuto tra i cittadini! 🏛",
                color=discord.Color.green()
            )
            embed_dm.set_image(url="https://i.imgur.com/vzjYlCI.png")
            embed_dm.set_thumbnail(url=avatar_url)
            embed_dm.set_footer(text=f"Gestito da {interaction.user}", icon_url=interaction.user.display_avatar.url)
            await self.discord_user.send(embed=embed_dm)
        except:
            pass

        await interaction.response.send_message("Richiesta approvata.", ephemeral=True)

    @discord.ui.button(label="❌ Rifiuta", style=ButtonStyle.danger)
    async def rifiuta(self, interaction: Interaction, button: Button):
        view_parent = self  # Per mantenere i dati nel modal

        class MotivoRifiutoModal(Modal, title="Motivazione Rifiuto"):
            motivo = TextInput(label="Motivazione", style=TextStyle.paragraph)

            async def on_submit(self, modal_interaction: Interaction):
                avatar_url = f"https://www.roblox.com/headshot-thumbnail/image?userId={view_parent.roblox_id}&width=150&height=150&format=png"
                esiti = client.get_channel(CANALE_ESITI_ID)

                # Aggiorna embed messaggio originale
                embed_orig = view_parent.message.embeds[0]
                embed_orig.color = discord.Color.red()
                embed_orig.set_footer(text=f"Esito: RIFIUTATO ❌ — Motivo: {self.motivo.value}")
                await view_parent.message.edit(embed=embed_orig, view=None)

                # Salvataggio nel DB con motivo rifiuto
                await richieste.insert_one({
                    "discord_id": str(view_parent.discord_user.id),
                    "discord_tag": str(view_parent.discord_user),
                    "roblox_id": str(view_parent.roblox_id),
                    "roblox_username": view_parent.roblox_username,
                    "data": discord.utils.utcnow(),
                    "esito": "Rifiutato",
                    "motivazione": self.motivo.value,
                    "gestito_da": str(modal_interaction.user)
                })

                # Log esito rifiuto
                embed_esiti = discord.Embed(
                    title="Richiesta - Cittadinanza",
                    description=(
                        f" **Roblox ID:** `{view_parent.roblox_id}`\n"
                        f" **Username Roblox:** `{view_parent.roblox_username}`\n\n"
                        f"**Esito:** **RIFIUTATO**\n"
                        f"**Motivo:** {self.motivo.value}"
                    ),
                    color=discord.Color.red()
                )
                embed_esiti.set_image(url="https://i.imgur.com/6r8V5Tu.png")  # Immagine rifiuto sopra
                embed_esiti.set_thumbnail(url=avatar_url)  # Foto profilo Roblox di lato
                embed_esiti.set_footer(text=f"Gestito da {modal_interaction.user}", icon_url=modal_interaction.user.display_avatar.url)
                await esiti.send(embed=embed_esiti)

                # DM utente
                try:
                    embed_dm = discord.Embed(
                        title="❌ Cittadinanza Rifiutata",
                        description=f"Motivo del rifiuto:\n```{self.motivo.value}```",
                        color=discord.Color.red()
                    )
                    embed_dm.set_image(url="https://i.imgur.com/6r8V5Tu.png")
                    embed_dm.set_thumbnail(url=avatar_url)
                    embed_dm.set_footer(text=f"Gestito da {modal_interaction.user}", icon_url=modal_interaction.user.display_avatar.url)
                    await view_parent.discord_user.send(embed=embed_dm)
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
    soggetto = await richieste.find_one({"roblox_username": nome})
    if soggetto:
        # Embed stile richieste cittadinanza
        embed = discord.Embed(
            title="Richiesta - Cittadinanza",
            color=discord.Color.green() if soggetto.get("esito") == "Accettato" else discord.Color.red()
        )
        embed.add_field(name="Nome del richiedente", value=soggetto.get("roblox_username", "N/A"), inline=False)
        embed.add_field(name="Esito", value=soggetto.get("esito", "N/A"), inline=False)
        
        if soggetto.get("esito") == "Rifiutato":
            embed.add_field(name="Motivazione", value=soggetto.get("motivazione", "N/A"), inline=False)

        if soggetto.get("avatar_url"):
            embed.set_thumbnail(url=soggetto["avatar_url"])

        embed.set_footer(
            text=f"Richiesta visionata da {soggetto.get('gestito_da', 'N/A')}",
            icon_url=interaction.user.display_avatar.url
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message("❌ Nessun soggetto trovato con questo nome.", ephemeral=True)

# ===== COMANDO ELIMINA SOGGETTO =====
@app_commands.command(name="elimina_soggetto", description="Elimina un soggetto dal database")
@has_admin_role()
async def elimina_soggetto(interaction: Interaction, nome: str):
    result = await richieste.delete_one({"roblox_username": nome})
    if result.deleted_count > 0:
        await interaction.response.send_message(f"✅ Soggetto **{nome}** eliminato con successo.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Nessun soggetto trovato con questo nome.", ephemeral=True)

@client.event
async def on_ready():
    guild_id = 1400851394595917937  # ID del tuo server
    guild = discord.Object(id=guild_id)

    print(f"🔄 Pulizia comandi per la guild {guild_id}...")
    # Cancella tutti i comandi registrati nella guild
    client.tree.clear_commands(guild=guild)

    # Registra di nuovo i comandi attuali
    synced = await client.tree.sync(guild=guild)

    print(f"✅ Bot connesso come {client.user}")
    print(f"📌 {len(synced)} comandi attivi per la guild {guild_id}:")
    for cmd in synced:
        print(f"  • /{cmd.name} — {cmd.description}")

    print("⚡ Sincronizzazione completata. I comandi sono ora aggiornati istantaneamente nella tua guild.")

# ===== AVVIO =====
client.run(TOKEN)
