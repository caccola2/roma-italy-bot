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

# 📨 Categorie dei ticket
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
        category = discord.utils.get(guild.categories, name="🎫・Tickets")

        if not category:
            category = await guild.create_category("🎫・Tickets")

        # Controlla se esiste già un ticket aperto
        existing = discord.utils.get(guild.text_channels, name=f"ticket-{user.name.lower()}")
        if existing:
            await interaction.response.send_message("Hai già un ticket aperto!", ephemeral=True)
            return

        # Crea il canale
        channel = await guild.create_text_channel(
            name=f"ticket-{user.name}",
            category=category,
            topic=f"Ticket aperto da {user.display_name} per {self.label}",
            permission_overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True)
            }
        )

        await channel.send(
            f"{user.mention}, il tuo ticket è stato creato per **{self.label}**. Uno staff ti assisterà a breve.",
            view=CloseTicketView()
        )

        await interaction.response.send_message(f"✅ Ticket creato: {channel.mention}", ephemeral=True)

# ❌ Bottone per chiudere
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

# ⚙️ Setup comando
@bot.tree.command(name="setup_ticket", description="Crea l'embed con i pulsanti per i ticket.")
async def setup_ticket(interaction: Interaction):
    embed = discord.Embed(
        title="🎫 Apri un Ticket",
        description="Premi uno dei pulsanti in basso per aprire un ticket con il nostro staff.\n\n"
                    "📌 Seleziona la categoria corretta per ricevere assistenza più rapidamente.",
        color=discord.Color.blue()
    )
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("✅ Embed creato con successo!", ephemeral=True)

# 📶 Avvio
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

# 🚀 Avvio
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    print(f"[DEBUG] Token presente: {bool(token)}")
    if token:
        print("[DEBUG] Avvio bot...")
        bot.run(token)
    else:
        print("[DEBUG] Variabile DISCORD_TOKEN non trovata.")
