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
@bot.tree.command(name="accept_group", description="Accetta un utente nel gruppo")
@app_commands.checks.has_role(PERMESSI_AUTORIZZATI[0])
async def accept_group(interaction: Interaction, username: str):
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
        payload = {"roleId": 1}  # ID del ruolo base (default)

        async with session.patch(url, json=payload, headers=headers) as r:
            if r.status == 200:
                await interaction.followup.send(f"✅ {username} accettato nel gruppo.", ephemeral=True)
            else:
                data = await r.text()
                await interaction.followup.send(f"❌ Errore accettazione utente: {r.status} {data}", ephemeral=True)

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
