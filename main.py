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
    Thread(target=run).start()

# ----- Bot Setup -----
TOKEN = os.getenv("DISCORD_TOKEN") 
intents = discord.Intents.default()
intents.members = True 
intents.message_content = True 
intents.guilds = True 

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced!")

bot = MyBot()

# ----- Logging Helper -----
async def log_action(guild, message):
    channel = discord.utils.get(guild.text_channels, name="mod-logs")
    if channel:
        embed = discord.Embed(
            title="Moderation Log", 
            description=message, 
            color=discord.Color.orange(), 
            timestamp=datetime.datetime.now()
        )
        await channel.send(embed=embed)

# ----- Lock & Lockdown Commands -----

@bot.tree.command(name="lock", description="Toggle lock/unlock on the current channel")
@app_commands.checks.has_permissions(administrator=True)
async def lock(interaction: discord.Interaction):
    channel = interaction.channel
    overwrite = channel.overwrites_for(interaction.guild.default_role)
    
    if overwrite.send_messages is False:
        overwrite.send_messages = True
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(f"🔓 {channel.mention} has been unlocked!")
    else:
        overwrite.send_messages = False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(f"🔒 {channel.mention} has been locked!")

@bot.tree.command(name="lockdown", description="Lock or unlock ALL text channels in the server")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(action="Choose to lock or unlock the whole server")
@app_commands.choices(action=[
    app_commands.Choice(name="Lock Server", value="lock"),
    app_commands.Choice(name="Unlock Server", value="unlock")
])
async def lockdown(interaction: discord.Interaction, action: str):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    
    for channel in guild.text_channels:
        overwrite = channel.overwrites_for(guild.default_role)
        overwrite.send_messages = (action == "unlock")
        await channel.set_permissions(guild.default_role, overwrite=overwrite)
    
    status = "🔒 Server is now in lockdown mode!" if action == "lock" else "🔓 Server lockdown lifted!"
    await interaction.followup.send(status)
    await log_action(guild, f"**Server-wide {action}** executed by {interaction.user.mention}")

# ----- Moderation Commands -----

@bot.tree.command(name="mute", description="Timeout a user (Text & Voice)")
@app_commands.checks.has_permissions(moderate_members=True)
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
    await member.timeout(None)
    log_msg = f"🔊 **{member.display_name}** has been unmuted by {interaction.user.mention}."
    await interaction.response.send_message(f"Removed timeout for {member.mention}.")
    await log_action(interaction.guild, log_msg)

@bot.tree.command(name="purge", description="Delete messages")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"Deleted {len(deleted)} messages.")

# ----- Events -----

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

if __name__ == "__main__":
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Error: No DISCORD_TOKEN found.")