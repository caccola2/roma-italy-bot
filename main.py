import discord
from discord import app_commands, Interaction
from discord.ui import View, Button
from discord.ui import button
from discord import ButtonStyle, TextStyle, TextInput, Modal
import aiohttp
import asyncio

# Costanti da definire
GROUP_ID = 5043872               # ID gruppo Roblox
CANALE_RICHIESTE_ID = 1402403913826701442
CANALE_ESITI_ID = 1402374664659144897
TURISTA_ROLE_ID = 1226305676708679740
CITTADINO_ROLE_ID = 1226305679398704168

# db richieste, ad esempio un motore async MongoDB
richieste = ...  # la tua collection/motore db async

client = discord.Client(intents=discord.Intents.all())
tree = app_commands.CommandTree(client)

# ===== VIEW CON PULSANTI =====
class RichiestaView(View):
    def __init__(self, discord_user, roblox_id, roblox_username):
        super().__init__(timeout=None)
        self.discord_user = discord_user
        self.roblox_id = roblox_id
        self.roblox_username = roblox_username
        self.message = None

    @button(label="✅ Accetta", style=ButtonStyle.success)
    async def accetta(self, interaction: Interaction, button: Button):
        member = interaction.guild.get_member(self.discord_user.id)
        if not member:
            await interaction.response.send_message("❌ Utente non trovato nel server.", ephemeral=True)
            return

        # Gestione ruoli
        await member.remove_roles(discord.Object(id=TURISTA_ROLE_ID), reason="Accettato come cittadino")
        await member.add_roles(discord.Object(id=CITTADINO_ROLE_ID), reason="Accettato come cittadino")

        # Salvataggio esito nel DB
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
        embed.set_image(url="https://i.imgur.com/vzjYlCI.png")
        embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text=f"Gestito da {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await esiti.send(embed=embed)

        # Aggiorna embed nel messaggio originale
        embed_orig = self.message.embeds[0]
        embed_orig.color = discord.Color.green()
        embed_orig.set_footer(text="Esito: ACCETTATO ✅")
        await self.message.edit(embed=embed_orig, view=None)

        # DM all’utente
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

    @button(label="❌ Rifiuta", style=ButtonStyle.danger)
    async def rifiuta(self, interaction: Interaction, button: Button):
        view_parent = self

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

                # Salvataggio DB con motivazione rifiuto
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
                embed_esiti.set_image(url="https://i.imgur.com/6r8V5Tu.png")
                embed_esiti.set_thumbnail(url=avatar_url)
                embed_esiti.set_footer(text=f"Gestito da {modal_interaction.user}", icon_url=modal_interaction.user.display_avatar.url)
                await esiti.send(embed=embed_esiti)

                # DM all’utente
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

# ===== COMANDO SLASH RICHIESTA =====
@tree.command(name="richiesta_cittadinanza", description="Invia richiesta cittadinanza Roblox")
@app_commands.describe(nome_roblox="Inserisci il tuo nome utente Roblox")
async def richiesta(interaction: Interaction, nome_roblox: str):
    await interaction.response.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:
        # Controlla esistenza utente Roblox
        async with session.post("https://users.roblox.com/v1/usernames/users", json={"usernames": [nome_roblox]}) as resp:
            data = await resp.json()
            if not data["data"]:
                await interaction.followup.send("❌ Utente Roblox non trovato.", ephemeral=True)
                return
            user_data = data["data"][0]
            user_id = user_data["id"]

        # Controlla se l’utente è nel gruppo Roblox
        async with session.get(f"https://groups.roblox.com/v1/users/{user_id}/groups/roles") as resp:
            data = await resp.json()
            if not any(group["group"]["id"] == GROUP_ID for group in data.get("data", [])):
                await interaction.followup.send("❌ Non fai parte del gruppo Roblox, richiesta rifiutata automaticamente.", ephemeral=True)
                return

    embed = discord.Embed(title="📥 Richiesta Cittadinanza", color=discord.Color.blue())
    embed.add_field(name="Discord", value=f"{interaction.user.mention} ({interaction.user.id})")
    embed.add_field(name="Roblox", value=f"{nome_roblox} (ID: {user_id})")
    embed.set_footer(text="In attesa di revisione")

    view = RichiestaView(
        discord_user=interaction.user,
        roblox_id=user_id,
        roblox_username=nome_roblox
    )

    canale = client.get_channel(CANALE_RICHIESTE_ID)
    messaggio = await canale.send(embed=embed, view=view)
    view.message = messaggio

    await interaction.followup.send("✅ Richiesta inviata con successo.", ephemeral=True)
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
