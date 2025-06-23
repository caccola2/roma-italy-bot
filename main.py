import os
import discord
from discord.ext import commands
from discord import app_commands, Interaction
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta  # CORRETTO

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

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    try:
        synced = await bot.tree.sync()
        print(f"[DEBUG] Comandi slash sincronizzati: {len(synced)}")
    except Exception as e:
        print(f"[DEBUG] Errore sincronizzazione: {e}")
    print(f"[DEBUG] Bot connesso come {bot.user}")

    # Funzione keep_alive
    async def keep_alive():
        while True:
            print("[DEBUG] Bot ancora vivo...")
            now = datetime.utcnow()
            next_ping = now.replace(second=0, microsecond=0) + timedelta(seconds=30)
            await discord.utils.sleep_until(next_ping)

    bot.loop.create_task(keep_alive())

# ✅ Comando di test
@bot.tree.command(name="check", description="Verifica se il bot è online.")
async def check(interaction: Interaction):
    await interaction.response.send_message("✅ Il bot funziona correttamente!", ephemeral=True)

# 🚀 Avvio
if __name__ == "__main__":
    token = os.getenv("ROMA_TOKEN")
    print(f"[DEBUG] Token presente: {bool(token)}")
    if token:
        print("[DEBUG] Avvio bot...")
        bot.run(token)
    else:
        print("[DEBUG] Variabile ROMA_TOKEN non trovata.")
