import os
import discord
from discord.ext import commands
from discord import app_commands, Interaction
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta

# 🌐 Web server per Render
app = Flask('')

@app.route('/')
def home():
    return "Bot attivo."

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

# ⚙️ Setup bot
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 🔔 Quando il bot è pronto
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

# ✅ Comando per test
@bot.tree.command(name="check", description="Verifica se il bot è online.")
async def check(interaction: Interaction):
    await interaction.response.send_message("✅ Il bot è attivo!", ephemeral=True)

# 🎟️ Comando per aprire un ticket
@bot.tree.command(name="ticket", description="Apri un ticket di supporto.")
async def ticket(interaction: Interaction):
    guild = interaction.guild
    user = interaction.user

    # Crea nome canale
    channel_name = f"ticket-{user.name}".replace(" ", "-").lower()

    # Permessi
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(view_channel=True),
    }

    # Crea il canale
    channel = await guild.create_text_channel(
        name=channel_name,
        overwrites=overwrites,
        reason=f"Ticket aperto da {user.name}"
    )

    await interaction.response.send_message(f"🎟️ Ticket creato: {channel.mention}", ephemeral=True)
    await channel.send(f"👋 Ciao {user.mention}, uno staff ti risponderà al più presto.\nUsa `/chiudi` per chiudere il ticket quando hai finito.")

# ❌ Comando per chiudere ticket
@bot.tree.command(name="chiudi", description="Chiude il ticket corrente.")
async def chiudi(interaction: Interaction):
    channel = interaction.channel
    if channel.name.startswith("ticket-"):
        await interaction.response.send_message("🗑️ Ticket chiuso. Il canale sarà eliminato in 5 secondi.")
        await discord.utils.sleep_until(datetime.utcnow() + timedelta(seconds=5))
        await channel.delete()
    else:
        await interaction.response.send_message("❌ Questo comando va usato in un ticket.", ephemeral=True)

# 🚀 Avvio
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    print(f"[DEBUG] Token presente: {bool(token)}")
    if token:
        print("[DEBUG] Avvio bot...")
        bot.run(token)
    else:
        print("[DEBUG] Variabile DISCORD_TOKEN non trovata.")
