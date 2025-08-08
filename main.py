import os
import discord
from discord import app_commands, Interaction, ButtonStyle, TextStyle
from discord.ui import View, Button, Modal, TextInput, button
from discord.ext import commands
import aiohttp

# ===== CONFIG =====
GROUP_ID = 5043872
CANALE_RICHIESTE_ID = 1402403913826701442
CANALE_ESITI_ID = 1402374664659144897
TURISTA_ROLE_ID = 1226305676708679740
CITTADINO_ROLE_ID = 1226305679398704168
GUILD_ID = 1400851394595917937  # ID della guild usata per la sync (se vuoi locale)
ROMA_TOKEN = os.getenv("ROMA_TOKEN")

# db richieste, ad esempio un motore async MongoDB
richieste = ...  # <-- inserisci qui la tua collection async (motor) o lascia placeholder

# Intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Usa commands.Bot (ha .tree) — mantiene nome client per non cambiare il resto del codice
client = commands.Bot(command_prefix="/", intents=intents)
# client.tree è automaticamente disponibile su commands.Bot

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
        try:
            await member.remove_roles(discord.Object(id=TURISTA_ROLE_ID), reason="Accettato come cittadino")
            await member.add_roles(discord.Object(id=CITTADINO_ROLE_ID), reason="Accettato come cittadino")
        except Exception as e:
            await interaction.response.send_message(f"Errore nella gestione ruoli: {e}", ephemeral=True)
            return

        # Salvataggio esito nel DB
        # ATTENZIONE: richieste deve essere la tua collection motor.AsyncIOMotorCollection o funzione equivalente
        try:
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
        except Exception:
            # Se non vuoi che un errore DB blocchi tutto, lo silenziamo qui
            pass

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
        embed.set_image(url="https://i.imgur.com/vzjYlCI.png")
        embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text=f"Gestito da {interaction.user}", icon_url=interaction.user.display_avatar.url)
        if esiti:
            await esiti.send(embed=embed)

        # Aggiorna embed messaggio originale
        if self.message and self.message.embeds:
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
        except Exception:
            pass

        await interaction.response.send_message("Richiesta approvata.", ephemeral=True)

    @button(label="❌ Rifiuta", style=ButtonStyle.danger)
    async def rifiuta(self, interaction: Interaction, button: Button):
        view_parent = self

        class MotivoRifiutoModal(Modal, title="Motivazione Rifiuto"):
            motivo = TextInput(label="Motivazione", style=TextStyle.paragraph, required=True)

            async def on_submit(self, modal_interaction: Interaction):
                avatar_url = f"https://www.roblox.com/headshot-thumbnail/image?userId={view_parent.roblox_id}&width=150&height=150&format=png"
                esiti = client.get_channel(CANALE_ESITI_ID)

                # Aggiorna embed messaggio originale
                if view_parent.message and view_parent.message.embeds:
                    embed_orig = view_parent.message.embeds[0]
                    embed_orig.color = discord.Color.red()
                    embed_orig.set_footer(text=f"Esito: RIFIUTATO ❌ — Motivo: {self.motivo.value}")
                    await view_parent.message.edit(embed=embed_orig, view=None)

                # Salvataggio nel DB con motivo rifiuto
                try:
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
                except Exception:
                    pass

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
                if esiti:
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
                except Exception:
                    pass

                await modal_interaction.response.send_message("Richiesta rifiutata.", ephemeral=True)

        await interaction.response.send_modal(MotivoRifiutoModal())

# ===== COMANDO SLASH RICHIESTA =====
@client.tree.command(name="richiesta_cittadinanza", description="Invia richiesta cittadinanza Roblox")
@app_commands.describe(nome_roblox="Inserisci il tuo nome utente Roblox")
async def richiesta(interaction: Interaction, nome_roblox: str):
    await interaction.response.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:
        # Controlla esistenza utente Roblox
        async with session.post("https://users.roblox.com/v1/usernames/users", json={"usernames": [nome_roblox]}) as resp:
            data = await resp.json()
            if not data.get("data"):
                await interaction.followup.send("❌ Utente Roblox non trovato.", ephemeral=True)
                return
            user_data = data["data"][0]
            user_id = user_data["id"]

        # Controlla se l’utente è nel gruppo Roblox
        async with session.get(f"https://groups.roblox.com/v1/users/{user_id}/groups/roles") as resp:
            data = await resp.json()
            gruppi = data.get("data", [])
            if not any(group["group"]["id"] == GROUP_ID for group in gruppi):
                await interaction.followup.send("❌ Non fai parte del gruppo Roblox, richiesta rifiutata automaticamente.", ephemeral=True)
                return

    embed = discord.Embed(title="📥 Richiesta Cittadinanza", color=discord.Color.blue())
    embed.add_field(name="Discord", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
    embed.add_field(name="Roblox", value=f"{nome_roblox} (ID: {user_id})", inline=False)
    embed.set_footer(text="In attesa di revisione")

    view = RichiestaView(
        discord_user=interaction.user,
        roblox_id=user_id,
        roblox_username=nome_roblox
    )

    canale = client.get_channel(CANALE_RICHIESTE_ID)
    if canale is None:
        # tenta il fetch se get_channel fallisce (es. bot appena connesso)
        try:
            canale = await client.fetch_channel(CANALE_RICHIESTE_ID)
        except Exception:
            await interaction.followup.send("Errore: canale richieste non trovato.", ephemeral=True)
            return

    messaggio = await canale.send(embed=embed, view=view)
    view.message = messaggio

    await interaction.followup.send("✅ Richiesta inviata con successo.", ephemeral=True)

# ===== ON_READY + SYNC =====
@client.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    print(f"🔄 Bot connesso come {client.user} — sincronizzo comandi per guild {GUILD_ID}...")

    # Pulizia e sync comandi per la guild (evita mismatch)
    try:
        await client.tree.clear_commands(guild=guild)
    except Exception:
        # se fallisce, ignoriamo e proviamo a sincronizzare comunque
        pass

    try:
        synced = await client.tree.sync(guild=guild)
    except Exception as e:
        print(f"⚠️ Errore sync comandi: {e}")
        synced = []

    print(f"✅ Sincronizzazione completata. {len(synced)} comandi attivi per la guild {GUILD_ID}.")

# ===== AVVIO =====
if not ROMA_TOKEN:
    raise RuntimeError("ROMA_TOKEN non impostato nell'ambiente. Aggiungi la variabile d'ambiente ROMA_TOKEN.")

client.run(ROMA_TOKEN)
