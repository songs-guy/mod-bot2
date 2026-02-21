import discord
from discord import app_commands
from discord.ext import commands
import datetime 
import os
import time
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
    t = Thread(target=run)
    t.start()

# ----- Configuration -----
TOKEN = os.getenv("DISCORD_TOKEN") 

intents = discord.Intents.default()
intents.members = True 
intents.message_content = True 
intents.guilds = True 

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # This syncs your slash commands with Discord
        await self.tree.sync()
        print("Slash commands synced!")

bot = MyBot()

# ----- Data Storage & Settings -----
user_warns = defaultdict(list) 
user_last_message = {}
MOD_LOG_CHANNEL_NAME = "mod-logs" # Change this to your preferred channel name

# ----- Helper Function for Logs -----
async def log_action(guild, message):
    channel = discord.utils.get(guild.text_channels, name=MOD_LOG_CHANNEL_NAME)
    if channel:
        embed = discord.Embed(
            title="Moderation Log", 
            description=message, 
            color=discord.Color.red(), 
            timestamp=datetime.datetime.now()
        )
        await channel.send(embed=embed)

# ----- Slash Moderation Commands -----

@bot.tree.command(name="mute", description="Timeout a user (Text & Voice)")
@app_commands.checks.has_permissions(moderate_members=True)
@app_commands.describe(minutes="Minutes to timeout", reason="Why are they being muted?")
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
    if member.top_role >= interaction.user.top_role:
        return await interaction.response.send_message("You cannot mute someone with a higher/equal role!", ephemeral=True)

    duration = datetime.timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    
    log_msg = f"🔇 **{member.display_name}** muted for **{minutes}m**.\n**Reason:** {reason}\n**By:** {interaction.user.mention}"
    await interaction.response.send_message(f"Timed out {member.mention} for {minutes} minutes.")
    await log_action(interaction.guild, log_msg)

@bot.tree.command(name="unmute", description="Remove timeout/voice ban")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    if not member.is_timed_out():
        return await interaction.response.send_message("This user is not timed out.", ephemeral=True)

    await member.timeout(None)
    log_msg = f"🔊 **{member.display_name}** has been unmuted by {interaction.user.mention}."
    await interaction.response.send_message(f"Removed timeout for {member.mention}.")
    await log_action(interaction.guild, log_msg)

@bot.tree.command(name="kick", description="Kick a member")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not member.kickable:
        return await interaction.response.send_message("I cannot kick this user.", ephemeral=True)
    
    await member.kick(reason=reason)
    log_msg = f"👞 **{member.display_name}** kicked.\n**Reason:** {reason}\n**By:** {interaction.user.mention}"
    await interaction.response.send_message(f"Kicked {member.mention}.")
    await log_action(interaction.guild, log_msg)

@bot.tree.command(name="purge", description="Delete messages")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        return await interaction.response.send_message("Provide a number between 1-100.", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"Deleted {len(deleted)} messages.")

@bot.tree.command(name="warn", description="Warn a member")
@app_commands.checks.has_permissions(kick_members=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    user_warns[member.id].append(reason)
    log_msg = f"⚠️ **{member.display_name}** warned.\n**Reason:** {reason}\n**By:** {interaction.user.mention}"
    await interaction.response.send_message(f"Warned {member.mention}.")
    await log_action(interaction.guild, log_msg)

# ----- Events -----

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Basic Anti-Spam
    now = time.time()
    last = user_last_message.get(message.author.id, 0)
    if now - last < 2:
        try:
            await message.delete()
        except:
            pass
        return

    user_last_message[message.author.id] = now
    await bot.process_commands(message)

if __name__ == "__main__":
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Error: No DISCORD_TOKEN found in environment variables.")