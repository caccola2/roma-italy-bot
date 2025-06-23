import os
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread

# 🌐 Web server per tenere vivo il bot su Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot attivo."

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

# ⚙️ Intents attivi (devono essere abilitati anche nel Developer Portal!)
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# 🤖 Setup bot
bot = commands.Bot(command_prefix="!", intents=intents)

# 🟢 Evento quando il bot è online
@bot.event
async def on_ready():
    print("[DEBUG] Evento on_ready avviato")
    await bot.wait_until_ready()
    try:
        synced = await bot.tree.sync()
        print(f"[DEBUG] Comandi slash sincronizzati: {len(synced)}")
    except Exception as e:
        print(f"[DEBUG] Errore sincronizzazione: {e}")
    print(f"[DEBUG] Bot connesso come {bot.user}")

    # 🔁 Task per dimostrare che il bot è vivo ogni 30 secondi
    async def keep_alive():
        while True:
            print("[DEBUG] Bot ancora vivo...")
            await discord.utils.sleep_until(discord.utils.utcnow().replace(second=0, microsecond=0) + discord.utils.timedelta(seconds=30))
    bot.loop.create_task(keep_alive())

# ✅ Comando slash per testare lo stato
@bot.tree.command(name="check", description="Verifica se il bot è online.")
async def check(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Il bot funziona ed è vivo 🐷⚡", ephemeral=True)

# 🚀 Avvio
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    print(f"[DEBUG] Token presente: {bool(token)}")
    if token:
        print("[DEBUG] Avvio bot...")
        bot.run(token)
    else:
        print("[DEBUG] Variabile DISCORD_TOKEN non trovata.")

