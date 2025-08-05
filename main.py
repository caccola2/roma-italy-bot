import os
import discord
import aiohttp
import sqlite3
from discord.ext import commands
from discord import app_commands, Interaction, Embed
from discord.ui import View, Button, Modal, TextInput
from datetime import datetime

# Variabili configurazione
GROUP_ID = 8730810  # Gruppo Roblox fisso
COOKIE = os.getenv("ROBLOX_COOKIE")
CANALE_RICHIESTE = 1402403913826701442
CANALE_LOG = 1402374664659144897
ID_RUOLO_TURISTA = 1400852869489496185
ID_RUOLO_CITTADINO = 1400856967534215188

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# DB setup
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

# Funzione per recuperare user id da username Roblox
async def get_user_id(username: str):
    async with aiohttp.ClientSession() as session:
        url = "https://users.roblox.com/v1/usernames/users"
        async with session.post(url, json={"usernames": [username]}) as resp:
            data = await resp.json()
            if data.get("data"):
                return data["data"][0]["id"]
    return None

# Controlla se utente è nel gruppo Roblox
async def is_user_in_group(user_id: int):
    async with aiohttp.ClientSession() as session:
        url = f"https://groups.roblox.com/v1/groups/{GROUP_ID}/users/{user_id}"
        async with session.get(url) as resp:
            if resp.status == 200:
                return True
    return False

# Funzione per inviare esito DM e log canale
async def send_esito(bot, user, roblox_username, roblox_user_id, accettato: bool, motivo=None):
    # Embed DM
    embed_dm = Embed(title="🏛️ Cittadinanza " + ("Approvata" if accettato else "Rifiutata"),
                     color=discord.Color.green() if accettato else discord.Color.red())
    if accettato:
        embed_dm.description = "La tua richiesta di cittadinanza è stata **approvata**! Benvenuto/a."
    else:
        embed_dm.description = "La tua richiesta di cittadinanza è stata **rifiutata**."
        if motivo:
            embed_dm.add_field(name="Motivazione", value=motivo, inline=False)

    try:
        await user.send(embed=embed_dm)
    except:
        pass  # L'utente ha DM chiusi

    # Embed log
    embed_log = Embed(title="Nuova valutazione richiesta cittadinanza",
                      color=discord.Color.green() if accettato else discord.Color.red(),
                      timestamp=datetime.utcnow())
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

# View per gestione richiesta (accetta / rifiuta)
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
            await interaction.response.send_message("❌ Non hai i permessi per usare questo pulsante.", ephemeral=True)
            return

        # Rimuovi ruolo turista e assegna cittadino
        guild = interaction.guild
        membro = guild.get_member(self.richiedente.id)
        if membro:
            ruolo_turista = guild.get_role(ID_RUOLO_TURISTA)
            ruolo_cittadino = guild.get_role(ID_RUOLO_CITTADINO)
            if ruolo_turista in membro.roles:
                await membro.remove_roles(ruolo_turista, reason="Cittadinanza accettata")
            if ruolo_cittadino not in membro.roles:
                await membro.add_roles(ruolo_cittadino, reason="Cittadinanza accettata")

        # Imposta ruolo Roblox (ruolo base "Cittadino" nel gruppo)
        async with aiohttp.ClientSession() as session:
            csrf_token = await get_csrf_token(session)
            headers = {
                "Cookie": f".ROBLOSECURITY={COOKIE}",
                "X-CSRF-TOKEN": csrf_token,
                "Content-Type": "application/json"
            }
            # Qui devi impostare l'ID ruolo di "Cittadino" nel gruppo Roblox (esempio: ottienilo a mano)
            role_id_cittadino = await get_role_id_by_name("Cittadino")
            url = f"https://groups.roblox.com/v1/groups/{GROUP_ID}/users/{self.roblox_user_id}"
            payload = {"roleId": role_id_cittadino}
            async with session.patch(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    await interaction.followup.send(f"⚠️ Errore durante l'assegnazione ruolo Roblox ({resp.status})", ephemeral=True)

        # Aggiorna embed nel canale
        embed = self.messaggio.embeds[0]
        embed.color = discord.Color.green()
        embed.set_field_at(2, name="Esito", value="✅ Accettato", inline=False)
        await self.messaggio.edit(embed=embed, view=None)

        # Salva nel database
        conn = sqlite3.connect("cittadinanze.db")
        c = conn.cursor()
        profile_url = f"https://www.roblox.com/users/{self.roblox_user_id}/profile"
        c.execute("INSERT OR REPLACE INTO cittadinanze (user_id, roblox_username, roblox_user_id, profile_url) VALUES (?, ?, ?, ?)",
                  (self.richiedente.id, self.roblox_username, self.roblox_user_id, profile_url))
        conn.commit()
        conn.close()

        # Invia DM e log
        await send_esito(self.bot, self.richiedente, self.roblox_username, self.roblox_user_id, True)
        await interaction.response.send_message("Richiesta accettata con successo.", ephemeral=True)

    @discord.ui.button(label="❌ Rifiuta", style=discord.ButtonStyle.danger)
    async def rifiuta(self, interaction: Interaction, button: Button):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ Non hai i permessi per usare questo pulsante.", ephemeral=True)
            return
        await interaction.response.send_modal(MotivazioneRifiutoModal(self))

class MotivazioneRifiutoModal(Modal, title="Motivazione Rifiuto"):
    motivo = TextInput(label="Motivo", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, view: GestioneRichiestaView):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: Interaction):
        # Aggiorna embed canale
        embed = self.view.messaggio.embeds[0]
        embed.color = discord.Color.red()
        embed.set_field_at(2, name="Esito", value="❌ Rifiutato", inline=False)
        embed.add_field(name="Motivazione", value=self.motivo.value, inline=False)
        await self.view.messaggio.edit(embed=embed, view=None)

        # Invia DM e log
        await send_esito(
            self.view.bot,
            self.view.richiedente,
            self.view.roblox_username,
            self.view.roblox_user_id,
            False,
            motivo=self.motivo.value
        )
        await interaction.response.send_message("Richiesta rifiutata con successo.", ephemeral=True)
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
