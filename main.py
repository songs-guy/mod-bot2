import discord
from discord.ext import commands, tasks
from collections import defaultdict
import time
import os
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
# IMPORTANT: If you aren't using .env yet, replace os.getenv with "YOUR_TOKEN" 
# just to test locally. Switch back to os.getenv before pushing to GitHub!
TOKEN = os.getenv("DISCORD_TOKEN") 
PREFIX = "!"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

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

# ----- Moderation Commands -----

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    if not member.kickable:
        return await ctx.send("I cannot kick this user.")
    await member.kick(reason=reason)
    await ctx.send(f"{member} has been kicked. Reason: {reason}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    if not member.bannable:
        return await ctx.send("I cannot ban this user.")
    await member.ban(reason=reason)
    await ctx.send(f"{member} has been banned. Reason: {reason}")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name=MUTED_ROLE_NAME)
    if role is None:
        role = await ctx.guild.create_role(name=MUTED_ROLE_NAME)
        for channel in ctx.guild.channels:
            await channel.set_permissions(role, send_messages=False, speak=False)
    await member.add_roles(role)
    await ctx.send(f"{member} has been muted.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name=MUTED_ROLE_NAME)
    if role and role in member.roles:
        await member.remove_roles(role)
        await ctx.send(f"{member} has been unmuted.")
    else:
        await ctx.send("This user is not muted.")

@bot.command()
@commands.has_permissions(kick_members=True)
async def warn(ctx, member: discord.Member, *, reason="No reason provided"):
    user_warns[member.id].append(reason)
    await ctx.send(f"{member} has been warned. Reason: {reason}")

@bot.command(name="warnings")
async def check_warnings(ctx, member: discord.Member):
    warns = user_warns.get(member.id, [])
    if warns:
        formatted = "\n".join(warns)
        await ctx.send(f"{member} has {len(warns)} warning(s):\n{formatted}")
    else:
        await ctx.send("No warnings.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    if amount < 1 or amount > 100:
        return await ctx.send("Please provide a number between 1 and 100.")
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"Deleted {amount} messages.", delete_after=5)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("Channel locked.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("Channel unlocked.")

# ----- Events -----

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    now = time.time()
    last = user_last_message.get(message.author.id, 0)
    if now - last < 3:
        try:
            await message.delete()
            await message.channel.send(f"{message.author.mention}, slow down!", delete_after=3)
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
        print("Error: No TOKEN found. Check your Environment Variables.")