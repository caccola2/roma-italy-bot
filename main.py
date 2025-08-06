import os
import discord
import aiohttp
import sqlite3
from discord.ext import commands
from discord import app_commands, Interaction, Embed
from datetime import datetime
import asyncio

# === CONFIGURAZIONE ===
GROUP_ID = 5043872  # ✅ NUOVO GRUPPO per cittadinanza
COOKIE = os.getenv("ROBLOX_COOKIE")
ROMA_TOKEN = os.getenv("ROMA_TOKEN")

CANALE_RICHIESTE = 1402403913826701442
CANALE_LOG = 1402374664659144897
ID_RUOLO_ADMIN = 1226305676708679740

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# === DATABASE ===
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

# === PERMESSI ===
def ha_permessi(user: discord.User) -> bool:
    return any(role.id == ID_RUOLO_ADMIN for role in getattr(user, "roles", []))

# === UTILITY ===
# Funzione per ottenere user_id da username Roblox (API aggiornata)
async def get_user_id(session, username: str) -> int | None:
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": True}
    try:
        async with session.post(url, json=payload, timeout=10) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            users = data.get("data", [])
            if not users:
                return None
            return users[0].get("id")
    except (asyncio.TimeoutError, aiohttp.ClientError):
        return None

# Funzione per verificare se l'utente è nel gruppo Roblox
async def is_user_in_group(session, user_id: int, group_id: int) -> bool:
    url = f"https://groups.roblox.com/v1/users/{user_id}/groups/roles"
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                return False
            data = await resp.json()
            return any(group['group']['id'] == group_id for group in data.get("data", []))
    except (asyncio.TimeoutError, aiohttp.ClientError):
        return False

# === COMANDO: RICHIEDI CITTADINANZA ===
@bot.tree.command(name="richiedi_cittadinanza", description="Invia richiesta per diventare cittadino.")
@app_commands.describe(username="Il tuo username Roblox")
async def richiedi_cittadinanza(interaction: Interaction, username: str):
    try:
        await interaction.response.defer(ephemeral=True)
    except discord.errors.InteractionResponded:
        return
    except discord.errors.NotFound:
        print("Interazione scaduta prima del defer.")
        return

    async with aiohttp.ClientSession() as session:
        user_id = await get_roblox_user_id(session, username)
        if not user_id:
            await interaction.followup.send("❌ Username Roblox non valido o utente non trovato.", ephemeral=True)
            return

        in_group = await check_user_in_group(session, user_id, GROUP_ID)
        if not in_group:
            await interaction.followup.send(f"❌ Non fai parte del gruppo richiesto ({GROUP_ID}).", ephemeral=True)
            return

    # Salvataggio nel DB
    cursor.execute("""
        INSERT OR REPLACE INTO cittadini (user_id, username, roblox_id, data)
        VALUES (?, ?, ?, ?)
    """, (
        str(interaction.user.id),
        username,
        str(user_id),
        datetime.utcnow()
    ))
    db.commit()

    embed = discord.Embed(
        title="📜 Nuova Richiesta di Cittadinanza",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="👤 Utente Discord", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
    embed.add_field(name="🎮 Username Roblox", value=f"`{username}` (`{user_id}`)", inline=False)
    embed.add_field(name="🔗 Profilo", value=f"https://www.roblox.com/users/{user_id}/profile", inline=False)
    embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=420&height=420&format=png")
    embed.set_footer(text="Sistema Cittadinanza")

    canale_log = bot.get_channel(CANALE_LOG)
    if canale_log:
        await canale_log.send(embed=embed)

    await interaction.followup.send("✅ Richiesta di cittadinanza inviata e registrata con successo.", ephemeral=True)

# === EVENTO SYNC ===
@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print("✅ Comandi sincronizzati.")
    except Exception as e:
        print(f"❌ Errore sincronizzazione: {e}")
    print(f"🤖 Bot online come {bot.user}")

# === COMANDO: CERCA CITTADINO ===
@bot.tree.command(name="cerca_cittadino", description="Cerca un cittadino nel database tramite username Roblox.")
@app_commands.describe(username="Username Roblox da cercare")
async def cerca_cittadino(interaction: Interaction, username: str):
    if not ha_permessi(interaction.user):
        await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
        return

    cursor.execute("SELECT * FROM cittadini WHERE username = ?", (username,))
    result = cursor.fetchone()

    if result:
        user_id, username_db, roblox_id, data = result
        embed = Embed(title="📋 Dati Cittadino", color=discord.Color.blue())
        embed.add_field(name="Discord ID", value=user_id, inline=False)
        embed.add_field(name="Roblox Username", value=username_db, inline=False)
        embed.add_field(name="Roblox ID", value=roblox_id, inline=False)
        embed.add_field(name="Registrato il", value=data, inline=False)
        embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={roblox_id}&width=420&height=420&format=png")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message("❌ Nessun cittadino trovato con questo username Roblox.", ephemeral=True)

# === COMANDO: RIMUOVI CITTADINO ===
@bot.tree.command(name="rimuovi_cittadino", description="Rimuovi un cittadino dal database tramite username Roblox.")
@app_commands.describe(username="Username Roblox da rimuovere")
async def rimuovi_cittadino(interaction: Interaction, username: str):
    if not ha_permessi(interaction.user):
        await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
        return

    cursor.execute("DELETE FROM cittadini WHERE username = ?", (username,))
    db.commit()
    await interaction.response.send_message("✅ Cittadino rimosso dal database.", ephemeral=True)

# Avvio
bot.run(ROMA_TOKEN)
