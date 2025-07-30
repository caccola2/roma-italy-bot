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
class RichiestaView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user

    @discord.ui.button(label="Invia Richiesta", style=discord.ButtonStyle.green, emoji="📩")
    async def invia(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("Questa richiesta non è per te.", ephemeral=True)
            return

        embed_richiesta = Embed(
            title="📨 Nuova Richiesta di Cittadinanza",
            description=f"**Utente:** {self.user.mention} ({self.user.name})\n**ID:** `{self.user.id}`",
            color=discord.Color.blurple()
        )
        canale = bot.get_channel(CANALE_RICHIESTE_ID)
        view = ModerazioneView(self.user)
        await canale.send(embed=embed_richiesta, view=view)
        await interaction.response.send_message("✅ Richiesta inviata con successo!", ephemeral=True)
        self.stop()

class ModerazioneView(discord.ui.View):
    def __init__(self, richiedente):
        super().__init__(timeout=None)
        self.richiedente = richiedente

    @discord.ui.button(label="Accetta", style=discord.ButtonStyle.green)
    async def accetta(self, interaction: Interaction, button: discord.ui.Button):
        embed_ok = Embed(
            title="📨 Esito cittadinanza",
            description="Ciao 👋\nLa tua richiesta di cittadinanza è stata accettata! 🟢",
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
    async def rifiuta(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MotivazioneRifiutoModal(self.richiedente))

class MotivazioneRifiutoModal(discord.ui.Modal, title="Motivo del rifiuto"):
    motivo = discord.ui.TextInput(label="Scrivi la motivazione", style=discord.TextStyle.paragraph)

    def __init__(self, utente):
        super().__init__()
        self.utente = utente

    async def on_submit(self, interaction: Interaction):
        embed_ko = Embed(
            title="📨 Esito cittadinanza",
            description="Ciao 👋\nLa tua richiesta di cittadinanza è stata **rifiutata**.",
            color=discord.Color.red()
        )
        embed_ko.add_field(name="Motivo del rifiuto", value=self.motivo.value, inline=False)
        try:
            await self.utente.send(embed=embed_ko)
        except:
            await interaction.response.send_message("❌ Impossibile inviare DM all'utente.", ephemeral=True)
            return
        await interaction.response.send_message("❌ Richiesta rifiutata con successo.", ephemeral=True)

@bot.tree.command(name="richiesta_cittadinanza", description="Invia richiesta di cittadinanza")
async def richiesta_cittadinanza(interaction: Interaction):
    embed = Embed(
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
