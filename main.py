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



CANALE_RICHIESTE = 1402403913826701442
CANALE_LOG = 1402374664659144897
ID_RUOLO_TURISTA = 1234567890  # Sostituisci con l'ID reale
ID_RUOLO_CITTADINO = 9876543210  # Sostituisci con l'ID reale
ROBLOX_GROUP_ID = 8730810  # ID fisso del gruppo Roblox
COOKIE = os.getenv("ROBLOX_COOKIE")  # Sicuro da usare se lo setti come variabile ambiente

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

class Cittadinanza(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="richiesta_cittadinanza", description="Invia richiesta di cittadinanza")
    async def richiesta_cittadinanza(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Richiesta Cittadinanza",
            description="Premi il pulsante qui sotto per inviare la tua richiesta di cittadinanza. Verrà valutata dallo staff.",
            color=discord.Color.gold()
        )
        view = RichiestaView(self.bot)
        await interaction.user.send(embed=embed, view=view)
        await interaction.response.send_message("Controlla i tuoi DM per completare la richiesta.", ephemeral=True)

class RichiestaView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Invia Richiesta", style=discord.ButtonStyle.green)
    async def invia(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RichiestaModal(self.bot))

class RichiestaModal(Modal, title="Modulo Cittadinanza"):
    roblox_nick = TextInput(label="Nickname Roblox", placeholder="Inserisci il tuo nick Roblox", required=True)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        roblox_username = self.roblox_nick.value
        user = interaction.user

        await interaction.message.delete()

        roblox_user_id = await get_user_id_legacy(roblox_username)
        if roblox_user_id is None:
            return await user.send("⚠️ Errore nel trovare l'utente Roblox.")

        is_member = await is_user_in_group(roblox_user_id)
        if not is_member:
            await send_esito(self.bot, user, roblox_username, roblox_user_id, False, motivo="Utente non presente nel Gruppo Roblox")
            return

        embed = discord.Embed(
            title="📨 Nuova Richiesta di Cittadinanza",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1104076520292358144/1138941902683539507/Cittadinanza.png")
        embed.add_field(name="Utente Discord", value=f"{user.mention}", inline=False)
        embed.add_field(name="Nick Roblox", value=roblox_username, inline=False)
        embed.add_field(name="Esito", value="In attesa di valutazione", inline=False)

        view = GestioneRichiestaView(self.bot, user, roblox_username, roblox_user_id)
        channel = await self.bot.fetch_channel(CANALE_RICHIESTE)
        await channel.send(embed=embed, view=view)

async def get_user_id_legacy(username: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.roblox.com/users/get-by-username?username={username}") as resp:
            data = await resp.json()
            return data.get("Id") if "Id" in data else None

async def is_user_in_group(user_id: int):
    headers = {"Cookie": f".ROBLOSECURITY={COOKIE}"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f"https://groups.roblox.com/v1/users/{user_id}/groups") as resp:
            if resp.status != 200:
                return False
            data = await resp.json()
            for group in data.get("data", []):
                if group["group"]["id"] == ROBLOX_GROUP_ID:
                    return True
            return False

async def set_user_rank(user_id: int, rank: int):
    headers = {
        "Cookie": f".ROBLOSECURITY={COOKIE}",
        "X-CSRF-TOKEN": await get_xcsrf_token(),
        "Content-Type": "application/json"
    }
    payload = {"userId": user_id, "roleId": rank}
    async with aiohttp.ClientSession(headers=headers) as session:
        await session.patch(f"https://groups.roblox.com/v1/groups/{ROBLOX_GROUP_ID}/users/{user_id}", json=payload)

async def get_xcsrf_token():
    async with aiohttp.ClientSession(cookies={".ROBLOSECURITY": COOKIE}) as session:
        async with session.post("https://auth.roblox.com/v2/logout") as resp:
            return resp.headers.get("x-csrf-token")

class GestioneRichiestaView(View):
    def __init__(self, bot, user, roblox_username, roblox_user_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user
        self.roblox_username = roblox_username
        self.roblox_user_id = roblox_user_id

    @discord.ui.button(label="Accetta", style=discord.ButtonStyle.green)
    async def accetta(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.edit(embed=aggiorna_embed(interaction.message.embeds[0], "Esito: Accettato"), view=None)
        await self.user.send(embed=discord.Embed(
            title="✅ Cittadinanza Approvata",
            description="La tua richiesta è stata accettata. Benvenuto come cittadino!",
            color=discord.Color.green()
        ))
        await assegna_ruoli(self.user)
        await set_user_rank(self.roblox_user_id, 1)  # 1 = ruolo cittadino, cambialo se necessario
        await salva_in_database(self.user.id, self.roblox_username, self.roblox_user_id)
        await send_esito(self.bot, self.user, self.roblox_username, self.roblox_user_id, True)

    @discord.ui.button(label="Rifiuta", style=discord.ButtonStyle.red)
    async def rifiuta(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MotivoRifiutoModal(self.bot, self.user, self.roblox_username, self.roblox_user_id, interaction.message))

class MotivoRifiutoModal(Modal, title="Motivazione Rifiuto"):
    motivo = TextInput(label="Motivo", required=True)

    def __init__(self, bot, user, roblox_username, roblox_user_id, msg):
        super().__init__()
        self.bot = bot
        self.user = user
        self.roblox_username = roblox_username
        self.roblox_user_id = roblox_user_id
        self.msg = msg

    async def on_submit(self, interaction: discord.Interaction):
        await self.msg.edit(embed=aggiorna_embed(self.msg.embeds[0], f"Esito: Rifiutato\nMotivo: {self.motivo.value}"), view=None)
        await send_esito(self.bot, self.user, self.roblox_username, self.roblox_user_id, False, motivo=self.motivo.value)
        await interaction.response.send_message("Richiesta rifiutata.", ephemeral=True)

def aggiorna_embed(embed, new_esito):
    embed.set_field_at(2, name="Esito", value=new_esito, inline=False)
    return embed

async def assegna_ruoli(user):
    guild = user.guild
    turista = guild.get_role(ID_RUOLO_TURISTA)
    cittadino = guild.get_role(ID_RUOLO_CITTADINO)
    if turista in user.roles:
        await user.remove_roles(turista)
    await user.add_roles(cittadino)

async def salva_in_database(user_id, username, roblox_id):
    conn = sqlite3.connect("cittadinanze.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO cittadinanze VALUES (?, ?, ?, ?)", (user_id, username, roblox_id, f"https://www.roblox.com/users/{roblox_id}/profile"))
    conn.commit()
    conn.close()

async def send_esito(bot, user, roblox_username, roblox_id, approvato, motivo=None):
    embed = discord.Embed(
        title="📥 Esito Richiesta Cittadinanza",
        color=discord.Color.green() if approvato else discord.Color.red()
    )
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1104076520292358144/1138941902683539507/Cittadinanza.png")
    embed.add_field(name="Utente Discord", value=user.mention, inline=False)
    embed.add_field(name="Nick Roblox", value=roblox_username, inline=False)
    embed.add_field(name="Profilo", value=f"https://www.roblox.com/users/{roblox_id}/profile", inline=False)
    embed.add_field(name="Esito", value="Accettato ✅" if approvato else f"Rifiutato ❌\nMotivo: {motivo}", inline=False)

    log_channel = await bot.fetch_channel(CANALE_LOG)
    await log_channel.send(embed=embed)

# Comandi per gestione DB
class DB(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="cerca_cittadino")
    async def cerca(self, interaction: discord.Interaction, user_id: str):
        conn = sqlite3.connect("cittadinanze.db")
        c = conn.cursor()
        c.execute("SELECT * FROM cittadinanze WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        if row:
            await interaction.response.send_message(f"🟢 Cittadino trovato:\nDiscord ID: {row[0]}\nRoblox: {row[1]}\nLink: {row[3]}", ephemeral=True)
        else:
            await interaction.response.send_message("🔴 Nessun cittadino trovato con quell'ID.", ephemeral=True)

    @app_commands.command(name="aggiungi_cittadino")
    async def aggiungi(self, interaction: discord.Interaction, user_id: str, username: str, roblox_id: int):
        await salva_in_database(int(user_id), username, roblox_id)
        await interaction.response.send_message("✅ Cittadino aggiunto manualmente.", ephemeral=True)

    @app_commands.command(name="rimuovi_cittadino")
    async def rimuovi(self, interaction: discord.Interaction, user_id: str):
        conn = sqlite3.connect("cittadinanze.db")
        c = conn.cursor()
        c.execute("DELETE FROM cittadinanze WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        await interaction.response.send_message("🗑️ Cittadino rimosso dal database.", ephemeral=True)
