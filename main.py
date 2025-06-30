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

MOD_LOG_CHANNEL_ID = 123456789012345678  # Sostituisci con l'ID del tuo canale log


class ModPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger, emoji="🛠️", custom_id="kick")
    async def kick_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, action="kick")

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="ban")
    async def ban_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, action="ban")

    @discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary, emoji="🔇", custom_id="mute")
    async def mute_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, action="mute")

    @discord.ui.button(label="Unmute", style=discord.ButtonStyle.success, emoji="🔓", custom_id="unmute")
    async def unmute_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, action="unmute")

    async def handle_action(self, interaction: discord.Interaction, action: str):
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("⛔ Non hai i permessi per usare questo pannello.", ephemeral=True)
            return

        modal = UserActionModal(action)
        await interaction.response.send_modal(modal)


class UserActionModal(discord.ui.Modal, title="Mod Panel – Azione Moderazione"):
    def __init__(self, action: str):
        self.action = action
        super().__init__()

    user_input = discord.ui.TextInput(label="Utente (ID o menzione)", placeholder="@utente o ID", required=True)
    reason = discord.ui.TextInput(label="Motivo", placeholder="Spiega il motivo...", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        try:
            user_id = int(self.user_input.value.strip("<@!>"))
            target = await guild.fetch_member(user_id)
        except:
            await interaction.response.send_message("❌ Utente non valido.", ephemeral=True)
            return

        reason = self.reason.value
        action = self.action

        try:
            if action == "kick":
                await target.kick(reason=reason)
            elif action == "ban":
                await target.ban(reason=reason, delete_message_days=0)
            elif action == "mute":
                muted_role = discord.utils.get(guild.roles, name="Muted")
                if muted_role:
                    await target.add_roles(muted_role, reason=reason)
                else:
                    return await interaction.response.send_message("❌ Ruolo 'Muted' non trovato.", ephemeral=True)
            elif action == "unmute":
                muted_role = discord.utils.get(guild.roles, name="Muted")
                if muted_role:
                    await target.remove_roles(muted_role, reason=reason)
                else:
                    return await interaction.response.send_message("❌ Ruolo 'Muted' non trovato.", ephemeral=True)

            await interaction.response.send_message(f"✅ Azione **{action.upper()}** eseguita su {target.mention}", ephemeral=True)

            log_channel = bot.get_channel(MOD_LOG_CHANNEL_ID)
            if log_channel:
                embed = discord.Embed(title="🛡️ Azione Moderazione", color=discord.Color.red())
                embed.add_field(name="Azione", value=action.upper(), inline=True)
                embed.add_field(name="Staff", value=interaction.user.mention, inline=True)
                embed.add_field(name="Utente", value=target.mention, inline=True)
                embed.add_field(name="Motivo", value=reason, inline=False)
                await log_channel.send(embed=embed)

        except discord.Forbidden:
            await interaction.response.send_message("❌ Permessi insufficienti per questa azione.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Errore: {e}", ephemeral=True)


@bot.tree.command(name="modpanel", description="Invia il pannello di moderazione")
@app_commands.checks.has_permissions(kick_members=True)
async def modpanel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛡️ Pannello Moderazione",
        description="Usa i pulsanti qui sotto per moderare gli utenti.",
        color=discord.Color.blurple()
    )
    await interaction.response.send_message(embed=embed, view=ModPanelView(), ephemeral=True)

@modpanel.error
async def modpanel_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ Non hai i permessi per usare questo comando.", ephemeral=True)



# 🚀 Avvio
if __name__ == "__main__":
    token = os.getenv("ROMA_TOKEN")
    print(f"[DEBUG] Token presente: {bool(token)}")
    if token:
        print("[DEBUG] Avvio bot...")
        bot.run(token)
    else:
        print("[DEBUG] Variabile ROMA_TOKEN non trovata.")

