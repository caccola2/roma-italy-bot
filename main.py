import os
import discord
import aiohttp
import sqlite3
from discord.ext import commands
from discord import app_commands, Interaction, Embed
from datetime import datetime

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
async def get_user_id(session, username):
    url = f"https://api.roblox.com/users/get-by-username?username={username}"
    async with session.get(url) as response:
        data = await response.json()
        return data.get("Id") if response.status == 200 else None

async def is_user_in_group(user_id):
    url = f"https://groups.roblox.com/v1/users/{user_id}/groups"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return False
            groups = await resp.json()
            return any(group['id'] == GROUP_ID for group in groups['data'])

async def get_csrf_token(session):
    async with session.post("https://auth.roblox.com/v2/logout") as resp:
        return resp.headers.get("x-csrf-token")

# === EVENTO SYNC ===
@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print("✅ Comandi sincronizzati.")
    except Exception as e:
        print(f"❌ Errore sincronizzazione: {e}")
    print(f"🤖 Bot online come {bot.user}")

# === COMANDO: RICHIEDI CITTADINANZA ===
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
            await interaction.followup.send("❌ Non fai parte del gruppo richiesto.", ephemeral=True)
            return

    # ✅ Inserimento nel DB dopo approvazione automatica
    cursor.execute("INSERT OR REPLACE INTO cittadini (user_id, username, roblox_id, data) VALUES (?, ?, ?, ?)", (
        str(interaction.user.id),
        username,
        str(user_id),
        datetime.utcnow()
    ))
    db.commit()

    embed = Embed(title="✅ Cittadinanza Accettata", color=discord.Color.green(), timestamp=datetime.utcnow())
    embed.add_field(name="Utente Discord", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
    embed.add_field(name="Username Roblox", value=f"{username} ({user_id})", inline=False)
    embed.add_field(name="Link Profilo", value=f"https://www.roblox.com/users/{user_id}/profile", inline=False)
    embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=420&height=420&format=png")
    embed.set_footer(text="Sistema Cittadinanza")

    canale_log = bot.get_channel(CANALE_LOG)
    if canale_log:
        await canale_log.send(embed=embed)

    await interaction.followup.send("✅ Cittadinanza approvata e registrata nel sistema.", ephemeral=True)

# === COMANDO: CERCA CITTADINO ===
@bot.tree.command(name="cerca_cittadino", description="Cerca un cittadino nel database.")
@app_commands.describe(discord_id="ID utente Discord da cercare")
async def cerca_cittadino(interaction: Interaction, discord_id: str):
    if not ha_permessi(interaction.user):
        await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
        return

    cursor.execute("SELECT * FROM cittadini WHERE user_id = ?", (discord_id,))
    result = cursor.fetchone()

    if result:
        _, username, roblox_id, data = result
        embed = Embed(title="📋 Dati Cittadino", color=discord.Color.blue())
        embed.add_field(name="Discord ID", value=discord_id, inline=False)
        embed.add_field(name="Roblox Username", value=username, inline=False)
        embed.add_field(name="Roblox ID", value=roblox_id, inline=False)
        embed.add_field(name="Registrato il", value=data, inline=False)
        embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={roblox_id}&width=420&height=420&format=png")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message("❌ Nessun cittadino trovato con questo ID.", ephemeral=True)

# === COMANDO: RIMUOVI CITTADINO ===
@bot.tree.command(name="rimuovi_cittadino", description="Rimuovi un cittadino dal database.")
@app_commands.describe(discord_id="ID utente Discord da rimuovere")
async def rimuovi_cittadino(interaction: Interaction, discord_id: str):
    if not ha_permessi(interaction.user):
        await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
        return

    cursor.execute("DELETE FROM cittadini WHERE user_id = ?", (discord_id,))
    db.commit()
    await interaction.response.send_message("✅ Cittadino rimosso dal database.", ephemeral=True)

# Avvio
bot.run(os.getenv("ROMA_TOKEN"))

