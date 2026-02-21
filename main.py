import discord
from discord import app_commands
from discord.ext import commands
from collections import defaultdict
import time
import os
from threading import Thread
from flask import Flask
import datetime

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

# ----- Data Storage -----
user_warns = defaultdict(list)
user_last_message = {}
join_tracker = defaultdict(list)

RAID_THRESHOLD = 3
RAID_TIME = 10
MUTED_ROLE_NAME = "Muted"

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# ----- Slash Moderation Commands -----

@bot.tree.command(name="kick", description="Kick a member from the server")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not member.kickable:
        return await interaction.response.send_message("I cannot kick this user.", ephemeral=True)
    await member.kick(reason=reason)
    await interaction.response.send_message(f"{member} has been kicked. Reason: {reason}")

@bot.tree.command(name="ban", description="Ban a member from the server")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not member.bannable:
        return await interaction.response.send_message("I cannot ban this user.", ephemeral=True)
    await member.ban(reason=reason)
    await interaction.response.send_message(f"{member} has been banned. Reason: {reason}")

@bot.tree.command(name="mute", description="Timeout a user and ban them from voice for a set time")
@app_commands.checks.has_permissions(moderate_members=True)
@app_commands.describe(minutes="How many minutes should the user be timed out?")
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
    # Check if the user is trying to mute an admin/themselves
    if member.top_role >= interaction.user.top_role:
        return await interaction.response.send_message("You cannot mute someone with a higher or equal role!", ephemeral=True)

    # Convert minutes to a duration
    duration = datetime.timedelta(minutes=minutes)
    
    try:
        # This one command handles text, voice, and reactions
        await member.timeout(duration, reason=reason)
        
        await interaction.response.send_message(
            f"✅ **{member.display_name}** has been timed out for **{minutes} minutes**.\n"
            f"**Reason:** {reason}"
        )
    except Exception as e:
        await interaction.response.send_message(f"Failed to timeout user: {e}", ephemeral=True)

@bot.tree.command(name="warn", description="Give a warning to a member")
@app_commands.checks.has_permissions(kick_members=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    user_warns[member.id].append(reason)
    await interaction.response.send_message(f"{member} has been warned. Reason: {reason}")

@bot.tree.command(name="warnings", description="Check a member's warnings")
async def check_warnings(interaction: discord.Interaction, member: discord.Member):
    warns = user_warns.get(member.id, [])
    if warns:
        formatted = "\n".join(warns)
        await interaction.response.send_message(f"{member} has {len(warns)} warning(s):\n{formatted}")
    else:
        await interaction.response.send_message("No warnings.", ephemeral=True)

@bot.tree.command(name="purge", description="Delete a certain amount of messages")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        return await interaction.response.send_message("Please provide a number between 1 and 100.", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True) # Tells Discord the bot is working
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"Deleted {len(deleted)} messages.")

@bot.tree.command(name="mute", description="Timeout a user (Text & Voice)")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not member.is_timed_out():
        return await interaction.response.send_message("This user is not currently timed out.", ephemeral=True)

    try:
        # Setting timeout to None removes the restriction immediately
        await member.timeout(None, reason=reason)
        await interaction.response.send_message(f"✅ Removed timeout for **{member.display_name}**.")
    except Exception as e:
        await interaction.response.send_message(f"Failed to remove timeout: {e}", ephemeral=True)

# ----- Events (Anti-Spam & Anti-Raid) -----

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    now = time.time()
    last = user_last_message.get(message.author.id, 0)
    if now - last < 3:
        try:
            await message.delete()
        except:
            pass
        return

    user_last_message[message.author.id] = now
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    now = time.time()
    timestamps = join_tracker[member.guild.id]
    timestamps.append(now)
    join_tracker[member.guild.id] = [t for t in timestamps if now - t <= RAID_TIME]

    if len(join_tracker[member.guild.id]) >= RAID_THRESHOLD:
        role = discord.utils.get(member.guild.roles, name=MUTED_ROLE_NAME)
        if role:
            await member.add_roles(role)

if __name__ == "__main__":
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Error: No TOKEN found.")