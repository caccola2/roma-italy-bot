import os
import discord
import aiohttp
import sqlite3
from datetime import datetime
from discord.ext import commands
from discord import app_commands, Interaction, Embed, User
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
bot = commands.Bot(command_prefix="!", intents=intents)
GROUP_ID = 5043872
PERMESSI_AUTORIZZATI = [1389416705943666840]  # ID del ruolo con permessi
COOKIE = os.getenv("ROBLOX_COOKIE")

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

# ──────────────────────────────
# COMANDI GRUPPO
# ──────────────────────────────
@bot.tree.command(name="set_group_role", description="Imposta un ruolo specifico nel gruppo Roblox per un utente.")
@has_required_role()
@app_commands.describe(username="Username dell'utente da modificare", role_name="Nome del ruolo da assegnare")
async def set_group_role(interaction: discord.Interaction, username: str, role_name: str):
    await interaction.response.defer(ephemeral=True)
    user_id = await get_user_id(username)
    if user_id is None:
        await interaction.followup.send("❌ Errore: Username non trovato.", ephemeral=True)
        return

    role_id = await get_role_id_by_name(role_name)
    if role_id is None:
        await interaction.followup.send("❌ Errore: Nome ruolo non valido.", ephemeral=True)
        return

    headers = {
        "Cookie": f".ROBLOSECURITY={ROBLOX_COOKIE}",
        "Content-Type": "application/json",
        "X-CSRF-TOKEN": ""
    }

    async with aiohttp.ClientSession() as session:
        # Ottieni il token CSRF
        async with session.post("https://auth.roblox.com/v2/logout", headers=headers) as r:
            headers["X-CSRF-TOKEN"] = r.headers.get("x-csrf-token", "")

        async with session.patch(f"https://groups.roblox.com/v1/groups/{GROUP_ID}/users/{user_id}",
                                 headers=headers,
                                 json={"roleId": role_id}) as response:
            if response.status == 200:
                await interaction.followup.send(f"✅ Ruolo impostato con successo per **{username}**.", ephemeral=True)
            else:
                error = await response.text()
                await interaction.followup.send(f"❌ Errore impostazione ruolo: {response.status} {error}", ephemeral=True)

@bot.tree.command(name="kick_group", description="Espelle un utente dal gruppo")
@app_commands.checks.has_role(PERMESSI_AUTORIZZATI[0])
async def kick_group(interaction: Interaction, username: str):
    await interaction.response.defer(ephemeral=True)
    async with aiohttp.ClientSession() as session:
        user_id = await get_user_id(session, username)
        if not user_id:
            return await interaction.followup.send("❌ Utente non trovato.", ephemeral=True)

        csrf_token = await get_csrf_token(session)
        headers = {
            "Cookie": f".ROBLOSECURITY={COOKIE}",
            "x-csrf-token": csrf_token,
            "Content-Type": "application/json"
        }

        url = f"https://groups.roblox.com/v1/groups/{GROUP_ID}/users/{user_id}"
        payload = {"roleId": 0}  # Espulsione

        async with session.patch(url, json=payload, headers=headers) as r:
            if r.status == 200:
                await interaction.followup.send(f"✅ {username} espulso dal gruppo.", ephemeral=True)
            else:
                data = await r.text()
                await interaction.followup.send(f"❌ Errore espulsione: {r.status} {data}", ephemeral=True)

@bot.tree.command(name="ban_group", description="Banna un utente dal gruppo")
@app_commands.checks.has_role(PERMESSI_AUTORIZZATI[0])
async def ban_group(interaction: Interaction, username: str):
    await interaction.response.defer(ephemeral=True)
    async with aiohttp.ClientSession() as session:
        user_id = await get_user_id(session, username)
        if not user_id:
            return await interaction.followup.send("❌ Utente non trovato.", ephemeral=True)

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
# /richiesta-cittadinanza
# ──────────────────────────────
CANALE_RICHIESTE_ID = 1400175826804412536

class RichiestaView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user

    @discord.ui.button(label="Invia Richiesta", style=discord.ButtonStyle.green, emoji="📩")
    async def invia(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("Questa richiesta non è per te.", ephemeral=True)
            return

        embed_richiesta = discord.Embed(
            title="📨 Nuova Richiesta di Cittadinanza",
            description=f"**Utente:** {self.user.mention} ({self.user.name})\n**ID:** `{self.user.id}`",
            color=discord.Color.blurple()
        )
        view_moderazione = ModerazioneView(self.user)
        canale = bot.get_channel(CANALE_RICHIESTE_ID)
        await canale.send(embed=embed_richiesta, view=view_moderazione)
        await interaction.response.send_message("✅ Richiesta inviata con successo!", ephemeral=True)
        self.stop()

class ModerazioneView(discord.ui.View):
    def __init__(self, richiedente):
        super().__init__(timeout=None)
        self.richiedente = richiedente

    @discord.ui.button(label="Accetta", style=discord.ButtonStyle.green)
    async def accetta(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed_ok = discord.Embed(
            title="📨 Esito cittadinanza",
            description=f"Ciao 👋\nLa tua richiesta di cittadinanza è stata accettata! 🟢",
            color=discord.Color.green()
        )
        try:
            await self.richiedente.send(embed=embed_ok)
        except:
            await interaction.response.send_message("❌ Impossibile inviare DM all'utente.", ephemeral=True)
            return
        await interaction.response.send_message("✅ Richiesta accettata.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Rifiuta", style=discord.ButtonStyle.red)
    async def rifiuta(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MotivazioneRifiutoModal(self.richiedente))

class MotivazioneRifiutoModal(discord.ui.Modal, title="Motivo del rifiuto"):
    motivo = discord.ui.TextInput(label="Scrivi la motivazione", style=discord.TextStyle.paragraph)

    def __init__(self, utente):
        super().__init__()
        self.utente = utente

    async def on_submit(self, interaction: discord.Interaction):
        embed_ko = discord.Embed(
            title="📨 Esito cittadinanza",
            description="Ciao 👋\nLa tua richiesta di cittadinanza è stata **rifiutata**. 📩",
            color=discord.Color.red()
        )
        embed_ko.add_field(name="Motivo del rifiuto", value=f"{self.motivo.value}", inline=False)
        try:
            await self.utente.send(embed=embed_ko)
        except:
            await interaction.response.send_message("❌ Impossibile inviare DM all'utente.", ephemeral=True)
            return
        await interaction.response.send_message("❌ Richiesta rifiutata con successo.", ephemeral=True)

@bot.tree.command(name="richiesta_cittadinanza", description="Invia richiesta di cittadinanza")
async def richiesta_cittadinanza(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📨 Richiesta Cittadinanza",
        description="Per fare richiesta, assicurati di rispettare i seguenti requisiti:",
        color=discord.Color.blue()
    )
    embed.add_field(name="✅ Requisiti:", value="- Essere in un gruppo Roblox\n- Essere verificato su Discord", inline=False)
    await interaction.user.send(embed=embed, view=RichiestaView(interaction.user))
    await interaction.response.send_message("📩 Ti ho inviato un messaggio privato con i dettagli.", ephemeral=True)

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
