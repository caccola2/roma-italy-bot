import os
import discord
from discord.ext import commands
from discord import app_commands, Interaction
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta

# 🌐 Web server
app = Flask('')

@app.route('/')
def home():
    return "Bot attivo."

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

# ⚙️ Intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 📨 Categorie dei ticket (puoi modificarle qui)
CATEGORIE = {
    "supporto": "🛠 Supporto",
    "reclami": "⚠ Reclami",
    "partnership": "🤝 Partnership",
    "altro": "❓ Altro"
}

# 📌 VIEW con i pulsanti
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for key, label in CATEGORIE.items():
            self.add_item(TicketButton(label=label, custom_id=key))

class TicketButton(discord.ui.Button):
    def __init__(self, label, custom_id):
        super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id=custom_id)

    async def callback(self, interaction: Interaction):
        guild = interaction.guild
        user = interaction.user

        # Crea o trova la categoria specifica
        category_name = f"🌐・{self.label}"
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)

        # Verifica se esiste un ticket
        for channel in category.text_channels:
            if channel.name == f"ticket-{user.name.lower()}":
                await interaction.response.send_message("Hai già un ticket aperto!", ephemeral=True)
                return

        # Crea canale
        channel = await guild.create_text_channel(
            name=f"ticket-{user.name}",
            category=category,
            topic=f"Ticket aperto da {user.display_name} per {self.label}",
            permission_overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )

        await channel.send(
            f"{user.mention}, il tuo ticket è stato creato per **{self.label}**. Uno staff ti assisterà a breve.",
            view=CloseTicketView()
        )

        await interaction.response.send_message(f"✅ Ticket creato: {channel.mention}", ephemeral=True)

# ❌ Bottone per chiudere il ticket
class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CloseButton())

class CloseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔒 Chiudi Ticket", style=discord.ButtonStyle.danger, custom_id="close")

    async def callback(self, interaction: Interaction):
        channel = interaction.channel
        await interaction.response.send_message("⏳ Ticket in chiusura...")
        await channel.delete()

# ⚙️ Comando di setup
@bot.tree.command(name="setup_ticket", description="Crea l'embed con i pulsanti per i ticket.")
async def setup_ticket(interaction: Interaction):
    embed = discord.Embed(
        title="🎛 Apri un Ticket",
        description="Premi uno dei pulsanti in basso per aprire un ticket con il nostro staff.\n\n"
                    "📌 Seleziona la categoria corretta per ricevere assistenza più rapidamente.",
        color=discord.Color.blue()
    )
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("✅ Embed creato con successo!", ephemeral=True)

# 📶 Keep Alive + Avvio
@bot.event
async def on_ready():
    await bot.wait_until_ready()
    try:
        synced = await bot.tree.sync()
        print(f"[DEBUG] Comandi slash sincronizzati: {len(synced)}")
    except Exception as e:
        print(f"[DEBUG] Errore sincronizzazione: {e}")
    print(f"[DEBUG] Bot connesso come {bot.user}")

    async def keep_alive():
        while True:
            print("[DEBUG] Bot ancora vivo...")
            now = datetime.utcnow()
            next_ping = now.replace(second=0, microsecond=0) + timedelta(seconds=30)
            await discord.utils.sleep_until(next_ping)

    bot.loop.create_task(keep_alive())

# ✅ MOD PANNEL

# ──────────────── UTILITY PER IL LOG ────────────────

async def send_modlog(interaction, action: str, target: Member, reason: str):
    log_channel = bot.get_channel(MOD_LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(title="🛡️ Azione Moderazione", color=discord.Color.orange())
        embed.add_field(name="Azione", value=action.upper(), inline=True)
        embed.add_field(name="Staff", value=interaction.user.mention, inline=True)
        embed.add_field(name="Utente", value=target.mention, inline=True)
        embed.add_field(name="Motivo", value=reason, inline=False)
        await log_channel.send(embed=embed)

# ──────────────── COMANDI MOD ────────────────

@bot.tree.command(name="kick", description="Espelli un utente dal server.")
@app_commands.describe(utente="Utente da espellere", motivo="Motivo dell'espulsione")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_cmd(interaction: discord.Interaction, utente: Member, motivo: str):
    try:
        await utente.kick(reason=motivo)
        await interaction.response.send_message(f"✅ {utente.mention} è stato **kickato**. Motivo: {motivo}", ephemeral=True)
        await send_modlog(interaction, "Kick", utente, motivo)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Permessi insufficienti.", ephemeral=True)

@bot.tree.command(name="ban", description="Banna un utente dal server.")
@app_commands.describe(utente="Utente da bannare", motivo="Motivo del ban")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_cmd(interaction: discord.Interaction, utente: Member, motivo: str):
    try:
        await utente.ban(reason=motivo, delete_message_days=0)
        await interaction.response.send_message(f"✅ {utente.mention} è stato **bannato**. Motivo: {motivo}", ephemeral=True)
        await send_modlog(interaction, "Ban", utente, motivo)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Permessi insufficienti.", ephemeral=True)

@bot.tree.command(name="mute", description="Silenzia un utente (aggiunge ruolo Muted).")
@app_commands.describe(utente="Utente da mutare", motivo="Motivo del mute")
@app_commands.checks.has_permissions(manage_roles=True)
async def mute_cmd(interaction: discord.Interaction, utente: Member, motivo: str):
    muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not muted_role:
        return await interaction.response.send_message("❌ Ruolo 'Muted' non trovato.", ephemeral=True)
    try:
        await utente.add_roles(muted_role, reason=motivo)
        await interaction.response.send_message(f"🔇 {utente.mention} è stato **mutato**. Motivo: {motivo}", ephemeral=True)
        await send_modlog(interaction, "Mute", utente, motivo)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Permessi insufficienti.", ephemeral=True)

@bot.tree.command(name="unmute", description="Rimuove il silenziamento a un utente.")
@app_commands.describe(utente="Utente da unmutare", motivo="Motivo dell'unmute")
@app_commands.checks.has_permissions(manage_roles=True)
async def unmute_cmd(interaction: discord.Interaction, utente: Member, motivo: str):
    muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not muted_role:
        return await interaction.response.send_message("❌ Ruolo 'Muted' non trovato.", ephemeral=True)
    try:
        await utente.remove_roles(muted_role, reason=motivo)
        await interaction.response.send_message(f"🔓 {utente.mention} è stato **unmutato**. Motivo: {motivo}", ephemeral=True)
        await send_modlog(interaction, "Unmute", utente, motivo)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Permessi insufficienti.", ephemeral=True)

# ──────────────── ERRORI PERMESSI ────────────────

@kick_cmd.error
@ban_cmd.error
@mute_cmd.error
@unmute_cmd.error
async def mod_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("⛔ Non hai i permessi per questo comando.", ephemeral=True)



# 🚀 Avvio
if __name__ == "__main__":
    token = os.getenv("ROMA_TOKEN")
    print(f"[DEBUG] Token presente: {bool(token)}")
    if token:
        print("[DEBUG] Avvio bot...")
        bot.run(token)
    else:
        print("[DEBUG] Variabile ROMA_TOKEN non trovata.")

