import os
import discord
import aiohttp
import sqlite3
from discord.ext import commands
from discord import app_commands, Interaction, Embed
from discord.ui import View, Button, Modal, TextInput
from datetime import datetime

# Config
GROUP_ID = 8730810
COOKIE = os.getenv("ROBLOX_COOKIE")
CANALE_RICHIESTE = 1402403913826701442
CANALE_LOG = 1402374664659144897
ID_RUOLO_TURISTA = 1400852869489496185
ID_RUOLO_CITTADINO = 1400856967534215188
ID_RUOLO_ADMIN = 1226305676708679740

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Evento: on_ready → sync comandi
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comandi sincronizzati.")
    except Exception as e:
        print(f"❌ Errore sync comandi: {e}")
    print(f"🤖 Bot connesso come {bot.user}")

# DB init
def create_database():
    conn = sqlite3.connect("cittadinanze.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS cittadinanze (
        user_id INTEGER PRIMARY KEY,
        roblox_username TEXT,
        roblox_user_id INTEGER,
        profile_url TEXT
    )""")
    conn.commit()
    conn.close()

create_database()

# Funzioni utili
async def get_user_id(session, username: str):
    url = "https://users.roblox.com/v1/usernames/users"
    async with session.post(url, json={"usernames": [username]}) as resp:
        data = await resp.json()
        if data.get("data"):
            return data["data"][0]["id"]
    return None

async def is_user_in_group(user_id: int):
    async with aiohttp.ClientSession() as session:
        url = f"https://groups.roblox.com/v1/groups/{GROUP_ID}/users/{user_id}"
        async with session.get(url) as resp:
            return resp.status == 200

async def get_csrf_token(session):
    url = "https://auth.roblox.com/v2/login"
    async with session.post(url) as resp:
        if resp.status == 403:
            return resp.headers.get("x-csrf-token")
    return None

async def get_role_id_by_name(role_name: str):
    roles_map = {
        "Cittadino": 1234567,  # Sostituisci con l'ID reale
    }
    return roles_map.get(role_name)

def ha_permessi(user: discord.Member):
    return any(role.id == ID_RUOLO_ADMIN for role in user.roles)

async def send_esito(bot, user, roblox_username, roblox_user_id, accettato: bool, motivo=None):
    embed_dm = Embed(
        title="🏛️ Cittadinanza " + ("Approvata" if accettato else "Rifiutata"),
        color=discord.Color.green() if accettato else discord.Color.red()
    )
    embed_dm.description = (
        "La tua richiesta di cittadinanza è stata **approvata**! Benvenuto/a."
        if accettato else "La tua richiesta di cittadinanza è stata **rifiutata**."
    )
    if motivo and not accettato:
        embed_dm.add_field(name="Motivazione", value=motivo, inline=False)

    try:
        await user.send(embed=embed_dm)
    except:
        pass

    embed_log = Embed(
        title="Nuova valutazione richiesta cittadinanza",
        color=discord.Color.green() if accettato else discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    embed_log.add_field(name="Utente Discord", value=f"{user} ({user.id})", inline=False)
    embed_log.add_field(name="Username Roblox", value=f"{roblox_username} ({roblox_user_id})", inline=False)
    embed_log.add_field(name="Esito", value="✅ Accettato" if accettato else f"❌ Rifiutato", inline=False)
    if motivo:
        embed_log.add_field(name="Motivazione", value=motivo, inline=False)
    embed_log.set_thumbnail(url="https://cdn.discordapp.com/attachments/1104076520292358144/1138941902683539507/Cittadinanza.png")
    embed_log.set_footer(text="Bot Cittadinanza")

    channel = bot.get_channel(CANALE_LOG)
    if channel:
        await channel.send(embed=embed_log)

# View di gestione
class GestioneRichiestaView(View):
    def __init__(self, bot, richiedente, roblox_username, roblox_user_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.richiedente = richiedente
        self.roblox_username = roblox_username
        self.roblox_user_id = roblox_user_id
        self.messaggio = None

    @discord.ui.button(label="✅ Accetta", style=discord.ButtonStyle.success)
    async def accetta(self, interaction: Interaction, button: Button):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ Permessi insufficienti.", ephemeral=True)
            return

        guild = interaction.guild
        membro = guild.get_member(self.richiedente.id)
        if membro:
            ruolo_turista = guild.get_role(ID_RUOLO_TURISTA)
            ruolo_cittadino = guild.get_role(ID_RUOLO_CITTADINO)
            if ruolo_turista in membro.roles:
                await membro.remove_roles(ruolo_turista)
            if ruolo_cittadino not in membro.roles:
                await membro.add_roles(ruolo_cittadino)

        async with aiohttp.ClientSession() as session:
            csrf_token = await get_csrf_token(session)
            headers = {
                "Cookie": f".ROBLOSECURITY={COOKIE}",
                "X-CSRF-TOKEN": csrf_token,
                "Content-Type": "application/json"
            }
            role_id = await get_role_id_by_name("Cittadino")
            if role_id:
                url = f"https://groups.roblox.com/v1/groups/{GROUP_ID}/users/{self.roblox_user_id}"
                await session.patch(url, headers=headers, json={"roleId": role_id})

        embed = self.messaggio.embeds[0]
        embed.color = discord.Color.green()
        embed.set_field_at(2, name="Esito", value="✅ Accettato", inline=False)
        await self.messaggio.edit(embed=embed, view=None)

        conn = sqlite3.connect("cittadinanze.db")
        c = conn.cursor()
        profile_url = f"https://www.roblox.com/users/{self.roblox_user_id}/profile"
        c.execute("""INSERT OR REPLACE INTO cittadinanze (user_id, roblox_username, roblox_user_id, profile_url)
                     VALUES (?, ?, ?, ?)""",
                  (self.richiedente.id, self.roblox_username, self.roblox_user_id, profile_url))
        conn.commit()
        conn.close()

        await send_esito(self.bot, self.richiedente, self.roblox_username, self.roblox_user_id, True)
        await interaction.response.send_message("✅ Richiesta accettata.", ephemeral=True)

    @discord.ui.button(label="❌ Rifiuta", style=discord.ButtonStyle.danger)
    async def rifiuta(self, interaction: Interaction, button: Button):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ Permessi insufficienti.", ephemeral=True)
            return
        await interaction.response.send_modal(MotivazioneRifiutoModal(self))

class MotivazioneRifiutoModal(Modal, title="Motivazione Rifiuto"):
    motivo = TextInput(label="Motivo", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, view: GestioneRichiestaView):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: Interaction):
        embed = self.view.messaggio.embeds[0]
        embed.color = discord.Color.red()
        embed.set_field_at(2, name="Esito", value="❌ Rifiutato", inline=False)
        embed.add_field(name="Motivazione", value=self.motivo.value, inline=False)
        await self.view.messaggio.edit(embed=embed, view=None)

        await send_esito(self.view.bot, self.view.richiedente, self.view.roblox_username,
                         self.view.roblox_user_id, False, motivo=self.motivo.value)
        await interaction.response.send_message("❌ Richiesta rifiutata.", ephemeral=True)

# ──────────────────────────────
# COMANDI SLASH
# ──────────────────────────────
@bot.tree.command(name="set_group_role", description="Imposta un ruolo nel gruppo Roblox per un utente.")
@app_commands.describe(username="Username dell'utente", role_name="Nome del ruolo")
async def set_group_role(interaction: Interaction, username: str, role_name: str):
    if not ha_permessi(interaction.user):
        await interaction.response.send_message("❌ Permessi insufficienti.", ephemeral=True)
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
                await interaction.followup.send(f"✅ Ruolo impostato per **{username}**.", ephemeral=True)
            else:
                error = await response.text()
                await interaction.followup.send(f"❌ Errore: {response.status} {error}", ephemeral=True)

@bot.tree.command(name="kick_group", description="Espelle un utente dal gruppo.")
@app_commands.describe(username="Username da espellere")
async def kick_group(interaction: Interaction, username: str):
    if not ha_permessi(interaction.user):
        await interaction.response.send_message("❌ Permessi insufficienti.", ephemeral=True)
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
            "X-CSRF-TOKEN": csrf_token,
            "Content-Type": "application/json"
        }
        url = f"https://groups.roblox.com/v1/groups/{GROUP_ID}/users/{user_id}"
        async with session.delete(url, headers=headers) as response:
            if response.status == 200:
                await interaction.followup.send(f"✅ Utente **{username}** espulso dal gruppo.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Errore durante l'espulsione: {response.status}", ephemeral=True)
