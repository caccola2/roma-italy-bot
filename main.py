import os
import discord
import aiohttp
import sqlite3
from datetime import datetime
from discord.ext import commands
from discord import app_commands, Interaction, Embed
from flask import Flask
from threading import Thread

# ──────────────────────────────
# FLASK KEEP-ALIVE
# ──────────────────────────────
app = Flask('')

@app.route('/')
def home():
    return "Bot attivo."

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

# ──────────────────────────────
# CONFIGURAZIONE
# ──────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
GROUP_ID = 5043872
PERMESSI_AUTORIZZATI = [1389416705943666840]
COOKIE = os.getenv("ROBLOX_COOKIE")
CANALE_RICHIESTE_ID = 1400175826804412536

# ──────────────────────────────
# UTILITY
# ──────────────────────────────
def ha_permessi(member):
    return any(role.id in PERMESSI_AUTORIZZATI for role in member.roles)

async def get_user_id(session, username):
    url = "https://users.roblox.com/v1/usernames/users"
    async with session.post(url, json={"usernames": [username], "excludeBannedUsers": False}) as resp:
        data = await resp.json()
        return data["data"][0]["id"] if data.get("data") else None

async def get_csrf_token(session):
    async with session.post("https://auth.roblox.com/v2/logout") as resp:
        return resp.headers.get("x-csrf-token")

async def get_role_id_by_name(role_name):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://groups.roblox.com/v1/groups/{GROUP_ID}/roles") as r:
            data = await r.json()
            for role in data.get("roles", []):
                if role["name"].lower() == role_name.lower():
                    return role["id"]
            return None

# ──────────────────────────────
# COMANDI GRUPPO
# ──────────────────────────────
@bot.tree.command(name="set_group_role", description="Imposta un ruolo nel gruppo Roblox per un utente.")
@app_commands.describe(username="Username dell'utente", role_name="Nome del ruolo")
async def set_group_role(interaction: Interaction, username: str, role_name: str):
    if not ha_permessi(interaction.user):
        await interaction.response.send_message("❌ Non hai i permessi per usare questo comando.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    async with aiohttp.ClientSession() as session:
        user_id = await get_user_id(session, username)
        if not user_id:
            await interaction.followup.send("❌ Username non trovato.", ephemeral=True)
            return

        role_id = await get_role_id_by_name(role_name)
        if not role_id:
            await interaction.followup.send("❌ Nome ruolo non valido.", ephemeral=True)
            return

        csrf_token = await get_csrf_token(session)
        headers = {
            "Cookie": f".ROBLOSECURITY={COOKIE}",
            "X-CSRF-TOKEN": csrf_token,
            "Content-Type": "application/json"
        }

        url = f"https://groups.roblox.com/v1/groups/{GROUP_ID}/users/{user_id}"
        payload = {"roleId": role_id}

        async with session.patch(url, headers=headers, json=payload) as response:
            if response.status == 200:
                await interaction.followup.send(f"✅ Ruolo impostato con successo per **{username}**.", ephemeral=True)
            else:
                error = await response.text()
                await interaction.followup.send(f"❌ Errore impostazione ruolo: {response.status} {error}", ephemeral=True)

@bot.tree.command(name="kick_group", description="Espelle un utente dal gruppo.")
@app_commands.describe(username="Username da espellere")
async def kick_group(interaction: Interaction, username: str):
    if not ha_permessi(interaction.user):
        await interaction.response.send_message("❌ Non hai i permessi per usare questo comando.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    async with aiohttp.ClientSession() as session:
        user_id = await get_user_id(session, username)
        if not user_id:
            await interaction.followup.send("❌ Utente non trovato.", ephemeral=True)
            return

        csrf_token = await get_csrf_token(session)
        headers = {
            "Cookie": f".ROBLOSECURITY={COOKIE}",
            "x-csrf-token": csrf_token,
            "Content-Type": "application/json"
        }

        url = f"https://groups.roblox.com/v1/groups/{GROUP_ID}/users/{user_id}"
        payload = {"roleId": 0}

        async with session.patch(url, headers=headers, json=payload) as r:
            if r.status == 200:
                await interaction.followup.send(f"✅ {username} espulso dal gruppo.", ephemeral=True)
            else:
                data = await r.text()
                await interaction.followup.send(f"❌ Errore espulsione: {r.status} {data}", ephemeral=True)

@bot.tree.command(name="ban_group", description="Banna un utente dal gruppo.")
@app_commands.describe(username="Username da bannare")
async def ban_group(interaction: Interaction, username: str):
    if not ha_permessi(interaction.user):
        await interaction.response.send_message("❌ Non hai i permessi per usare questo comando.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    async with aiohttp.ClientSession() as session:
        user_id = await get_user_id(session, username)
        if not user_id:
            await interaction.followup.send("❌ Utente non trovato.", ephemeral=True)
            return

        csrf_token = await get_csrf_token(session)
        headers = {
            "Cookie": f".ROBLOSECURITY={COOKIE}",
            "x-csrf-token": csrf_token,
            "Content-Type": "application/json"
        }

        url = f"https://groups.roblox.com/v1/users/{user_id}/groups/{GROUP_ID}"

        async with session.delete(url, headers=headers) as r:
            if r.status == 200:
                await interaction.followup.send(f"✅ {username} bannato dal gruppo.", ephemeral=True)
            else:
                data = await r.text()
                await interaction.followup.send(f"❌ Errore ban: {r.status} {data}", ephemeral=True)

# ──────────────────────────────
# RICHIESTA CITTADINANZA
# ──────────────────────────────
class RichiestaCittadinanzaView(discord.ui.View):
    def __init__(self, richiedente):
        super().__init__(timeout=None)
        self.richiedente = richiedente

    @discord.ui.button(label="📨 Invia Richiesta", style=discord.ButtonStyle.success)
    async def invia_richiesta(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.richiedente:
            await interaction.response.send_message("❌ Solo l'utente che ha richiesto la cittadinanza può usare questo pulsante.", ephemeral=True)
            return

        await interaction.message.delete()  # Elimina il messaggio DM

        embed = discord.Embed(
            title="📥 Nuova Richiesta di Cittadinanza",
            description=f"**Utente:** {self.richiedente.mention}\n**ID:** `{self.richiedente.id}`",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=self.richiedente.display_avatar.url)
        embed.set_footer(text="Esamina la richiesta e scegli un'azione.")

        view = GestioneRichiestaView(self.richiedente)

        ID_CANALE = 123456789012345678  # <-- Sostituisci con l'ID del canale corretto
        canale = interaction.client.get_channel(ID_CANALE)

        if canale is None:
            await interaction.response.send_message("❌ Errore interno: canale di destinazione non trovato.", ephemeral=True)
            return

        messaggio = await canale.send(embed=embed, view=view)
        view.messaggio = messaggio  # Salva per aggiornare dopo
        await interaction.response.send_message("✅ Richiesta inviata correttamente.", ephemeral=True)

class GestioneRichiestaView(discord.ui.View):
    def __init__(self, richiedente):
        super().__init__(timeout=None)
        self.richiedente = richiedente
        self.messaggio = None

    @discord.ui.button(label="✅ Accetta", style=discord.ButtonStyle.success)
    async def accetta(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed_dm = discord.Embed(
            title="🏛️ Cittadinanza Approvata",
            description="La tua richiesta di cittadinanza è stata **approvata**! Benvenuto/a ufficialmente.",
            color=discord.Color.green()
        )
        await self.richiedente.send(embed=embed_dm)

        embed_canale = self.messaggio.embeds[0]
        embed_canale.add_field(name="Esito", value="✅ Accettato", inline=False)
        embed_canale.color = discord.Color.green()
        await self.messaggio.edit(embed=embed_canale, view=None)

        await interaction.response.send_message("Hai accettato la richiesta ✅", ephemeral=True)

    @discord.ui.button(label="❌ Rifiuta", style=discord.ButtonStyle.danger)
    async def rifiuta(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MotivazioneRifiutoModal(self))

class MotivazioneRifiutoModal(discord.ui.Modal, title="Motivazione del Rifiuto"):
    motivazione = discord.ui.TextInput(
        label="Motivo del rifiuto",
        placeholder="Spiega il motivo del rifiuto...",
        style=discord.TextStyle.paragraph,
        required=True
    )

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        embed_dm = discord.Embed(
            title="🏛️ Cittadinanza Rifiutata",
            description="La tua richiesta di cittadinanza è stata **rifiutata**.",
            color=discord.Color.red()
        )
        embed_dm.add_field(name="Motivazione", value=self.motivazione.value, inline=False)
        await self.view.richiedente.send(embed=embed_dm)

        embed_canale = self.view.messaggio.embeds[0]
        embed_canale.add_field(name="Esito", value="❌ Rifiutato", inline=False)
        embed_canale.add_field(name="Motivazione", value=self.motivazione.value, inline=False)
        embed_canale.color = discord.Color.red()
        await self.view.messaggio.edit(embed=embed_canale, view=None)

        await interaction.response.send_message("Hai rifiutato la richiesta ❌", ephemeral=True)

@bot.tree.command(name="richiesta_cittadinanza", description="Invia una richiesta per ottenere la cittadinanza.")
async def richiesta_cittadinanza(interaction: discord.Interaction):
    try:
        await interaction.response.send_message("📩 Ti ho inviato un messaggio privato con i dettagli.", ephemeral=True)
        embed = discord.Embed(
            title="Richiesta Cittadinanza 🏛️",
            description=(
                "**Requisiti per ottenere la cittadinanza:**\n"
                "- Essere presenti nel Gruppo Roblox\n"
                "- Essere Verificati nel Server Discord\n"
            ),
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Premi il pulsante qui sotto per inviare la richiesta.")
        view = RichiestaCittadinanzaView(interaction.user)
        await interaction.user.send(embed=embed, view=view)
    except discord.Forbidden:
        await interaction.followup.send("❌ Non posso inviarti un messaggio privato. Controlla le impostazioni della privacy.", ephemeral=True)

# ──────────────────────────────
# EVENTO READY
# ──────────────────────────────
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Bot pronto. Comandi sincronizzati: {len(synced)}")
    except Exception as e:
        print(f"[ERRORE SYNC]: {e}")

# ──────────────────────────────
# AVVIO BOT
# ──────────────────────────────
if __name__ == "__main__":
    token = os.getenv("ROMA_TOKEN")
    if token:
        bot.run(token)
    else:
        print("[ERRORE] ROMA_TOKEN mancante.")
