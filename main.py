import os
import discord
import aiohttp
import sqlite3
from discord.ext import commands
from discord import app_commands, Interaction, Embed
from datetime import datetime

# Configurazione
GROUP_ID = 8730810
COOKIE = os.getenv("ROBLOX_COOKIE")
CANALE_RICHIESTE = 1402403913826701442
CANALE_LOG = 1402374664659144897
ID_RUOLO_TURISTA = 1400852869489496185
ID_RUOLO_CITTADINO = 1400856967534215188
ID_RUOLO_ADMIN = 1226305676708679740

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# Controllo permessi (esempio, implementa come ti serve)
def ha_permessi(user: discord.User) -> bool:
    # Modifica con la logica di permessi vera, ad esempio ruoli o ID utenti admin
    return any(role.id == ID_RUOLO_ADMIN for role in getattr(user, "roles", []))

# Evento on_ready → sync comandi
@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print("✅ Comandi sincronizzati.")
    except Exception as e:
        print(f"❌ Errore sincronizzazione: {e}")
    print(f"🤖 Bot online come {bot.user}")

# Database
db = sqlite3.connect("cittadini.db")
cursor = db.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS cittadini (
        user_id TEXT PRIMARY KEY,
        username TEXT,
        roblox_id TEXT,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
db.commit()

import aiohttp

GROUP_ID = 5043872  # Sostituisci con l'ID corretto del tuo gruppo

# UTILITY FUNCTION
async def get_user_id(session, username):
    """
    Restituisce l'ID utente Roblox dato un username, usando l'endpoint aggiornato.
    """
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": False}
    headers = {"Content-Type": "application/json"}

    try:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status != 200:
                return None
            data = await response.json()
            if "data" in data and data["data"]:
                return data["data"][0]["id"]
            return None
    except aiohttp.ClientError as e:
        print(f"Errore durante il recupero dell'ID utente: {e}")
        return None

async def is_user_in_group(user_id):
    """
    Verifica se l'utente è in un gruppo specifico dato il suo user ID.
    """
    url = f"https://groups.roblox.com/v1/users/{user_id}/groups"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return False
            groups = await resp.json()
            return any(group['id'] == GROUP_ID for group in groups['data'])

async def get_role_id_by_name(role_name):
    """
    Restituisce l'ID del ruolo nel gruppo dato il nome del ruolo.
    """
    url = f"https://groups.roblox.com/v1/groups/{GROUP_ID}/roles"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                return None
            data = await response.json()
            for role in data.get("roles", []):
                if role["name"].lower() == role_name.lower():
                    return role["id"]
    return None

async def get_csrf_token(session):
    """
    Ottiene il token CSRF necessario per eseguire operazioni protette (es. cambio ruolo, esilio).
    """
    async with session.post("https://auth.roblox.com/v2/logout") as resp:
        return resp.headers.get("x-csrf-token")

# COMANDO: RICHIESTA CITTADINANZA
@bot.tree.command(name="richiedi_cittadinanza", description="Invia richiesta per diventare cittadino.")
@app_commands.describe(username="Il tuo username Roblox")
async def richiedi_cittadinanza(interaction: Interaction, username: str):
    await interaction.response.defer(ephemeral=True)

    async with aiohttp.ClientSession() as session:
        user_id = await get_user_id(session, username)
        if not user_id:
            await interaction.followup.send("❌ Username non valido.", ephemeral=True)
            return

        if not await is_user_in_group(user_id):
            embed = Embed(title="❌ Richiesta Rifiutata", color=discord.Color.red(), timestamp=datetime.utcnow())
            embed.add_field(name="Utente Discord", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
            embed.add_field(name="Username Roblox", value=f"{username} ({user_id})", inline=False)
            embed.add_field(name="Esito", value="❌ Rifiutata: Utente non presente nel Gruppo Roblox", inline=False)
            embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=420&height=420&format=png")
            canale_log = bot.get_channel(CANALE_LOG)
            if canale_log:
                await canale_log.send(embed=embed)
            await interaction.followup.send("❌ Richiesta rifiutata automaticamente.", ephemeral=True)
            return

    embed = Embed(title="📝 Nuova Richiesta di Cittadinanza", color=discord.Color.blurple(), timestamp=datetime.utcnow())
    embed.add_field(name="Utente Discord", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
    embed.add_field(name="Username Roblox", value=f"{username} ({user_id})", inline=False)
    embed.add_field(name="Link Profilo", value=f"https://www.roblox.com/users/{user_id}/profile", inline=False)
    embed.add_field(name="Esito", value="⏳ In attesa di revisione", inline=False)
    embed.set_footer(text="Sistema Cittadinanza")
    embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=420&height=420&format=png")

    canale = bot.get_channel(CANALE_RICHIESTE)
    if canale:
        await canale.send(embed=embed)
        await interaction.followup.send("✅ Richiesta inviata correttamente.", ephemeral=True)
    else:
        await interaction.followup.send("❌ Errore: canale richieste non trovato.", ephemeral=True)

# COMANDO: SET GROUP ROLE (con controllo permessi)
@bot.tree.command(name="set_group_role", description="Imposta un ruolo Roblox a un utente.")
@app_commands.describe(username="Username", role_name="Nome del ruolo Roblox")
async def set_group_role(interaction: Interaction, username: str, role_name: str):
    if not ha_permessi(interaction.user):
        await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    async with aiohttp.ClientSession() as session:
        user_id = await get_user_id(session, username)
        role_id = await get_role_id_by_name(role_name)
        if not user_id or not role_id:
            await interaction.followup.send("❌ Username o ruolo non valido.", ephemeral=True)
            return

        csrf_token = await get_csrf_token(session)
        headers = {
            "Cookie": f".ROBLOSECURITY={COOKIE}",
            "X-CSRF-TOKEN": csrf_token,
            "Content-Type": "application/json"
        }
        url = f"https://groups.roblox.com/v1/groups/{GROUP_ID}/users/{user_id}"
        async with session.patch(url, headers=headers, json={"roleId": role_id}) as response:
            if response.status == 200:
                await interaction.followup.send(f"✅ Ruolo aggiornato per **{username}**.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Errore: {response.status}", ephemeral=True)

# COMANDO: KICK GROUP (con controllo permessi)
@bot.tree.command(name="kick_group", description="Espelle un utente dal gruppo Roblox.")
@app_commands.describe(username="Username da espellere")
async def kick_group(interaction: Interaction, username: str):
    if not ha_permessi(interaction.user):
        await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
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
            "X-CSRF-TOKEN": csrf_token
        }
        url = f"https://groups.roblox.com/v1/groups/{GROUP_ID}/users/{user_id}"
        async with session.delete(url, headers=headers) as response:
            if response.status == 200:
                await interaction.followup.send(f"✅ {username} espulso dal gruppo.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Errore: {response.status}", ephemeral=True)

# Avvio
bot.run(os.getenv("ROMA_TOKEN"))

