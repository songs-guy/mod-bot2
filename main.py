import discord
from discord import app_commands
from discord.ext import commands
import datetime 
import os
import asyncio
import random
import re
import logging
import time
from collections import defaultdict
from threading import Thread
from flask import Flask
from supabase import create_client, Client

# ----- Standard Logging Setup -----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord_bot')

# ----- Render Keep-Alive Server -----
app = Flask('')

@app.route('/')
def home(): 
    return "Ultra-Security Moderation Bot is Online"

def run(): 
    app.run(host='0.0.0.0', port=8080)

def keep_alive(): 
    Thread(target=run).start()

# ----- Configuration -----
TOKEN = os.getenv("DISCORD_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") 
SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_KEY")

SWEAR_WORDS = ["badword1", "badword2", "badword3"] 
MUTED_ROLE_NAME = "Muted"
VERIFIED_ROLE_NAME = "Member"
UNVERIFIED_ROLE_NAME = "Unverified"
MIN_ACCOUNT_AGE_DAYS = 1

# Initialize Supabase Client
if SUPA_URL and SUPA_KEY:
    supabase: Client = create_client(SUPA_URL, SUPA_KEY)
    logger.info("✅ Supabase connection initialized.")
else:
    supabase = None
    logger.error("🚨 Supabase credentials missing!")

intents = discord.Intents.all()
user_message_logs = defaultdict(list)

# ----- Captcha Modal System -----

class CaptchaModal(discord.ui.Modal, title="Security Verification"):
    def __init__(self, answer: int):
        super().__init__()
        self.answer = answer
        self.user_answer = discord.ui.TextInput(
            label=f"Anti-Bot: What is {answer - 7} + 7?",
            placeholder="Type the result here...",
            min_length=1,
            max_length=3,
            required=True
        )
        self.add_item(self.user_answer)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if self.user_answer.value == str(self.answer):
                verified_role = discord.utils.get(interaction.guild.roles, name=VERIFIED_ROLE_NAME)
                unverified_role = discord.utils.get(interaction.guild.roles, name=UNVERIFIED_ROLE_NAME)

                if not verified_role:
                    await interaction.response.send_message(f"❌ Error: Role '{VERIFIED_ROLE_NAME}' not found.", ephemeral=True)
                    return

                await interaction.user.add_roles(verified_role)
                if unverified_role and unverified_role in interaction.user.roles:
                    await interaction.user.remove_roles(unverified_role)
                
                await interaction.response.send_message("✅ Success! You are verified.", ephemeral=True)
                send_to_webhook("🛡️ Verification Success", f"User: {interaction.user.mention}", discord.Color.green(), interaction.user)
            else:
                await interaction.response.send_message("❌ Incorrect answer. Try again.", ephemeral=True)
        except Exception as e:
            logger.error(f"Captcha Error: {e}")

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify Identity", style=discord.ButtonStyle.blurple, custom_id="verify_persistent", emoji="🛡️")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_age = (discord.utils.utcnow() - interaction.user.created_at).days
        if user_age < MIN_ACCOUNT_AGE_DAYS:
            await interaction.response.send_message(f"❌ Account too new. Need {MIN_ACCOUNT_AGE_DAYS} day(s).", ephemeral=True)
            return

        answer = random.randint(11, 60)
        await interaction.response.send_modal(CaptchaModal(answer))

# ----- Bot Core Class -----

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!", 
            intents=intents,
            status=discord.Status.online,
            activity=discord.Activity(type=discord.ActivityType.watching, name="over the server")
        )

    async def setup_hook(self):
        self.add_view(VerifyView())
        await self.tree.sync()
        logger.info("Slash commands and UI views synced.")

bot = MyBot()

# ----- Helper Functions -----

def send_to_webhook(title, description, color, member=None):
    if not WEBHOOK_URL: return
    try:
        webhook = discord.SyncWebhook.from_url(WEBHOOK_URL)
        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
        if member: embed.set_footer(text=f"Member ID: {member.id}")
        webhook.send(embed=embed)
    except Exception as e:
        logger.error(f"Webhook Failure: {e}")

async def ensure_muted_role(guild):
    role = discord.utils.get(guild.roles, name=MUTED_ROLE_NAME)
    if not role:
        try:
            role = await guild.create_role(name=MUTED_ROLE_NAME, reason="Auto-Mod Mute Role")
            for channel in guild.channels:
                await channel.set_permissions(role, send_messages=False, add_reactions=False)
        except: pass
    return role

# ----- Global Events -----

@bot.event
async def on_ready():
    logger.info(f"✅ Bot Ready: {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return

    if any(word.lower() in message.content.lower() for word in SWEAR_WORDS):
        await message.delete()
        send_to_webhook("🚫 Content Filtered", f"User: {message.author.mention}\nMessage: {message.content}", discord.Color.red(), message.author)
        return

    now = datetime.datetime.utcnow()
    user_message_logs[message.author.id].append(now)
    user_message_logs[message.author.id] = [t for t in user_message_logs[message.author.id] if (now - t).total_seconds() < 5]

    if len(user_message_logs[message.author.id]) >= 5:
        mute_role = await ensure_muted_role(message.guild)
        if mute_role and mute_role not in message.author.roles:
            await message.author.add_roles(mute_role)
            await message.channel.send(f"🔇 {message.author.mention} auto-muted for spamming.")
            await asyncio.sleep(60)
            await message.author.remove_roles(mute_role)
        return

    await bot.process_commands(message)

# ----- Moderation Slash Commands -----

@bot.tree.command(name="warn", description="Issue a permanent warning")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not supabase: return await interaction.response.send_message("❌ Database not connected.", ephemeral=True)
    
    data = {
        "guild_id": str(interaction.guild.id),
        "user_id": str(member.id),
        "reason": reason,
        "moderator": interaction.user.name,
        "created_at": datetime.datetime.utcnow().isoformat()
    }
    
    try:
        supabase.table("warnings").insert(data).execute()
        await interaction.response.send_message(f"⚠️ **{member.display_name}** warned: `{reason}`")
        send_to_webhook("⚠️ Warned", f"User: {member.mention}\nReason: {reason}", discord.Color.gold(), member)
    except Exception as e:
        await interaction.response.send_message(f"❌ DB Error. Did you run the SQL command in Supabase? Error: {e}", ephemeral=True)

@bot.tree.command(name="warnings", description="View a member's record")
async def warnings(interaction: discord.Interaction, member: discord.Member):
    if not supabase: return await interaction.response.send_message("❌ Database Error.", ephemeral=True)
    
    response = supabase.table("warnings").select("*").eq("user_id", str(member.id)).execute()
    user_warns = response.data

    if not user_warns:
        return await interaction.response.send_message(f"✅ {member.display_name} has no warnings.")

    embed = discord.Embed(title=f"Record: {member.display_name}", color=discord.Color.orange())
    for w in user_warns:
        date = w['created_at'].split("T")[0]
        embed.add_field(name=f"Date: {date}", value=f"Reason: {w['reason']}\nBy: {w['moderator']}", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clear_warnings", description="Wipe a member's record")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear_warnings(interaction: discord.Interaction, member: discord.Member):
    supabase.table("warnings").delete().eq("user_id", str(member.id)).execute()
    await interaction.response.send_message(f"🧹 Cleared warnings for {member.mention}.")

@bot.tree.command(name="setup_verify", description="Deploy the verification portal")
@app_commands.checks.has_permissions(administrator=True)
async def setup_verify(interaction: discord.Interaction):
    embed = discord.Embed(title="🛡️ Security Verification", description="Click the button to verify.", color=discord.Color.blue())
    await interaction.channel.send(embed=embed, view=VerifyView())
    await interaction.response.send_message("Portal deployed.", ephemeral=True)

@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("🔄 Synced!")

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)