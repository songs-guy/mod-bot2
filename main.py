import discord
from discord import app_commands
from discord.ext import commands
import datetime 
import os
import time
import asyncio
from collections import defaultdict
from threading import Thread
from flask import Flask

# ----- Render Keep-Alive Server -----
app = Flask('')
@app.route('/')
def home(): 
    return "Bot is live!"

def run(): 
    app.run(host='0.0.0.0', port=8080)

def keep_alive(): 
    Thread(target=run).start()

# ----- Configuration -----
TOKEN = os.getenv("DISCORD_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") 
SWEAR_WORDS = ["badword1", "badword2"] # Add your filtered words here
MUTED_ROLE_NAME = "Muted"

# Raid Detection Settings
MESSAGE_LIMIT = 5      
TIME_WINDOW = 5        
MUTE_DURATION = 60     

intents = discord.Intents.default()
intents.members = True 
intents.message_content = True 
intents.guilds = True

# Data Tracking
user_message_logs = defaultdict(list)
log_config = {
    "messageDelete": True,
    "messageEdit": True,
    "guildMemberAdd": True,
    "guildMemberRemove": True
}

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced!")

bot = MyBot()

# ----- Logging Helper -----
def send_audit_log(embed):
    if WEBHOOK_URL:
        try:
            webhook = discord.SyncWebhook.from_url(WEBHOOK_URL)
            webhook.send(embed=embed)
        except Exception as e:
            print(f"Webhook error: {e}")

# ----- Events (Anti-Swear, Anti-Raid, & Logs) -----

@bot.event
async def on_message(message):
    if message.author.bot: 
        return

    # 1. Swear Word Filter
    if any(word.lower() in message.content.lower() for word in SWEAR_WORDS):
        await message.delete()
        await message.channel.send(f"{message.author.mention}, watch your language!", delete_after=5)
        return

    # 2. Anti-Raid / Auto-Mute Logic
    now = datetime.datetime.utcnow()
    user_message_logs[message.author.id].append(now)
    user_message_logs[message.author.id] = [t for t in user_message_logs[message.author.id] if (now - t).total_seconds() < TIME_WINDOW]

    if len(user_message_logs[message.author.id]) >= MESSAGE_LIMIT:
        muted_role = discord.utils.get(message.guild.roles, name=MUTED_ROLE_NAME)
        if muted_role:
            await message.author.add_roles(muted_role)
            await message.channel.send(f"🔇 {message.author.mention} has been auto-muted for spamming.")
            user_message_logs[message.author.id].clear()
            
            await asyncio.sleep(MUTE_DURATION)
            await message.author.remove_roles(muted_role)
            await message.channel.send(f"✅ {message.author.mention} has been unmuted.")
        return

    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    if not log_config["messageDelete"] or message.author.bot: 
        return
    embed = discord.Embed(title="🗑️ Message Deleted", description=f"By **{message.author}** in {message.channel.mention}", color=discord.Color.red())
    embed.add_field(name="Content", value=message.content or "No content")
    embed.timestamp = discord.utils.utcnow()
    send_audit_log(embed)

@bot.event
async def on_message_edit(before, after):
    if not log_config["messageEdit"] or before.author.bot or before.content == after.content: 
        return
    embed = discord.Embed(title="✏️ Message Edited", description=f"By **{before.author}** in {before.channel.mention}", color=discord.Color.orange())
    embed.add_field(name="Before", value=before.content or "No content", inline=False)
    embed.add_field(name="After", value=after.content or "No content", inline=False)
    send_audit_log(embed)

@bot.event
async def on_member_join(member):
    if not log_config["guildMemberAdd"]: 
        return
    embed = discord.Embed(title="👋 Member Joined", description=f"{member.mention} joined the server.", color=discord.Color.green())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.timestamp = discord.utils.utcnow()
    send_audit_log(embed)

# ----- Slash Commands -----

@bot.tree.command(name="lock", description="Toggle lock/unlock on the current channel")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction):
    channel = interaction.channel
    overwrite = channel.overwrites_for(interaction.guild.default_role)
    lock_status = not (overwrite.send_messages is False)
    overwrite.send_messages = not lock_status
    await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    action = "locked" if lock_status else "unlocked"
    await interaction.response.send_message(f"Channel has been {action}.")

@bot.tree.command(name="purge", description="Delete messages")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"Deleted {len(deleted)} messages.")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

if __name__ == "__main__":
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Error: No DISCORD_TOKEN found.")